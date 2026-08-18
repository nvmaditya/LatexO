import hashlib
from pathlib import Path

from latexo.apply import PatchSet, ReplaceSpan, apply_patchset
from latexo.segment import segment_source
from latexo.snapshot import take_snapshot

RESUME = rb"""\documentclass{article}
\begin{document}
\section{Experience}
\begin{itemize}
\item Shipped the compiler.
\item Cut latency.
\end{itemize}
\end{document}
"""


def _prep(tmp_path: Path):
    live = tmp_path / "live"
    stage = tmp_path / "stage"
    live.mkdir()
    path = live / "resume.tex"
    path.write_bytes(RESUME)
    snap = take_snapshot(live)
    spans = segment_source(snap, live)
    return live, stage, path, snap, spans


def _item(spans, data: bytes, needle: bytes):
    return next(
        s
        for s in spans
        if s.kind == "list_item" and needle in data[s.start_byte : s.end_byte]
    )


def test_replace_writes_staging_only_and_emits_unified_diff(tmp_path: Path) -> None:
    live, stage, path, snap, spans = _prep(tmp_path)
    data = path.read_bytes()
    item = _item(spans, data, b"Shipped the compiler")
    expected = hashlib.sha256(data[item.start_byte : item.end_byte]).hexdigest()
    assert expected == item.text_sha256
    replacement = "\\item Shipped a faster compiler.\n"
    result = apply_patchset(
        snap,
        spans,
        PatchSet(
            patch_id="p1",
            base_revision=snap.revision_id,
            objective="tighten first bullet",
            expected_paths=["resume.tex"],
            operations=[
                ReplaceSpan(
                    operation="replace",
                    span_id=item.span_id,
                    expected_sha256=expected,
                    replacement=replacement,
                )
            ],
        ),
        live,
        stage,
    )
    assert result.ok is True
    assert path.read_bytes() == RESUME
    staged = (stage / "resume.tex").read_bytes()
    assert b"Shipped a faster compiler" in staged
    assert b"Shipped the compiler" not in staged
    assert "Shipped the compiler" in result.unified_diff
    assert "Shipped a faster compiler" in result.unified_diff


def test_stale_hash_fails_without_touching_live_or_succeeding(tmp_path: Path) -> None:
    live, stage, path, snap, spans = _prep(tmp_path)
    data = path.read_bytes()
    item = _item(spans, data, b"Shipped the compiler")
    result = apply_patchset(
        snap,
        spans,
        PatchSet(
            patch_id="p2",
            base_revision=snap.revision_id,
            objective="stale",
            expected_paths=["resume.tex"],
            operations=[
                ReplaceSpan(
                    operation="replace",
                    span_id=item.span_id,
                    expected_sha256="0" * 64,
                    replacement="\\item nearby similar compiler text.\n",
                )
            ],
        ),
        live,
        stage,
    )
    assert result.ok is False
    assert path.read_bytes() == RESUME
    assert result.staging_dir is None
    assert not (stage / "resume.tex").exists()


def test_overlapping_ops_fail_and_leave_live_unchanged(tmp_path: Path) -> None:
    live, stage, path, snap, spans = _prep(tmp_path)
    data = path.read_bytes()
    item = _item(spans, data, b"Shipped the compiler")
    expected = item.text_sha256
    result = apply_patchset(
        snap,
        spans,
        PatchSet(
            patch_id="p3",
            base_revision=snap.revision_id,
            objective="overlap",
            expected_paths=["resume.tex"],
            operations=[
                ReplaceSpan(
                    operation="replace",
                    span_id=item.span_id,
                    expected_sha256=expected,
                    replacement="\\item A.\n",
                ),
                ReplaceSpan(
                    operation="replace",
                    span_id=item.span_id,
                    expected_sha256=expected,
                    replacement="\\item B.\n",
                ),
            ],
        ),
        live,
        stage,
    )
    assert result.ok is False
    assert path.read_bytes() == RESUME
    assert result.staging_dir is None


def test_two_nonoverlapping_ops_apply_together(tmp_path: Path) -> None:
    live, stage, path, snap, spans = _prep(tmp_path)
    data = path.read_bytes()
    a = _item(spans, data, b"Shipped the compiler")
    b = _item(spans, data, b"Cut latency")
    result = apply_patchset(
        snap,
        spans,
        PatchSet(
            patch_id="p4",
            base_revision=snap.revision_id,
            objective="both bullets",
            expected_paths=["resume.tex"],
            operations=[
                ReplaceSpan(
                    operation="replace",
                    span_id=a.span_id,
                    expected_sha256=a.text_sha256,
                    replacement="\\item Shipped v2.\n",
                ),
                ReplaceSpan(
                    operation="replace",
                    span_id=b.span_id,
                    expected_sha256=b.text_sha256,
                    replacement="\\item Cut p99.\n",
                ),
            ],
        ),
        live,
        stage,
    )
    assert result.ok is True
    assert path.read_bytes() == RESUME
    staged = (stage / "resume.tex").read_bytes()
    assert b"Shipped v2" in staged
    assert b"Cut p99" in staged
    assert "Shipped v2" in result.unified_diff
    assert "Cut p99" in result.unified_diff

from pathlib import Path

from latexo.apply import ReplaceSpan, apply_patchset
from latexo.merge import merge_proposals
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


def _ops(a, b):
    return [
        ReplaceSpan(
            operation="replace",
            span_id=a.span_id,
            expected_sha256=a.text_sha256,
            replacement="\\item ALPHA.\n",
        ),
        ReplaceSpan(
            operation="replace",
            span_id=b.span_id,
            expected_sha256=b.text_sha256,
            replacement="\\item BETA.\n",
        ),
    ]


def test_merge_two_items_then_apply_writes_both_in_staging(tmp_path: Path) -> None:
    live, stage, path, snap, spans = _prep(tmp_path)
    data = path.read_bytes()
    a = _item(spans, data, b"Shipped the compiler")
    b = _item(spans, data, b"Cut latency")
    merged = merge_proposals(snap, spans, _ops(a, b), patch_id="m1")
    assert merged.ok is True
    assert merged.candidate is not None
    applied = apply_patchset(snap, spans, merged.candidate, live, stage)
    assert applied.ok is True
    assert path.read_bytes() == RESUME
    staged = (stage / "resume.tex").read_bytes()
    assert b"ALPHA" in staged
    assert b"BETA" in staged
    assert "ALPHA" in applied.unified_diff
    assert "BETA" in applied.unified_diff


def test_overlap_and_nesting_reject_without_partial_staging(tmp_path: Path) -> None:
    live, stage, path, snap, spans = _prep(tmp_path)
    data = path.read_bytes()
    item = _item(spans, data, b"Shipped the compiler")
    section = next(s for s in spans if s.kind == "section")
    same = merge_proposals(
        snap,
        spans,
        [
            ReplaceSpan(
                operation="replace",
                span_id=item.span_id,
                expected_sha256=item.text_sha256,
                replacement="\\item A.\n",
            ),
            ReplaceSpan(
                operation="replace",
                span_id=item.span_id,
                expected_sha256=item.text_sha256,
                replacement="\\item B.\n",
            ),
        ],
        patch_id="m2",
    )
    assert same.ok is False
    assert same.candidate is None
    assert path.read_bytes() == RESUME
    assert not (stage / "resume.tex").exists()

    nested = merge_proposals(
        snap,
        spans,
        [
            ReplaceSpan(
                operation="replace",
                span_id=section.span_id,
                expected_sha256=section.text_sha256,
                replacement="\\section{X}\n",
            ),
            ReplaceSpan(
                operation="replace",
                span_id=item.span_id,
                expected_sha256=item.text_sha256,
                replacement="\\item Y.\n",
            ),
        ],
        patch_id="m3",
    )
    assert nested.ok is False
    assert nested.candidate is None
    assert path.read_bytes() == RESUME
    assert not (stage / "resume.tex").exists()


def test_duplicate_ops_are_rejected(tmp_path: Path) -> None:
    live, stage, path, snap, spans = _prep(tmp_path)
    data = path.read_bytes()
    item = _item(spans, data, b"Cut latency")
    op = ReplaceSpan(
        operation="replace",
        span_id=item.span_id,
        expected_sha256=item.text_sha256,
        replacement="\\item Z.\n",
    )
    merged = merge_proposals(snap, spans, [op, op.model_copy()], patch_id="m4")
    assert merged.ok is False
    assert merged.candidate is None
    assert path.read_bytes() == RESUME
    assert not (stage / "resume.tex").exists()


def test_stale_hash_or_revision_rejects_merge(tmp_path: Path) -> None:
    live, stage, path, snap, spans = _prep(tmp_path)
    data = path.read_bytes()
    a = _item(spans, data, b"Shipped the compiler")
    b = _item(spans, data, b"Cut latency")
    ops = _ops(a, b)
    ops[0] = ops[0].model_copy(update={"expected_sha256": "0" * 64})
    stale = merge_proposals(snap, spans, ops, patch_id="m5")
    assert stale.ok is False
    assert stale.candidate is None
    assert path.read_bytes() == RESUME

    bad_rev = merge_proposals(
        snap, spans, _ops(a, b), patch_id="m6", base_revision="deadbeef"
    )
    assert bad_rev.ok is False
    assert bad_rev.candidate is None
    assert path.read_bytes() == RESUME
    assert not (stage / "resume.tex").exists()

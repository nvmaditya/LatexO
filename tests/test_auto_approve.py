import hashlib
from pathlib import Path

from latexo.apply import PatchSet, ReplaceSpan, apply_patchset
from latexo.policy import AutoApprovePolicy, auto_approve
from latexo.review import commit_approved
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
    store = tmp_path / "versions"
    live.mkdir()
    path = live / "resume.tex"
    path.write_bytes(RESUME)
    snap = take_snapshot(live)
    spans = segment_source(snap, live)
    return live, stage, store, path, snap, spans


def _stage(live, stage, snap, spans, path: Path, replacement: str = "\\item Shipped v2.\n"):
    data = path.read_bytes()
    item = next(
        s
        for s in spans
        if s.kind == "list_item" and b"Shipped the compiler" in data[s.start_byte : s.end_byte]
    )
    applied = apply_patchset(
        snap,
        spans,
        PatchSet(
            patch_id="p1",
            base_revision=snap.revision_id,
            objective="rewrite bullet",
            expected_paths=["resume.tex"],
            operations=[
                ReplaceSpan(
                    operation="replace",
                    span_id=item.span_id,
                    expected_sha256=item.text_sha256,
                    replacement=replacement,
                )
            ],
        ),
        live,
        stage,
    )
    return applied


def test_low_risk_policy_auto_approves_and_commit_writes_live(tmp_path: Path) -> None:
    live, stage, store, path, snap, spans = _prep(tmp_path)
    applied = _stage(live, stage, snap, spans, path)
    assert applied.ok
    result = auto_approve(
        policy=AutoApprovePolicy(enabled=True),
        patch_id="p1",
        base_revision=snap.revision_id,
        unified_diff=applied.unified_diff,
        live_root=live,
        expected_paths=["resume.tex"],
        request="Rewrite this bullet more concisely.",
    )
    assert result.issued is True
    assert result.approval is not None
    assert result.approval.patch_id == "p1"
    assert result.approval.base_revision == snap.revision_id
    assert result.approval.diff_sha256 == hashlib.sha256(
        applied.unified_diff.encode("utf-8")
    ).hexdigest()
    committed = commit_approved(
        live,
        stage,
        approval=result.approval,
        patch_id="p1",
        base_revision=snap.revision_id,
        unified_diff=applied.unified_diff,
        store_dir=store,
    )
    assert committed.ok is True
    assert path.read_bytes() == (stage / "resume.tex").read_bytes()


def test_no_policy_or_high_risk_does_not_auto_approve(tmp_path: Path) -> None:
    live, stage, store, path, snap, spans = _prep(tmp_path)
    applied = _stage(live, stage, snap, spans, path)
    off = auto_approve(
        policy=None,
        patch_id="p1",
        base_revision=snap.revision_id,
        unified_diff=applied.unified_diff,
        live_root=live,
        expected_paths=["resume.tex"],
        request="Rewrite this bullet more concisely.",
    )
    assert off.issued is False
    assert off.approval is None
    denied = commit_approved(
        live,
        stage,
        approval=None,
        patch_id="p1",
        base_revision=snap.revision_id,
        unified_diff=applied.unified_diff,
        store_dir=store,
    )
    assert denied.ok is False
    assert path.read_bytes() == RESUME

    risky = auto_approve(
        policy=AutoApprovePolicy(enabled=True),
        patch_id="p1",
        base_revision=snap.revision_id,
        unified_diff=applied.unified_diff,
        live_root=live,
        expected_paths=["resume.tex"],
        request="Add that I increased revenue 47% at Globocorp.",
    )
    assert risky.issued is False
    assert path.read_bytes() == RESUME

    preamble = auto_approve(
        policy=AutoApprovePolicy(enabled=True),
        patch_id="p1",
        base_revision=snap.revision_id,
        unified_diff="--- a/resume.cls\n+++ b/resume.cls\n+\\ProvidesClass{resume}\n",
        live_root=live,
        expected_paths=["resume.cls"],
        request="Change the class file.",
    )
    assert preamble.issued is False


def test_auto_approval_still_cas_after_live_mutation(tmp_path: Path) -> None:
    live, stage, store, path, snap, spans = _prep(tmp_path)
    applied = _stage(live, stage, snap, spans, path)
    result = auto_approve(
        policy=AutoApprovePolicy(enabled=True),
        patch_id="p1",
        base_revision=snap.revision_id,
        unified_diff=applied.unified_diff,
        live_root=live,
        expected_paths=["resume.tex"],
        request="Tighten wording.",
    )
    assert result.issued is True
    mutated = RESUME + b"% mutated\n"
    path.write_bytes(mutated)
    committed = commit_approved(
        live,
        stage,
        approval=result.approval,
        patch_id="p1",
        base_revision=snap.revision_id,
        unified_diff=applied.unified_diff,
        store_dir=store,
    )
    assert committed.ok is False
    assert path.read_bytes() == mutated

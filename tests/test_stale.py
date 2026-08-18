from pathlib import Path

from latexo.apply import PatchSet, ReplaceSpan, apply_patchset
from latexo.review import commit_approved, issue_approval
from latexo.segment import segment_source
from latexo.snapshot import take_snapshot

RESUME = rb"""\documentclass{article}
\begin{document}
\section{A}
\item Hello.
\end{document}
"""


def test_stale_apply_and_commit_do_not_overwrite_mutated_live(tmp_path: Path) -> None:
    live = tmp_path / "live"
    stage = tmp_path / "stage"
    store = tmp_path / "store"
    live.mkdir()
    path = live / "resume.tex"
    path.write_bytes(RESUME)
    snap = take_snapshot(live)
    spans = segment_source(snap, live)
    item = next(
        s
        for s in spans
        if s.kind in {"list_item", "paragraph"}
        and b"Hello" in RESUME[s.start_byte : s.end_byte]
    )
    patch = PatchSet(
        patch_id="stale",
        base_revision=snap.revision_id,
        objective="x",
        expected_paths=["resume.tex"],
        operations=[
            ReplaceSpan(
                operation="replace",
                span_id=item.span_id,
                expected_sha256=item.text_sha256,
                replacement="CHANGED\n",
            )
        ],
    )
    mutated = RESUME + b"% extra\n"
    path.write_bytes(mutated)
    applied = apply_patchset(snap, spans, patch, live, stage)
    assert applied.ok is False
    assert path.read_bytes() == mutated
    assert applied.staging_dir is None

    path.write_bytes(RESUME)
    good = apply_patchset(snap, spans, patch, live, stage)
    assert good.ok is True
    approval = issue_approval("stale", snap.revision_id, good.unified_diff)
    path.write_bytes(mutated)
    committed = commit_approved(
        live,
        stage,
        approval=approval,
        patch_id="stale",
        base_revision=snap.revision_id,
        unified_diff=good.unified_diff,
        store_dir=store,
    )
    assert committed.ok is False
    assert path.read_bytes() == mutated

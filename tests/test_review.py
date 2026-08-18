import hashlib
from pathlib import Path

from latexo.apply import PatchSet, ReplaceSpan, apply_patchset
from latexo.review import (
    RepairSession,
    commit_approved,
    issue_approval,
    repair_candidate,
    undo_last,
)
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


def _stage_replace(live, stage, snap, spans, path: Path) -> tuple:
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
                    replacement="\\item Shipped v2.\n",
                )
            ],
        ),
        live,
        stage,
    )
    return applied, item


def test_repair_accepts_one_candidate_fix_and_refuses_a_second(tmp_path: Path) -> None:
    live, stage, _store, path, _snap, _spans = _prep(tmp_path)
    stage.mkdir()
    (stage / "resume.tex").write_bytes(b"broken\n")
    session = RepairSession()
    first = repair_candidate(
        session,
        reason="candidate_failure",
        live_root=live,
        staging_root=stage,
        correction=b"\\documentclass{article}\n\\begin{document}fixed\\end{document}\n",
        path="resume.tex",
    )
    assert first.ok is True
    assert first.attempt == 1
    assert path.read_bytes() == RESUME
    assert (stage / "resume.tex").read_bytes().startswith(b"\\documentclass")
    second = repair_candidate(
        session,
        reason="candidate_failure",
        live_root=live,
        staging_root=stage,
        correction=b"again\n",
        path="resume.tex",
    )
    assert second.ok is False
    assert "repair budget" in (second.error or "").lower()
    assert path.read_bytes() == RESUME
    assert (stage / "resume.tex").read_bytes().startswith(b"\\documentclass")


def test_repair_rejects_escaping_path_and_leaves_live_untouched(tmp_path: Path) -> None:
    live, stage, _store, path, _snap, _spans = _prep(tmp_path)
    stage.mkdir()
    (stage / "resume.tex").write_bytes(b"broken\n")
    outside = tmp_path / "outside.tex"
    outside.write_bytes(b"secret\n")
    session = RepairSession()
    relative = repair_candidate(
        session,
        reason="candidate_failure",
        live_root=live,
        staging_root=stage,
        correction=b"PWNED\n",
        path="../live/resume.tex",
    )
    assert relative.ok is False
    assert path.read_bytes() == RESUME
    assert (stage / "resume.tex").read_bytes() == b"broken\n"
    absolute = repair_candidate(
        session,
        reason="candidate_failure",
        live_root=live,
        staging_root=stage,
        correction=b"PWNED\n",
        path=str(outside.resolve()),
    )
    assert absolute.ok is False
    assert outside.read_bytes() == b"secret\n"
    assert path.read_bytes() == RESUME
    assert session.attempts == 0


def test_missing_fact_is_ask_not_repair(tmp_path: Path) -> None:
    live, stage, _store, path, _snap, _spans = _prep(tmp_path)
    stage.mkdir()
    (stage / "resume.tex").write_bytes(b"x\n")
    session = RepairSession()
    result = repair_candidate(
        session,
        reason="missing_fact",
        live_root=live,
        staging_root=stage,
        correction=b"invented 47%\n",
        path="resume.tex",
    )
    assert result.ok is False
    assert result.requires_clarification is True
    assert session.attempts == 0
    assert path.read_bytes() == RESUME
    assert (stage / "resume.tex").read_bytes() == b"x\n"


def test_commit_requires_matching_approval_and_cas(tmp_path: Path) -> None:
    live, stage, store, path, snap, spans = _prep(tmp_path)
    applied, _item = _stage_replace(live, stage, snap, spans, path)
    assert applied.ok
    bad = commit_approved(
        live,
        stage,
        approval=None,
        patch_id="p1",
        base_revision=snap.revision_id,
        unified_diff=applied.unified_diff,
        store_dir=store,
    )
    assert bad.ok is False
    assert path.read_bytes() == RESUME

    approval = issue_approval("p1", snap.revision_id, applied.unified_diff)
    wrong = commit_approved(
        live,
        stage,
        approval=approval,
        patch_id="other",
        base_revision=snap.revision_id,
        unified_diff=applied.unified_diff,
        store_dir=store,
    )
    assert wrong.ok is False
    assert path.read_bytes() == RESUME

    path.write_bytes(RESUME + b"% mutated\n")
    stale = commit_approved(
        live,
        stage,
        approval=approval,
        patch_id="p1",
        base_revision=snap.revision_id,
        unified_diff=applied.unified_diff,
        store_dir=store,
    )
    assert stale.ok is False
    assert path.read_bytes() == RESUME + b"% mutated\n"

    path.write_bytes(RESUME)
    good = commit_approved(
        live,
        stage,
        approval=approval,
        patch_id="p1",
        base_revision=snap.revision_id,
        unified_diff=applied.unified_diff,
        store_dir=store,
    )
    assert good.ok is True
    assert path.read_bytes() == (stage / "resume.tex").read_bytes()
    assert b"Shipped v2" in path.read_bytes()
    assert good.record is not None
    assert good.record.patch_id == "p1"
    assert good.record.old_revision == snap.revision_id
    assert good.record.approval.diff_sha256 == hashlib.sha256(
        applied.unified_diff.encode("utf-8")
    ).hexdigest()


def test_undo_restores_prior_bytes_and_keeps_version_record(tmp_path: Path) -> None:
    live, stage, store, path, snap, spans = _prep(tmp_path)
    applied, _item = _stage_replace(live, stage, snap, spans, path)
    approval = issue_approval("p1", snap.revision_id, applied.unified_diff)
    committed = commit_approved(
        live,
        stage,
        approval=approval,
        patch_id="p1",
        base_revision=snap.revision_id,
        unified_diff=applied.unified_diff,
        store_dir=store,
    )
    assert committed.ok
    original_id = committed.record.record_id
    undone = undo_last(live, store)
    assert undone.ok is True
    assert path.read_bytes() == RESUME
    records = undone.records
    assert any(r.record_id == original_id for r in records)
    assert any(r.kind == "undo" for r in records)

from pathlib import Path

from latexo.locate import locate_targets
from latexo.plan import UserFact, plan_edit
from latexo.segment import segment_source
from latexo.snapshot import take_snapshot

RESUME = rb"""\documentclass{article}
\newcommand{\role}[1]{#1}
\begin{document}
\section{Experience}
Acme Corp built widgets.

\begin{itemize}
\item Shipped the compiler.
\item Cut latency.
\end{itemize}
\end{document}
"""

ALLOWED = {"replace", "insert_before", "insert_after", "delete"}


def _prep(tmp_path: Path):
    path = tmp_path / "resume.tex"
    path.write_bytes(RESUME)
    snap = take_snapshot(tmp_path)
    spans = segment_source(snap, tmp_path)
    return snap, spans, RESUME


def _locate_item(tmp_path: Path, snap, spans, data: bytes):
    item = next(
        s
        for s in spans
        if s.kind == "list_item" and b"Shipped the compiler" in data[s.start_byte : s.end_byte]
    )
    located = locate_targets(
        snap,
        spans,
        workspace_root=tmp_path,
        active_file="resume.tex",
        selection={"start_byte": item.start_byte + 6, "end_byte": item.start_byte + 14},
    )
    return item, located


def test_unique_rewrite_names_existing_span_and_requires_approval(tmp_path: Path) -> None:
    snap, spans, data = _prep(tmp_path)
    item, located = _locate_item(tmp_path, snap, spans, data)
    result = plan_edit(
        snap,
        spans,
        located,
        "Rewrite this bullet more concisely without adding facts.",
        workspace_root=tmp_path,
    )
    assert result.requires_clarification is False
    assert result.plan is not None
    assert result.plan.requires_approval is True
    assert result.plan.changes
    known = {s.span_id for s in spans}
    for change in result.plan.changes:
        assert change.action in ALLOWED
        assert change.target_span_ids
        assert set(change.target_span_ids) <= known
        assert change.target_span_ids == [item.span_id]
        assert change.invariants
    assert "resume.tex" in result.plan.expected_paths
    for change in result.plan.changes:
        for span_id in change.target_span_ids:
            assert span_id != f"{item.start_byte}:{item.end_byte}"
            assert not span_id.isdigit()


def test_missing_metric_asks_and_does_not_invent_fact_ids(tmp_path: Path) -> None:
    snap, spans, data = _prep(tmp_path)
    _item, located = _locate_item(tmp_path, snap, spans, data)
    result = plan_edit(
        snap,
        spans,
        located,
        "Add that I increased revenue 47% at Globocorp.",
        workspace_root=tmp_path,
    )
    assert result.requires_clarification is True
    allowed: list[str] = []
    if result.plan is not None:
        for change in result.plan.changes:
            allowed.extend(change.allowed_fact_ids)
    assert "47%" not in allowed
    assert not any("globocorp" in fid.lower() for fid in allowed)
    assert not any(fid.startswith("invented:") for fid in allowed)


def test_supplied_user_fact_is_allowed_on_the_change(tmp_path: Path) -> None:
    snap, spans, data = _prep(tmp_path)
    _item, located = _locate_item(tmp_path, snap, spans, data)
    result = plan_edit(
        snap,
        spans,
        located,
        "Add that I increased revenue 47%.",
        workspace_root=tmp_path,
        user_facts=[UserFact(fact_id="user:revenue", text="increased revenue 47%")],
    )
    assert result.requires_clarification is False
    assert result.plan is not None
    assert result.plan.requires_approval is True
    allowed = [fid for c in result.plan.changes for fid in c.allowed_fact_ids]
    assert "user:revenue" in allowed
    known = {s.span_id for s in spans}
    for change in result.plan.changes:
        assert set(change.target_span_ids) <= known

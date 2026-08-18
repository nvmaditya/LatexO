from pathlib import Path

from latexo.facts import build_fact_ledger
from latexo.locate import locate_targets
from latexo.plan import UserFact, plan_edit
from latexo.segment import segment_source
from latexo.snapshot import take_snapshot

RESUME = rb"""\documentclass{article}
\begin{document}
\section{Experience}
Acme Corp, 2019--2022.

\begin{itemize}
\item Shipped the compiler.
\end{itemize}
\end{document}
"""


def _prep(tmp_path: Path):
    path = tmp_path / "resume.tex"
    path.write_bytes(RESUME)
    snap = take_snapshot(tmp_path)
    spans = segment_source(snap, tmp_path)
    return path, snap, spans


def test_document_facts_bind_to_existing_spans(tmp_path: Path) -> None:
    path, snap, spans = _prep(tmp_path)
    data = path.read_bytes()
    ledger = build_fact_ledger(snap, spans, tmp_path)
    assert ledger.revision_id == snap.revision_id
    known = {s.span_id for s in spans}
    docs = [f for f in ledger.facts if f.source == "document"]
    assert docs
    orgs = [f for f in docs if f.category in {"organization", "employer"}]
    assert orgs
    org = next(f for f in orgs if "acme" in f.original_text.lower())
    assert org.source_span_id in known
    span = next(s for s in spans if s.span_id == org.source_span_id)
    chunk = data[span.start_byte : span.end_byte]
    assert org.original_text.encode("utf-8") in chunk
    dated = [f for f in docs if f.category in {"date", "year", "quantity"}]
    assert dated
    for fact in docs:
        assert fact.source_span_id in known
        assert fact.revision_id == snap.revision_id
        home = next(s for s in spans if s.span_id == fact.source_span_id)
        assert fact.original_text.encode("utf-8") in data[home.start_byte : home.end_byte]


def test_user_claim_is_user_message_source(tmp_path: Path) -> None:
    _path, snap, spans = _prep(tmp_path)
    ledger = build_fact_ledger(
        snap,
        spans,
        tmp_path,
        user_facts=[UserFact(fact_id="user:revenue", text="increased revenue 47%")],
    )
    users = [f for f in ledger.facts if f.source == "user_message"]
    assert users
    hit = next(f for f in users if "47%" in f.original_text or f.fact_id == "user:revenue")
    assert hit.source == "user_message"
    assert hit.source_span_id is None


def test_absent_metric_is_not_a_document_fact(tmp_path: Path) -> None:
    _path, snap, spans = _prep(tmp_path)
    ledger = build_fact_ledger(snap, spans, tmp_path)
    blob = " ".join(
        f"{f.original_text} {f.normalized_value} {f.fact_id}"
        for f in ledger.facts
        if f.source == "document"
    ).lower()
    assert "47%" not in blob
    assert "globocorp" not in blob


def test_planner_uses_ledger_ids_and_still_asks(tmp_path: Path) -> None:
    path, snap, spans = _prep(tmp_path)
    data = path.read_bytes()
    ledger = build_fact_ledger(snap, spans, tmp_path)
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
    blocked = plan_edit(
        snap,
        spans,
        located,
        "Add that I increased revenue 47% at Globocorp.",
        workspace_root=tmp_path,
        ledger=ledger,
    )
    assert blocked.requires_clarification is True
    allowed = []
    if blocked.plan is not None:
        allowed = [fid for c in blocked.plan.changes for fid in c.allowed_fact_ids]
    assert "47%" not in allowed
    assert not any("globocorp" in fid.lower() for fid in allowed)
    assert not any(fid.startswith("invented:") for fid in allowed)

    rewrite = plan_edit(
        snap,
        spans,
        located,
        "Rewrite this bullet more concisely without adding facts.",
        workspace_root=tmp_path,
        ledger=ledger,
    )
    assert rewrite.requires_clarification is False
    assert rewrite.plan is not None
    ledger_ids = {f.fact_id for f in ledger.facts}
    for change in rewrite.plan.changes:
        assert set(change.allowed_fact_ids) <= ledger_ids

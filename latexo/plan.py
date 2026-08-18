from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from latexo.facts import FactLedger

from pydantic import BaseModel, Field

from latexo.locate import LocationResult
from latexo.segment import SourceSpan
from latexo.snapshot import WorkspaceSnapshot, resolve_in_workspace

_METRIC = re.compile(r"\d+(?:\.\d+)?%|\$[\d,]+(?:\.\d+)?")
_EMPLOYER = re.compile(
    r"\b(?:at|for|joined)\s+([A-Z][\w.&-]+(?:\s+[A-Z][\w.&-]+)*)"
)


class UserFact(BaseModel):
    fact_id: str
    text: str


class PlannedChange(BaseModel):
    target_span_ids: list[str]
    action: Literal["replace", "insert_before", "insert_after", "delete"]
    instruction: str
    allowed_fact_ids: list[str] = Field(default_factory=list)
    invariants: list[str] = Field(default_factory=list)


class EditPlan(BaseModel):
    summary: str
    changes: list[PlannedChange]
    expected_paths: list[str]
    validation_requirements: list[str]
    requires_approval: bool


class PlanningResult(BaseModel):
    plan: EditPlan | None
    requires_clarification: bool


def _action(request: str) -> Literal["replace", "insert_before", "insert_after", "delete"]:
    lower = request.lower()
    if re.search(r"\b(delete|remove)\b", lower):
        return "delete"
    if re.search(r"insert\s+before|add\s+before", lower):
        return "insert_before"
    if re.search(r"insert\s+after|add\s+after", lower):
        return "insert_after"
    return "replace"


def _document_text(
    spans: list[SourceSpan], workspace_root: Path | None
) -> str:
    if workspace_root is None:
        return ""
    chunks: list[str] = []
    seen: set[str] = set()
    for span in spans:
        if span.path in seen:
            continue
        seen.add(span.path)
        data = resolve_in_workspace(workspace_root, span.path).read_bytes()
        chunks.append(data.decode("utf-8", errors="replace"))
    return "\n".join(chunks)


def _claims(request: str) -> list[str]:
    found = [m.group(0) for m in _METRIC.finditer(request)]
    found.extend(m.group(1) for m in _EMPLOYER.finditer(request))
    return found


def _covered(claim: str, document: str, facts: list[UserFact], ledger_texts: list[str]) -> bool:
    needle = claim.lower()
    if needle in document.lower():
        return True
    if any(needle in fact.text.lower() for fact in facts):
        return True
    return any(needle in text.lower() for text in ledger_texts)


def plan_edit(
    snapshot: WorkspaceSnapshot,
    spans: list[SourceSpan],
    location: LocationResult,
    request: str,
    *,
    workspace_root: Path | None = None,
    user_facts: list[UserFact] | None = None,
    ledger: FactLedger | None = None,
) -> PlanningResult:
    from latexo.facts import FactLedger, build_fact_ledger

    facts = list(user_facts or [])
    known = {s.span_id for s in spans if s.revision_id == snapshot.revision_id}
    if location.requires_clarification or location.targeting_mode != "single":
        return PlanningResult(plan=None, requires_clarification=True)
    targets = [t.span_id for t in location.targets if t.span_id in known]
    if len(targets) != 1:
        return PlanningResult(plan=None, requires_clarification=True)

    if ledger is None and workspace_root is not None:
        ledger = build_fact_ledger(snapshot, spans, workspace_root, user_facts=facts)
    ledger_texts = []
    if ledger is not None:
        ledger_texts = [f.original_text for f in ledger.facts] + [
            f.normalized_value for f in ledger.facts
        ]
    document = _document_text(spans, workspace_root)
    missing = [c for c in _claims(request) if not _covered(c, document, facts, ledger_texts)]
    if missing:
        return PlanningResult(plan=None, requires_clarification=True)

    if ledger is not None:
        allowed = [f.fact_id for f in ledger.facts if f.fact_id]
    else:
        allowed = [f.fact_id for f in facts if f.fact_id]
    span = next(s for s in spans if s.span_id == targets[0])
    change = PlannedChange(
        target_span_ids=targets,
        action=_action(request),
        instruction=request,
        allowed_fact_ids=allowed,
        invariants=[
            "preserve dates, organizations, and surrounding command shape",
        ],
    )
    plan = EditPlan(
        summary=request.strip() or "local edit",
        changes=[change],
        expected_paths=[span.path],
        validation_requirements=[
            "changes stay on expected paths",
            "only allowed facts may be introduced",
        ],
        requires_approval=True,
    )
    return PlanningResult(plan=plan, requires_clarification=False)

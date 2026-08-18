from __future__ import annotations

from latexo.apply import (
    DeleteSpan,
    InsertAtSpan,
    PatchSet,
    ReplaceSpan,
)
from latexo.segment import SourceSpan
from latexo.snapshot import WorkspaceSnapshot
from pydantic import BaseModel


class MergeResult(BaseModel):
    ok: bool
    candidate: PatchSet | None = None
    error: str | None = None


def _span_ref(op: ReplaceSpan | InsertAtSpan | DeleteSpan) -> str:
    if isinstance(op, InsertAtSpan):
        return op.anchor_span_id
    return op.span_id


def _conflicts(a: SourceSpan, b: SourceSpan) -> bool:
    if a.path != b.path:
        return False
    return a.start_byte < b.end_byte and b.start_byte < a.end_byte


def merge_proposals(
    snapshot: WorkspaceSnapshot,
    spans: list[SourceSpan],
    proposals: list[ReplaceSpan | InsertAtSpan | DeleteSpan],
    *,
    patch_id: str,
    objective: str = "",
    base_revision: str | None = None,
) -> MergeResult:
    if base_revision is not None and base_revision != snapshot.revision_id:
        return MergeResult(ok=False, error="base revision does not match snapshot")
    by_id = {s.span_id: s for s in spans if s.revision_id == snapshot.revision_id}
    resolved: list[tuple[ReplaceSpan | InsertAtSpan | DeleteSpan, SourceSpan]] = []
    seen: set[str] = set()
    for op in proposals:
        sid = _span_ref(op)
        if sid in seen:
            return MergeResult(ok=False, error="duplicate span")
        seen.add(sid)
        span = by_id.get(sid)
        if span is None:
            return MergeResult(ok=False, error="unknown span")
        if op.expected_sha256 != span.text_sha256:
            return MergeResult(ok=False, error="span hash mismatch")
        resolved.append((op, span))
    for i, (_op1, left) in enumerate(resolved):
        for _op2, right in resolved[i + 1 :]:
            if _conflicts(left, right):
                return MergeResult(ok=False, error="overlapping or nested operations")
    paths = sorted({span.path for _op, span in resolved})
    return MergeResult(
        ok=True,
        candidate=PatchSet(
            patch_id=patch_id,
            base_revision=snapshot.revision_id,
            objective=objective,
            expected_paths=paths,
            operations=[op for op, _span in resolved],
        ),
    )

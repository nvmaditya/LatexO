from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from latexo.apply import ApplyResult, DeleteSpan, ReplaceSpan, apply_patchset
from latexo.merge import merge_proposals
from latexo.segment import SourceSpan
from latexo.snapshot import WorkspaceSnapshot


class SectionEdit(BaseModel):
    action: Literal["replace", "delete", "reorder"]
    span_id: str
    replacement: str | None = None
    swap_with: str | None = None


def _span(spans: list[SourceSpan], span_id: str) -> SourceSpan:
    return next(s for s in spans if s.span_id == span_id)


def apply_sections(
    snapshot: WorkspaceSnapshot,
    spans: list[SourceSpan],
    workspace_root: Path,
    staging_root: Path,
    edits: list[SectionEdit],
) -> ApplyResult:
    ops: list[ReplaceSpan | DeleteSpan] = []
    for edit in edits:
        target = _span(spans, edit.span_id)
        if edit.action == "delete":
            ops.append(
                DeleteSpan(
                    operation="delete",
                    span_id=target.span_id,
                    expected_sha256=target.text_sha256,
                )
            )
        elif edit.action == "replace":
            ops.append(
                ReplaceSpan(
                    operation="replace",
                    span_id=target.span_id,
                    expected_sha256=target.text_sha256,
                    replacement=edit.replacement or "",
                )
            )
        else:
            if not edit.swap_with:
                return ApplyResult(ok=False, error="reorder requires swap_with")
            other = _span(spans, edit.swap_with)
            left_text = _bytes(workspace_root, target)
            right_text = _bytes(workspace_root, other)
            ops.append(
                ReplaceSpan(
                    operation="replace",
                    span_id=target.span_id,
                    expected_sha256=target.text_sha256,
                    replacement=right_text.decode("utf-8", errors="replace"),
                )
            )
            ops.append(
                ReplaceSpan(
                    operation="replace",
                    span_id=other.span_id,
                    expected_sha256=other.text_sha256,
                    replacement=left_text.decode("utf-8", errors="replace"),
                )
            )
    merged = merge_proposals(snapshot, spans, ops, patch_id="section")
    if not merged.ok or merged.candidate is None:
        return ApplyResult(ok=False, error=merged.error)
    return apply_patchset(snapshot, spans, merged.candidate, workspace_root, staging_root)


def _bytes(workspace_root: Path, span: SourceSpan) -> bytes:
    from latexo.snapshot import resolve_in_workspace

    data = resolve_in_workspace(workspace_root, span.path).read_bytes()
    return data[span.start_byte : span.end_byte]

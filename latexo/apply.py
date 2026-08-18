from __future__ import annotations

import difflib
import hashlib
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from latexo.segment import SourceSpan
from latexo.snapshot import WorkspaceSnapshot, resolve_in_workspace


class ReplaceSpan(BaseModel):
    operation: Literal["replace"]
    span_id: str
    expected_sha256: str
    replacement: str


class InsertAtSpan(BaseModel):
    operation: Literal["insert_before", "insert_after"]
    anchor_span_id: str
    expected_sha256: str
    content: str


class DeleteSpan(BaseModel):
    operation: Literal["delete"]
    span_id: str
    expected_sha256: str


class PatchSet(BaseModel):
    patch_id: str
    base_revision: str
    objective: str
    expected_paths: list[str]
    operations: list[ReplaceSpan | InsertAtSpan | DeleteSpan]


class ApplyResult(BaseModel):
    ok: bool
    staging_dir: Path | None = None
    unified_diff: str = ""
    error: str | None = None


def _span_ref(op: ReplaceSpan | InsertAtSpan | DeleteSpan) -> str:
    if isinstance(op, InsertAtSpan):
        return op.anchor_span_id
    return op.span_id


def _ranges_overlap(a: SourceSpan, b: SourceSpan) -> bool:
    if a.path != b.path:
        return False
    return a.start_byte < b.end_byte and b.start_byte < a.end_byte


def _fail(message: str) -> ApplyResult:
    return ApplyResult(ok=False, staging_dir=None, unified_diff="", error=message)


def _unified(path: str, old: bytes, new: bytes) -> str:
    old_lines = old.decode("utf-8", errors="replace").splitlines(keepends=True)
    new_lines = new.decode("utf-8", errors="replace").splitlines(keepends=True)
    return "".join(
        difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile=f"a/{path}",
            tofile=f"b/{path}",
        )
    )


def apply_patchset(
    snapshot: WorkspaceSnapshot,
    spans: list[SourceSpan],
    patch: PatchSet,
    workspace_root: Path,
    staging_root: Path,
) -> ApplyResult:
    if patch.base_revision != snapshot.revision_id:
        return _fail("base revision does not match snapshot")
    for record in snapshot.files:
        live_path = resolve_in_workspace(workspace_root, record.path)
        if hashlib.sha256(live_path.read_bytes()).hexdigest() != record.sha256:
            return _fail("workspace changed since snapshot")

    by_id = {s.span_id: s for s in spans if s.revision_id == snapshot.revision_id}
    resolved: list[tuple[ReplaceSpan | InsertAtSpan | DeleteSpan, SourceSpan]] = []
    for op in patch.operations:
        span = by_id.get(_span_ref(op))
        if span is None:
            return _fail("unknown span")
        if span.path not in patch.expected_paths:
            return _fail(f"path outside plan: {span.path}")
        live_path = resolve_in_workspace(workspace_root, span.path)
        data = live_path.read_bytes()
        actual = hashlib.sha256(data[span.start_byte : span.end_byte]).hexdigest()
        if actual != op.expected_sha256 or actual != span.text_sha256:
            return _fail("span hash mismatch")
        resolved.append((op, span))

    for i, (_op1, left) in enumerate(resolved):
        for _op2, right in resolved[i + 1 :]:
            if _ranges_overlap(left, right):
                return _fail("overlapping operations")

    buffers: dict[str, bytearray] = {}
    for _op, span in resolved:
        if span.path not in buffers:
            buffers[span.path] = bytearray(
                resolve_in_workspace(workspace_root, span.path).read_bytes()
            )

    for op, span in sorted(resolved, key=lambda item: (item[1].path, -item[1].start_byte)):
        buf = buffers[span.path]
        if isinstance(op, ReplaceSpan):
            buf[span.start_byte : span.end_byte] = op.replacement.encode("utf-8")
        elif isinstance(op, DeleteSpan):
            del buf[span.start_byte : span.end_byte]
        elif op.operation == "insert_before":
            buf[span.start_byte : span.start_byte] = op.content.encode("utf-8")
        else:
            buf[span.end_byte : span.end_byte] = op.content.encode("utf-8")

    staging_root.mkdir(parents=True, exist_ok=True)
    diffs: list[str] = []
    for rel, buf in sorted(buffers.items()):
        dest = staging_root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(bytes(buf))
        live = resolve_in_workspace(workspace_root, rel).read_bytes()
        diffs.append(_unified(rel, live, bytes(buf)))

    return ApplyResult(
        ok=True,
        staging_dir=staging_root,
        unified_diff="".join(diffs),
        error=None,
    )

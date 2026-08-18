from __future__ import annotations

import re
from pathlib import Path

from pydantic import BaseModel

from latexo.snapshot import WorkspaceSnapshot, resolve_in_workspace

_DOCUMENTCLASS = re.compile(rb"\\documentclass(?:\s*\[[^\]]*\])?\s*\{")
_BEGIN_DOCUMENT = re.compile(rb"\\begin\s*\{\s*document\s*\}")


class RootResolution(BaseModel):
    root_path: str | None
    candidates: list[str]
    requires_clarification: bool
    reason: str


def _is_compilable_root(data: bytes) -> bool:
    return bool(_DOCUMENTCLASS.search(data) and _BEGIN_DOCUMENT.search(data))


def _scan_candidates(snapshot: WorkspaceSnapshot, workspace_root: Path) -> list[str]:
    found: list[str] = []
    for record in snapshot.files:
        if not record.path.lower().endswith(".tex"):
            continue
        path = resolve_in_workspace(workspace_root, record.path)
        if _is_compilable_root(path.read_bytes()):
            found.append(record.path)
    found.sort()
    return found


def resolve_root(
    snapshot: WorkspaceSnapshot,
    workspace_root: Path,
    *,
    explicit_root: str | None = None,
    confirmed_root: str | None = None,
) -> RootResolution:
    del explicit_root, confirmed_root
    candidates = _scan_candidates(snapshot, workspace_root)
    if len(candidates) == 1:
        return RootResolution(
            root_path=candidates[0],
            candidates=candidates,
            requires_clarification=False,
            reason="unique documentclass and document body",
        )
    if not candidates:
        return RootResolution(
            root_path=None,
            candidates=[],
            requires_clarification=True,
            reason="no source with documentclass and document body",
        )
    return RootResolution(
        root_path=None,
        candidates=candidates,
        requires_clarification=True,
        reason="multiple plausible compilation roots",
    )

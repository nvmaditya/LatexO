from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from latexo.snapshot import UnsafePathError, WorkspaceSnapshot, resolve_in_workspace

_LETTERS = frozenset(b"abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ")


class IncludeEdge(BaseModel):
    source: str
    target: str
    command: str
    status: Literal["resolved", "unresolved", "escaped"]


class IncludeMap(BaseModel):
    revision_id: str
    edges: list[IncludeEdge] = Field(default_factory=list)


def _skip_comment(data: bytes, i: int) -> int:
    if i < len(data) and data[i] == 0x25:
        nl = data.find(b"\n", i)
        return len(data) if nl == -1 else nl + 1
    return i


def _read_cs(data: bytes, i: int) -> tuple[bytes, int] | None:
    if i >= len(data) or data[i] != 0x5C:
        return None
    j = i + 1
    if j >= len(data):
        return b"", j
    if data[j] in _LETTERS:
        k = j
        while k < len(data) and data[k] in _LETTERS:
            k += 1
        return data[j:k], k
    return data[j : j + 1], j + 1


def _skip_space(data: bytes, i: int) -> int:
    n = len(data)
    while i < n and data[i] in (0x20, 0x09, 0x0D, 0x0A):
        i += 1
    return i


def _read_target(data: bytes, i: int) -> tuple[str, int] | None:
    i = _skip_space(data, i)
    if i >= len(data):
        return None
    if data[i] == 0x7B:
        end = data.find(b"}", i + 1)
        if end == -1:
            return None
        return data[i + 1 : end].decode("utf-8", errors="replace").strip(), end + 1
    j = i
    while j < len(data) and data[j] not in (0x20, 0x09, 0x0D, 0x0A, 0x25):
        j += 1
    if j == i:
        return None
    return data[i:j].decode("utf-8", errors="replace").strip(), j


def _normalize_tex_name(raw: str) -> str:
    name = raw.replace("\\", "/").strip()
    if not name:
        return name
    if "." not in Path(name).name:
        name = name + ".tex"
    return name


def _classify_target(
    workspace_root: Path,
    source_path: str,
    raw: str,
    snapshot_paths: set[str],
) -> tuple[str, Literal["resolved", "unresolved", "escaped"]]:
    name = _normalize_tex_name(raw)
    source_dir = Path(source_path).parent
    relative = (source_dir / name).as_posix() if source_dir != Path(".") else name
    relative = Path(relative).as_posix()
    try:
        resolved = resolve_in_workspace(workspace_root, relative)
    except UnsafePathError:
        return name, "escaped"
    if not resolved.is_file():
        return Path(relative).as_posix(), "unresolved"
    posix = resolved.relative_to(workspace_root.resolve()).as_posix()
    if posix not in snapshot_paths:
        return posix, "unresolved"
    return posix, "resolved"


def build_include_map(
    snapshot: WorkspaceSnapshot, workspace_root: Path
) -> IncludeMap:
    snapshot_paths = {f.path for f in snapshot.files}
    edges: list[IncludeEdge] = []
    for record in snapshot.files:
        if not record.path.lower().endswith((".tex", ".ltx")):
            continue
        data = resolve_in_workspace(workspace_root, record.path).read_bytes()
        i = 0
        n = len(data)
        while i < n:
            if data[i] == 0x25:
                i = _skip_comment(data, i)
                continue
            cs = _read_cs(data, i)
            if cs is None:
                i += 1
                continue
            name, after = cs
            if name not in {b"input", b"include"}:
                i = after
                continue
            got = _read_target(data, after)
            if got is None:
                i = after
                continue
            raw, nxt = got
            target, status = _classify_target(
                workspace_root, record.path, raw, snapshot_paths
            )
            edges.append(
                IncludeEdge(
                    source=record.path,
                    target=target,
                    command=name.decode("ascii"),
                    status=status,
                )
            )
            i = nxt
    return IncludeMap(revision_id=snapshot.revision_id, edges=edges)


def reaches(edges: list[IncludeEdge], source: str, dest: str) -> bool:
    graph: dict[str, list[str]] = {}
    for edge in edges:
        if edge.status != "resolved":
            continue
        graph.setdefault(edge.source, []).append(edge.target)
    seen = {source}
    stack = [source]
    while stack:
        node = stack.pop()
        for nxt in graph.get(node, []):
            if nxt == dest:
                return True
            if nxt not in seen:
                seen.add(nxt)
                stack.append(nxt)
    return False

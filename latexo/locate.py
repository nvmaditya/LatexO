from __future__ import annotations

import re
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from latexo.segment import SourceSpan
from latexo.snapshot import WorkspaceSnapshot, resolve_in_workspace

_QUOTE = re.compile(r'"([^"]+)"|\'([^\']+)\'')


class LocatedTarget(BaseModel):
    span_id: str
    reason: str
    confidence: float


class LocationResult(BaseModel):
    targets: list[LocatedTarget] = Field(default_factory=list)
    targeting_mode: Literal["single", "all_matching", "none"]
    requires_clarification: bool


def _in_file(spans: list[SourceSpan], active_file: str | None) -> list[SourceSpan]:
    if not active_file:
        return list(spans)
    return [s for s in spans if s.path == active_file]


def _contains_range(span: SourceSpan, start: int, end: int) -> bool:
    return span.start_byte <= start and end <= span.end_byte


def _contains_cursor(span: SourceSpan, cursor: int) -> bool:
    return span.start_byte <= cursor < span.end_byte


def _smallest(candidates: list[SourceSpan]) -> list[SourceSpan]:
    if not candidates:
        return []
    width = min(s.end_byte - s.start_byte for s in candidates)
    return [s for s in candidates if s.end_byte - s.start_byte == width]


def _result(targets: list[LocatedTarget], *, unique: bool) -> LocationResult:
    if unique and len(targets) == 1:
        return LocationResult(
            targets=targets,
            targeting_mode="single",
            requires_clarification=False,
        )
    if not targets:
        return LocationResult(
            targets=[],
            targeting_mode="none",
            requires_clarification=True,
        )
    return LocationResult(
        targets=targets,
        targeting_mode="all_matching",
        requires_clarification=True,
    )


def _from_selection(
    pool: list[SourceSpan], selection: dict
) -> LocationResult | None:
    if "cursor_byte" in selection and "start_byte" not in selection:
        cursor = int(selection["cursor_byte"])
        hits = [s for s in pool if _contains_cursor(s, cursor)]
        reason = "cursor"
    elif "start_byte" in selection and "end_byte" in selection:
        start = int(selection["start_byte"])
        end = int(selection["end_byte"])
        if end < start:
            return _result([], unique=False)
        hits = [s for s in pool if _contains_range(s, start, end)]
        reason = "active selection"
    else:
        return None
    best = _smallest(hits)
    if len(best) == 1:
        return _result(
            [LocatedTarget(span_id=best[0].span_id, reason=reason, confidence=1.0)],
            unique=True,
        )
    if len(best) > 1:
        return _result(
            [
                LocatedTarget(span_id=s.span_id, reason=reason, confidence=0.4)
                for s in best
            ],
            unique=False,
        )
    return _result([], unique=False)


def _queries(request: str) -> list[str]:
    found = [a or b for a, b in _QUOTE.findall(request)]
    if found:
        return found
    text = request.strip()
    return [text] if text else []


def _span_bytes(cache: dict[str, bytes], workspace_root: Path, path: str) -> bytes:
    if path not in cache:
        cache[path] = resolve_in_workspace(workspace_root, path).read_bytes()
    return cache[path]


def _leaf_hits(
    pool: list[SourceSpan],
    workspace_root: Path,
    query: str,
) -> list[SourceSpan]:
    needle = query.encode("utf-8")
    if not needle:
        return []
    cache: dict[str, bytes] = {}
    matches: list[SourceSpan] = []
    for span in pool:
        blob = _span_bytes(cache, workspace_root, span.path)
        if needle in blob[span.start_byte : span.end_byte]:
            matches.append(span)
    leaves: list[SourceSpan] = []
    for span in matches:
        if any(
            other is not span
            and other.path == span.path
            and span.start_byte <= other.start_byte
            and other.end_byte <= span.end_byte
            and (other.start_byte, other.end_byte) != (span.start_byte, span.end_byte)
            for other in matches
        ):
            continue
        leaves.append(span)
    return leaves


def _prefer_heading(hits: list[SourceSpan], query: str, workspace_root: Path) -> list[SourceSpan]:
    marker = ("\\section{" + query + "}").encode("utf-8")
    cache: dict[str, bytes] = {}
    headed = []
    for span in hits:
        if span.kind != "section":
            continue
        blob = _span_bytes(cache, workspace_root, span.path)
        head = blob[span.start_byte : min(span.end_byte, span.start_byte + 80)]
        if marker in head:
            headed.append(span)
    return headed or hits


def locate_targets(
    snapshot: WorkspaceSnapshot,
    spans: list[SourceSpan],
    *,
    request: str = "",
    active_file: str | None = None,
    selection: dict | None = None,
    workspace_root: Path | None = None,
) -> LocationResult:
    known = {s.span_id for s in spans if s.revision_id == snapshot.revision_id}
    live = [s for s in spans if s.span_id in known]
    file_hint = active_file if active_file is not None else snapshot.active_file
    sel = selection if selection is not None else snapshot.selection
    pool = _in_file(live, file_hint)

    if isinstance(sel, dict) and sel:
        selected = _from_selection(pool, sel)
        if selected is not None:
            selected.targets = [t for t in selected.targets if t.span_id in known]
            if selected.targeting_mode == "single" and len(selected.targets) != 1:
                selected.targeting_mode = "none"
                selected.requires_clarification = True
            return selected

    if workspace_root is None or not request.strip():
        return _result([], unique=False)

    hits: list[SourceSpan] = []
    reason = "lexical"
    for query in _queries(request):
        found = _leaf_hits(pool or live, workspace_root, query)
        found = _prefer_heading(found, query, workspace_root)
        if found:
            hits = found
            reason = "quoted text" if _QUOTE.search(request) else "heading"
            break

    if len(hits) == 1:
        return _result(
            [LocatedTarget(span_id=hits[0].span_id, reason=reason, confidence=0.95)],
            unique=True,
        )
    return _result(
        [LocatedTarget(span_id=s.span_id, reason=reason, confidence=0.4) for s in hits],
        unique=False,
    )

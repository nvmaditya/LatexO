from __future__ import annotations

import hashlib
from pathlib import Path

from pydantic import BaseModel, Field

from latexo.snapshot import WorkspaceSnapshot, resolve_in_workspace

_LETTERS = frozenset(b"abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ")


class SourceSpan(BaseModel):
    span_id: str
    revision_id: str
    path: str
    start_byte: int
    end_byte: int
    text_sha256: str
    kind: str
    parent_span_id: str | None = None
    sibling_span_ids: list[str] = Field(default_factory=list)
    semantic_label: str | None = None
    semantic_confidence: float | None = None
    referenced_macros: list[str] = Field(default_factory=list)


def _span_id(revision_id: str, path: str, kind: str, start: int, end: int) -> str:
    payload = f"{revision_id}\n{path}\n{kind}\n{start}\n{end}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


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


def _at_cs(data: bytes, i: int, name: bytes) -> int | None:
    read = _read_cs(data, i)
    if read is None:
        return None
    got, after = read
    return after if got == name else None


def _skip_space_and_comments(data: bytes, i: int) -> int:
    n = len(data)
    while i < n:
        b = data[i]
        if b in (0x20, 0x09, 0x0D, 0x0A):
            i += 1
            continue
        if b == 0x25:
            nl = data.find(b"\n", i)
            i = n if nl == -1 else nl + 1
            continue
        break
    return i


def _match_delim(data: bytes, i: int, open_b: int, close_b: int) -> int | None:
    if i >= len(data) or data[i] != open_b:
        return None
    depth = 0
    n = len(data)
    j = i
    while j < n:
        if data[j] == 0x5C:
            cs = _read_cs(data, j)
            if cs is None:
                return None
            j = cs[1]
            continue
        if data[j] == 0x25:
            nl = data.find(b"\n", j)
            j = n if nl == -1 else nl + 1
            continue
        if data[j] == open_b:
            depth += 1
            j += 1
            continue
        if data[j] == close_b:
            depth -= 1
            j += 1
            if depth == 0:
                return j
            continue
        j += 1
    return None


def _match_braces(data: bytes, i: int) -> int | None:
    return _match_delim(data, i, 0x7B, 0x7D)


def _match_brackets(data: bytes, i: int) -> int | None:
    return _match_delim(data, i, 0x5B, 0x5D)


def _env_name_at_begin(data: bytes, i: int) -> tuple[bytes, int] | None:
    after = _at_cs(data, i, b"begin")
    if after is None:
        return None
    after = _skip_space_and_comments(data, after)
    end = _match_braces(data, after)
    if end is None:
        return None
    return data[after + 1 : end - 1], end


def _env_name_at_end(data: bytes, i: int) -> tuple[bytes, int] | None:
    after = _at_cs(data, i, b"end")
    if after is None:
        return None
    after = _skip_space_and_comments(data, after)
    end = _match_braces(data, after)
    if end is None:
        return None
    return data[after + 1 : end - 1], end


def _find_environments(data: bytes) -> list[tuple[int, int, bytes]]:
    found: list[tuple[int, int, bytes]] = []
    n = len(data)
    i = 0
    while i < n:
        if data[i] == 0x25:
            nl = data.find(b"\n", i)
            i = n if nl == -1 else nl + 1
            continue
        opened = _env_name_at_begin(data, i)
        if opened is None:
            i += 1
            continue
        name, after_begin = opened
        close = _find_matching_end(data, after_begin, name)
        if close is not None:
            found.append((i, close, name))
        i = after_begin
    return found


def _find_matching_end(data: bytes, i: int, name: bytes) -> int | None:
    stack = [name]
    n = len(data)
    while i < n:
        if data[i] == 0x25:
            nl = data.find(b"\n", i)
            i = n if nl == -1 else nl + 1
            continue
        opened = _env_name_at_begin(data, i)
        if opened is not None:
            stack.append(opened[0])
            i = opened[1]
            continue
        closed = _env_name_at_end(data, i)
        if closed is not None:
            cname, after = closed
            if stack and stack[-1] == cname:
                stack.pop()
                if not stack:
                    return after
            i = after
            continue
        if data[i] == 0x5C:
            cs = _read_cs(data, i)
            i = cs[1] if cs else i + 1
            continue
        i += 1
    return None


def _try_macro(data: bytes, i: int) -> int | None:
    after = _at_cs(data, i, b"newcommand")
    if after is None:
        after = _at_cs(data, i, b"renewcommand")
    if after is None:
        return None
    if after < len(data) and data[after] == 0x2A:
        after += 1
    after = _skip_space_and_comments(data, after)
    if after < len(data) and data[after] == 0x7B:
        after = _match_braces(data, after)
    elif after < len(data) and data[after] == 0x5C:
        cs = _read_cs(data, after)
        after = None if cs is None else cs[1]
    else:
        return None
    if after is None:
        return None
    after = _skip_space_and_comments(data, after)
    if after < len(data) and data[after] == 0x5B:
        after = _match_brackets(data, after)
        if after is None:
            return None
        after = _skip_space_and_comments(data, after)
        if after < len(data) and data[after] == 0x5B:
            after = _match_brackets(data, after)
            if after is None:
                return None
            after = _skip_space_and_comments(data, after)
    if after >= len(data) or data[after] != 0x7B:
        return None
    return _match_braces(data, after)


def _find_macros(data: bytes) -> list[tuple[int, int]]:
    found: list[tuple[int, int]] = []
    n = len(data)
    i = 0
    while i < n:
        if data[i] == 0x25:
            nl = data.find(b"\n", i)
            i = n if nl == -1 else nl + 1
            continue
        end = _try_macro(data, i)
        if end is not None:
            found.append((i, end))
            i = end
            continue
        if data[i] == 0x5C:
            cs = _read_cs(data, i)
            i = cs[1] if cs else i + 1
            continue
        i += 1
    return found


def _consume_section_head(data: bytes, i: int) -> int | None:
    after = _at_cs(data, i, b"section")
    if after is None:
        return None
    if after < len(data) and data[after] == 0x2A:
        after += 1
    after = _skip_space_and_comments(data, after)
    if after < len(data) and data[after] == 0x5B:
        after = _match_brackets(data, after)
        if after is None:
            return None
        after = _skip_space_and_comments(data, after)
    if after >= len(data) or data[after] != 0x7B:
        return None
    return _match_braces(data, after)


def _find_sections(data: bytes, limit: int) -> list[tuple[int, int]]:
    heads: list[int] = []
    i = 0
    n = min(len(data), limit) if limit else len(data)
    while i < n:
        if data[i] == 0x25:
            nl = data.find(b"\n", i)
            i = n if nl == -1 else nl + 1
            continue
        if _consume_section_head(data, i) is not None:
            heads.append(i)
            cs = _read_cs(data, i)
            i = cs[1] if cs else i + 1
            continue
        if data[i] == 0x5C:
            cs = _read_cs(data, i)
            i = cs[1] if cs else i + 1
            continue
        i += 1
    spans: list[tuple[int, int]] = []
    for idx, start in enumerate(heads):
        end = heads[idx + 1] if idx + 1 < len(heads) else limit
        if end > start:
            spans.append((start, end))
    return spans


def _find_items(data: bytes, env_start: int, env_end: int) -> list[tuple[int, int]]:
    body_close = env_end
    end_cmd = data.rfind(b"\\end", env_start, env_end)
    if end_cmd != -1:
        body_close = end_cmd
    heads: list[int] = []
    i = env_start
    while i < body_close:
        if data[i] == 0x25:
            nl = data.find(b"\n", i)
            i = body_close if nl == -1 else nl + 1
            continue
        after = _at_cs(data, i, b"item")
        if after is not None:
            heads.append(i)
            i = after
            continue
        if data[i] == 0x5C:
            cs = _read_cs(data, i)
            i = cs[1] if cs else i + 1
            continue
        i += 1
    spans: list[tuple[int, int]] = []
    for idx, start in enumerate(heads):
        end = heads[idx + 1] if idx + 1 < len(heads) else body_close
        if end > start:
            spans.append((start, end))
    return spans


def _split_blank_lines(data: bytes, start: int, end: int) -> list[tuple[int, int]]:
    chunks: list[tuple[int, int]] = []
    i = start
    while i < end:
        while i < end and data[i] in (0x20, 0x09, 0x0D, 0x0A):
            i += 1
        if i >= end:
            break
        j = i
        while j < end:
            if data[j] == 0x0A:
                k = j + 1
                while k < end and data[k] in (0x20, 0x09, 0x0D):
                    k += 1
                if k < end and data[k] == 0x0A:
                    break
            j += 1
        chunks.append((i, j))
        i = j + 1
    return chunks


def _starts_with_cs(data: bytes, i: int, end: int, names: set[bytes]) -> bytes | None:
    i = _skip_space_and_comments(data, i)
    if i >= end:
        return None
    read = _read_cs(data, i)
    if read is None:
        return None
    name, _ = read
    return name if name in names else None


def _find_paragraphs(data: bytes, doc_inner_start: int, doc_inner_end: int) -> list[tuple[int, int]]:
    skip_lead = {b"begin", b"end", b"item", b"newcommand", b"renewcommand"}
    found: list[tuple[int, int]] = []
    for a, b in _split_blank_lines(data, doc_inner_start, doc_inner_end):
        lead = _starts_with_cs(data, a, b, skip_lead | {b"section"})
        start = a
        if lead == b"section":
            head_end = _consume_section_head(data, _skip_space_and_comments(data, a))
            if head_end is None:
                continue
            start = _skip_space_and_comments(data, head_end)
        elif lead in skip_lead:
            continue
        while start < b and data[start] in (0x20, 0x09, 0x0D, 0x0A):
            start += 1
        end = b
        while end > start and data[end - 1] in (0x20, 0x09, 0x0D, 0x0A):
            end -= 1
        if end > start:
            found.append((start, end))
    return found


def _raw_spans(data: bytes) -> list[tuple[int, int, str]]:
    out: list[tuple[int, int, str]] = []
    envs = _find_environments(data)
    doc_begin = next((s for s, _e, name in envs if name == b"document"), None)
    doc_end = next((e for _s, e, name in envs if name == b"document"), len(data))
    if doc_begin is not None and doc_begin > 0:
        out.append((0, doc_begin, "preamble"))
    for start, end, _name in envs:
        out.append((start, end, "environment"))
    section_limit = doc_end
    if doc_begin is not None:
        end_cmd = data.rfind(b"\\end", doc_begin, doc_end)
        if end_cmd != -1:
            section_limit = end_cmd
    for start, end in _find_sections(data, section_limit):
        if doc_begin is not None and start < doc_begin:
            continue
        out.append((start, end, "section"))
    for start, end, name in envs:
        if name in {b"itemize", b"enumerate", b"description"}:
            for a, b in _find_items(data, start, end):
                out.append((a, b, "list_item"))
    for start, end in _find_macros(data):
        out.append((start, end, "macro_definition"))
    inner_start = 0
    inner_end = len(data)
    if doc_begin is not None:
        opened = _env_name_at_begin(data, doc_begin)
        inner_start = opened[1] if opened else doc_begin
        end_at = data.rfind(b"\\end", inner_start, doc_end)
        inner_end = end_at if end_at != -1 else doc_end
    for start, end in _find_paragraphs(data, inner_start, inner_end):
        out.append((start, end, "paragraph"))
    return out


def _assign_family(spans: list[SourceSpan]) -> None:
    for span in spans:
        container: SourceSpan | None = None
        width = None
        for other in spans:
            if other is span:
                continue
            if other.start_byte <= span.start_byte and span.end_byte <= other.end_byte:
                if other.start_byte == span.start_byte and other.end_byte == span.end_byte:
                    continue
                w = other.end_byte - other.start_byte
                if width is None or w < width:
                    container = other
                    width = w
        span.parent_span_id = container.span_id if container else None
    by_parent: dict[str | None, list[SourceSpan]] = {}
    for span in spans:
        by_parent.setdefault(span.parent_span_id, []).append(span)
    for group in by_parent.values():
        ids = [s.span_id for s in group]
        for span in group:
            span.sibling_span_ids = [i for i in ids if i != span.span_id]


def _build_spans(data: bytes, path: str, revision_id: str) -> list[SourceSpan]:
    raw = _raw_spans(data)
    spans: list[SourceSpan] = []
    for start, end, kind in raw:
        if end <= start:
            continue
        spans.append(
            SourceSpan(
                span_id=_span_id(revision_id, path, kind, start, end),
                revision_id=revision_id,
                path=path,
                start_byte=start,
                end_byte=end,
                text_sha256=hashlib.sha256(data[start:end]).hexdigest(),
                kind=kind,
            )
        )
    spans.sort(key=lambda s: (s.start_byte, -(s.end_byte - s.start_byte), s.kind))
    _assign_family(spans)
    return spans


def segment_source(
    snapshot: WorkspaceSnapshot,
    workspace_root: Path,
    *,
    path: str | None = None,
) -> list[SourceSpan]:
    wanted = {path} if path is not None else None
    spans: list[SourceSpan] = []
    for record in snapshot.files:
        if wanted is not None and record.path not in wanted:
            continue
        if not record.path.lower().endswith((".tex", ".ltx", ".sty", ".cls")):
            continue
        file_path = resolve_in_workspace(workspace_root, record.path)
        data = file_path.read_bytes()
        spans.extend(_build_spans(data, record.path, snapshot.revision_id))
    return spans

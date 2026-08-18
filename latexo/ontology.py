from __future__ import annotations

import re
from pathlib import Path

from latexo.segment import SourceSpan
from latexo.snapshot import resolve_in_workspace

_SECTION_HEAD = re.compile(rb"\\section\*?[ \t]*(?:\[[^\]]*\])?[ \t]*\{([^}]*)\}")
_CS = re.compile(rb"\\([A-Za-z]+)")
_NEWCMD = re.compile(
    rb"\\(?:re)?newcommand\*?[ \t]*\{?[ \t]*\\([A-Za-z]+)"
)

_LABELS = (
    (b"experience", "experience"),
    (b"employment", "experience"),
    (b"work", "experience"),
    (b"education", "education"),
    (b"skills", "skills"),
    (b"projects", "projects"),
    (b"summary", "summary"),
    (b"objective", "summary"),
)


def _file_bytes(cache: dict[str, bytes], workspace_root: Path, path: str) -> bytes:
    if path not in cache:
        cache[path] = resolve_in_workspace(workspace_root, path).read_bytes()
    return cache[path]


def label_spans(spans: list[SourceSpan], workspace_root: Path) -> list[SourceSpan]:
    cache: dict[str, bytes] = {}
    labeled: list[SourceSpan] = []
    for span in spans:
        copy = span.model_copy()
        data = _file_bytes(cache, workspace_root, span.path)
        chunk = data[span.start_byte : span.end_byte]
        if span.kind == "section":
            head = _SECTION_HEAD.search(chunk)
            title = head.group(1).lower() if head else chunk[:80].lower()
            for needle, label in _LABELS:
                if needle in title:
                    copy.semantic_label = label
                    break
        labeled.append(copy)
    return labeled


def lookup_macros(
    spans: list[SourceSpan], workspace_root: Path, span_id: str
) -> list[dict]:
    cache: dict[str, bytes] = {}
    target = next(s for s in spans if s.span_id == span_id)
    data = _file_bytes(cache, workspace_root, target.path)
    used = set(_CS.findall(data[target.start_byte : target.end_byte]))
    found: list[dict] = []
    for span in spans:
        if span.kind != "macro_definition":
            continue
        blob = _file_bytes(cache, workspace_root, span.path)
        chunk = blob[span.start_byte : span.end_byte]
        match = _NEWCMD.search(chunk)
        if match is None:
            continue
        name = match.group(1)
        if name in used:
            found.append(
                {
                    "name": name.decode("ascii"),
                    "definition": chunk.decode("utf-8", errors="replace"),
                    "span_id": span.span_id,
                }
            )
    return found

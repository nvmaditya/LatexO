from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from latexo.plan import UserFact
from latexo.segment import SourceSpan
from latexo.snapshot import WorkspaceSnapshot, resolve_in_workspace

_DATE = re.compile(rb"\b(?:19|20)\d{2}(?:\s*--\s*(?:19|20)\d{2})?\b")
_QTY = re.compile(rb"\d+(?:\.\d+)?%|\$[\d,]+(?:\.\d+)?")
_ORG = re.compile(rb"\b([A-Z][A-Za-z0-9.&'-]+(?:[ \t]+[A-Z][A-Za-z0-9.&'-]+)+)\b")


class ResumeFact(BaseModel):
    fact_id: str
    category: str
    normalized_value: str
    original_text: str
    source: Literal["document", "user_message"]
    source_span_id: str | None
    mutable_for_this_request: bool
    revision_id: str


class FactLedger(BaseModel):
    revision_id: str
    facts: list[ResumeFact] = Field(default_factory=list)


def _file_bytes(
    cache: dict[str, bytes], workspace_root: Path, path: str
) -> bytes:
    if path not in cache:
        cache[path] = resolve_in_workspace(workspace_root, path).read_bytes()
    return cache[path]


def _smallest(spans: list[SourceSpan], path: str, start: int, end: int) -> SourceSpan | None:
    containing = [
        s
        for s in spans
        if s.path == path and s.start_byte <= start and end <= s.end_byte
    ]
    if not containing:
        return None
    return min(containing, key=lambda s: (s.end_byte - s.start_byte, s.start_byte))


def _fact_id(revision_id: str, category: str, value: str, source: str, span_id: str | None) -> str:
    payload = f"{revision_id}\n{category}\n{value}\n{source}\n{span_id or ''}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _collect(
    data: bytes,
    path: str,
    spans: list[SourceSpan],
    revision_id: str,
    pattern: re.Pattern[bytes],
    category: str,
) -> list[ResumeFact]:
    found: list[ResumeFact] = []
    for match in pattern.finditer(data):
        start, end = match.span()
        span = _smallest(spans, path, start, end)
        if span is None:
            continue
        text = match.group(0).decode("utf-8", errors="replace")
        found.append(
            ResumeFact(
                fact_id=_fact_id(revision_id, category, text.lower(), "document", span.span_id),
                category=category,
                normalized_value=text.lower(),
                original_text=text,
                source="document",
                source_span_id=span.span_id,
                mutable_for_this_request=False,
                revision_id=revision_id,
            )
        )
    return found


def build_fact_ledger(
    snapshot: WorkspaceSnapshot,
    spans: list[SourceSpan],
    workspace_root: Path,
    *,
    user_facts: list[UserFact] | None = None,
) -> FactLedger:
    live = [s for s in spans if s.revision_id == snapshot.revision_id]
    cache: dict[str, bytes] = {}
    collected: list[ResumeFact] = []
    for path in {s.path for s in live}:
        data = _file_bytes(cache, workspace_root, path)
        collected.extend(_collect(data, path, live, snapshot.revision_id, _ORG, "organization"))
        collected.extend(_collect(data, path, live, snapshot.revision_id, _DATE, "date"))
        collected.extend(_collect(data, path, live, snapshot.revision_id, _QTY, "quantity"))
    unique: dict[tuple[str, str], ResumeFact] = {}
    for fact in collected:
        key = (fact.category, fact.normalized_value)
        prior = unique.get(key)
        if prior is None:
            unique[key] = fact
            continue
        prior_span = next(s for s in live if s.span_id == prior.source_span_id)
        new_span = next(s for s in live if s.span_id == fact.source_span_id)
        if (new_span.end_byte - new_span.start_byte) < (prior_span.end_byte - prior_span.start_byte):
            unique[key] = fact
    facts = list(unique.values())
    for supplied in user_facts or []:
        facts.append(
            ResumeFact(
                fact_id=supplied.fact_id,
                category="user",
                normalized_value=supplied.text.lower(),
                original_text=supplied.text,
                source="user_message",
                source_span_id=None,
                mutable_for_this_request=True,
                revision_id=snapshot.revision_id,
            )
        )
    facts.sort(key=lambda f: (f.source, f.category, f.normalized_value, f.fact_id))
    return FactLedger(revision_id=snapshot.revision_id, facts=facts)

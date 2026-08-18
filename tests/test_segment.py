import hashlib
from pathlib import Path

from latexo.segment import segment_source
from latexo.snapshot import take_snapshot

RESUME = rb"""\documentclass{article}
\newcommand{\role}[1]{#1}
\renewcommand{\thesection}{\arabic{section}}
\begin{document}
\section{Experience}
Acme Corp built widgets.

\begin{itemize}
\item Shipped the compiler.
\item Cut latency.
\end{itemize}

\section{Education}
B.S. in CS.

A final note about availability.
\end{document}
"""

UNCLOSED_ITEMIZE = rb"""\documentclass{article}
\begin{document}
\section{Open}
\begin{itemize}
\item dangling
\section{Later}
More text after the broken list.
\end{document}
"""

UNBALANCED_BRACE = rb"""\documentclass{article}
\newcommand{\bad}{oops
\begin{document}
\section{Later}
Body text.
\end{document}
"""


def _write_resume(tmp_path: Path, data: bytes, name: str = "resume.tex") -> Path:
    path = tmp_path / name
    path.write_bytes(data)
    return path


def _by_kind(spans: list, kind: str) -> list:
    return [s for s in spans if s.kind == kind]


def test_segments_article_resume_kinds_links_and_hashes(tmp_path: Path) -> None:
    path = _write_resume(tmp_path, RESUME)
    snap = take_snapshot(tmp_path)
    spans = segment_source(snap, tmp_path)
    data = path.read_bytes()

    kinds = {s.kind for s in spans}
    assert {
        "preamble",
        "environment",
        "section",
        "list_item",
        "paragraph",
        "macro_definition",
    } <= kinds

    for span in spans:
        assert span.revision_id == snap.revision_id
        assert span.path == "resume.tex"
        assert 0 <= span.start_byte < span.end_byte <= len(data)
        assert span.text_sha256 == hashlib.sha256(
            data[span.start_byte : span.end_byte]
        ).hexdigest()
        assert span.span_id
        assert span.span_id != f"{span.start_byte}:{span.end_byte}"
        assert f"{span.start_byte}-{span.end_byte}" not in span.span_id

    again = segment_source(snap, tmp_path)
    assert [s.span_id for s in again] == [s.span_id for s in spans]
    assert [(s.start_byte, s.end_byte, s.kind) for s in again] == [
        (s.start_byte, s.end_byte, s.kind) for s in spans
    ]

    preamble = _by_kind(spans, "preamble")
    assert len(preamble) == 1
    assert b"\\documentclass{article}" in data[preamble[0].start_byte : preamble[0].end_byte]
    assert b"\\begin{document}" not in data[preamble[0].start_byte : preamble[0].end_byte]

    macros = _by_kind(spans, "macro_definition")
    assert len(macros) == 2
    assert all(m.parent_span_id == preamble[0].span_id for m in macros)
    assert set(macros[0].sibling_span_ids) == {macros[1].span_id}
    assert set(macros[1].sibling_span_ids) == {macros[0].span_id}

    envs = _by_kind(spans, "environment")
    document = next(
        e
        for e in envs
        if data[e.start_byte : e.end_byte].startswith(b"\\begin{document}")
    )
    itemize = next(
        e
        for e in envs
        if data[e.start_byte : e.end_byte].startswith(b"\\begin{itemize}")
    )

    sections = _by_kind(spans, "section")
    assert len(sections) == 2
    assert all(s.parent_span_id == document.span_id for s in sections)
    experience = next(s for s in sections if b"Experience" in data[s.start_byte : s.end_byte][:40])
    assert itemize.parent_span_id == experience.span_id
    titles = [
        data[s.start_byte : s.end_byte]
        for s in sorted(sections, key=lambda s: s.start_byte)
    ]
    assert b"Experience" in titles[0]
    assert b"Education" in titles[1]
    assert b"\\section{Education}" not in titles[0]

    items = _by_kind(spans, "list_item")
    assert len(items) == 2
    assert all(i.parent_span_id == itemize.span_id for i in items)
    assert set(items[0].sibling_span_ids) == {items[1].span_id}
    bodies = [data[i.start_byte : i.end_byte] for i in items]
    assert any(b"Shipped the compiler" in b for b in bodies)
    assert any(b"Cut latency" in b for b in bodies)

    paragraphs = _by_kind(spans, "paragraph")
    texts = [data[p.start_byte : p.end_byte] for p in paragraphs]
    assert any(b"Acme Corp built widgets" in t for t in texts)
    assert any(b"B.S. in CS" in t for t in texts)
    assert any(b"A final note about availability" in t for t in texts)


def test_mutation_invalidates_prior_span_identity(tmp_path: Path) -> None:
    path = _write_resume(tmp_path, RESUME)
    snap = take_snapshot(tmp_path)
    spans = segment_source(snap, tmp_path)
    target = next(s for s in spans if s.kind == "section")
    old_id = target.span_id
    old_hash = target.text_sha256
    old_start = target.start_byte

    blob = bytearray(path.read_bytes())
    needle = blob.find(b"Experience")
    assert needle != -1
    blob[needle] = ord(b"A")
    path.write_bytes(blob)

    new_snap = take_snapshot(tmp_path)
    new_spans = segment_source(new_snap, tmp_path)
    assert old_id not in {s.span_id for s in new_spans}
    at_same = [
        s for s in new_spans if s.kind == "section" and s.start_byte == old_start
    ]
    assert at_same
    assert at_same[0].text_sha256 != old_hash
    assert at_same[0].revision_id == new_snap.revision_id
    assert at_same[0].revision_id != snap.revision_id


def test_unclosed_environment_does_not_swallow_later_text(tmp_path: Path) -> None:
    path = _write_resume(tmp_path, UNCLOSED_ITEMIZE)
    snap = take_snapshot(tmp_path)
    spans = segment_source(snap, tmp_path)
    data = path.read_bytes()
    begin = data.find(b"\\begin{itemize}")
    later = data.find(b"\\section{Later}")
    assert begin != -1 and later != -1
    for span in spans:
        if span.kind != "environment":
            continue
        if not (span.start_byte <= begin < span.end_byte):
            continue
        body = data[span.start_byte : span.end_byte]
        if body.startswith(b"\\begin{itemize}"):
            assert later < span.start_byte or later >= span.end_byte


def test_unbalanced_brace_does_not_eat_later_section(tmp_path: Path) -> None:
    path = _write_resume(tmp_path, UNBALANCED_BRACE)
    snap = take_snapshot(tmp_path)
    spans = segment_source(snap, tmp_path)
    data = path.read_bytes()
    later = data.find(b"\\section{Later}")
    assert later != -1
    for span in _by_kind(spans, "macro_definition"):
        assert later < span.start_byte or later >= span.end_byte

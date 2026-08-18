from pathlib import Path

from latexo.locate import locate_targets
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

DUAL = rb"""\documentclass{article}
\begin{document}
\section{Alpha}
SharedWord in the first block.

\section{Beta}
SharedWord in the second block.
\end{document}
"""


def _prep(tmp_path: Path, data: bytes):
    path = tmp_path / "resume.tex"
    path.write_bytes(data)
    snap = take_snapshot(tmp_path)
    spans = segment_source(snap, tmp_path)
    return path, snap, spans, data


def test_selection_inside_list_item_is_unique_single_target(tmp_path: Path) -> None:
    _path, snap, spans, data = _prep(tmp_path, RESUME)
    item = next(
        s
        for s in spans
        if s.kind == "list_item"
        and b"Shipped the compiler" in data[s.start_byte : s.end_byte]
    )
    result = locate_targets(
        snap,
        spans,
        workspace_root=tmp_path,
        active_file="resume.tex",
        selection={"start_byte": item.start_byte + 6, "end_byte": item.start_byte + 14},
    )
    assert result.requires_clarification is False
    assert result.targeting_mode == "single"
    assert len(result.targets) == 1
    assert result.targets[0].span_id == item.span_id
    assert result.targets[0].confidence >= 0.9
    located = next(s for s in spans if s.span_id == result.targets[0].span_id)
    assert located.revision_id == snap.revision_id
    assert result.targets[0].span_id in {s.span_id for s in spans}


def test_quoted_heading_locates_unique_section(tmp_path: Path) -> None:
    _path, snap, spans, data = _prep(tmp_path, RESUME)
    section = next(
        s
        for s in spans
        if s.kind == "section" and b"\\section{Experience}" in data[s.start_byte : s.end_byte]
    )
    result = locate_targets(
        snap,
        spans,
        workspace_root=tmp_path,
        request='Tighten the "Experience" section',
    )
    assert result.requires_clarification is False
    assert result.targeting_mode == "single"
    assert [t.span_id for t in result.targets] == [section.span_id]
    assert {t.span_id for t in result.targets} <= {s.span_id for s in spans}


def test_ambiguous_repeated_text_requires_clarification(tmp_path: Path) -> None:
    _path, snap, spans, data = _prep(tmp_path, DUAL)
    result = locate_targets(snap, spans, workspace_root=tmp_path, request="SharedWord")
    assert result.requires_clarification is True
    assert result.targeting_mode != "single"
    assert len(result.targets) != 1
    ids = {t.span_id for t in result.targets}
    assert ids <= {s.span_id for s in spans}
    for target in result.targets:
        assert target.span_id not in {str(s.start_byte) for s in spans}


def test_cursor_inside_section_heading_selects_that_section(tmp_path: Path) -> None:
    _path, snap, spans, data = _prep(tmp_path, RESUME)
    section = next(
        s
        for s in spans
        if s.kind == "section" and b"\\section{Education}" in data[s.start_byte : s.end_byte]
    )
    heading_at = data.find(b"Education")
    assert section.start_byte <= heading_at < section.end_byte
    result = locate_targets(
        snap,
        spans,
        workspace_root=tmp_path,
        active_file="resume.tex",
        selection={"cursor_byte": heading_at + 1},
    )
    assert result.requires_clarification is False
    assert result.targeting_mode == "single"
    assert result.targets[0].span_id == section.span_id


def test_location_never_returns_unknown_or_line_number_ids(tmp_path: Path) -> None:
    _path, snap, spans, _data = _prep(tmp_path, RESUME)
    result = locate_targets(snap, spans, workspace_root=tmp_path, request="Education")
    known = {s.span_id for s in spans}
    for target in result.targets:
        assert target.span_id in known
        assert ":" not in target.span_id
        assert not target.span_id.isdigit()

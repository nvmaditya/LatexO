from pathlib import Path

from latexo.section import SectionEdit, apply_sections
from latexo.segment import segment_source
from latexo.snapshot import take_snapshot

RESUME = rb"""\documentclass{article}
\begin{document}
\section{Experience}
Acme Corp.

\section{Education}
B.S. in CS.
\end{document}
"""


def _prep(tmp_path: Path):
    live = tmp_path / "live"
    stage = tmp_path / "stage"
    live.mkdir()
    path = live / "resume.tex"
    path.write_bytes(RESUME)
    snap = take_snapshot(live)
    spans = segment_source(snap, live)
    return live, stage, path, snap, spans


def _section(spans, data: bytes, title: bytes):
    return next(
        s
        for s in spans
        if s.kind == "section" and title in data[s.start_byte : s.end_byte]
    )


def test_section_replace_stages_and_leaves_live(tmp_path: Path) -> None:
    live, stage, path, snap, spans = _prep(tmp_path)
    data = path.read_bytes()
    exp = _section(spans, data, b"Experience")
    result = apply_sections(
        snap,
        spans,
        live,
        stage,
        [SectionEdit(action="replace", span_id=exp.span_id, replacement="\\section{Experience}\nNewCo.\n")],
    )
    assert result.ok is True
    assert path.read_bytes() == RESUME
    staged = (stage / "resume.tex").read_bytes()
    assert b"NewCo" in staged
    assert b"Acme Corp" not in staged


def test_section_delete_and_reorder(tmp_path: Path) -> None:
    live, stage, path, snap, spans = _prep(tmp_path)
    data = path.read_bytes()
    edu = _section(spans, data, b"Education")
    deleted = apply_sections(
        snap, spans, live, stage, [SectionEdit(action="delete", span_id=edu.span_id)]
    )
    assert deleted.ok is True
    assert path.read_bytes() == RESUME
    assert b"Education" not in (stage / "resume.tex").read_bytes()

    stage2 = tmp_path / "stage2"
    exp = _section(spans, data, b"Experience")
    reordered = apply_sections(
        snap,
        spans,
        live,
        stage2,
        [SectionEdit(action="reorder", span_id=exp.span_id, swap_with=edu.span_id)],
    )
    assert reordered.ok is True
    assert path.read_bytes() == RESUME
    text = (stage2 / "resume.tex").read_bytes()
    assert text.find(b"Education") < text.find(b"Experience")


def test_section_overlap_fails_closed(tmp_path: Path) -> None:
    live, stage, path, snap, spans = _prep(tmp_path)
    data = path.read_bytes()
    exp = _section(spans, data, b"Experience")
    para = next(
        s
        for s in spans
        if s.kind == "paragraph" and b"Acme" in data[s.start_byte : s.end_byte]
    )
    result = apply_sections(
        snap,
        spans,
        live,
        stage,
        [
            SectionEdit(action="replace", span_id=exp.span_id, replacement="\\section{X}\n"),
            SectionEdit(action="replace", span_id=para.span_id, replacement="Y\n"),
        ],
    )
    assert result.ok is False
    assert path.read_bytes() == RESUME
    assert not (stage / "resume.tex").exists()

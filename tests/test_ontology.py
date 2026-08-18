from pathlib import Path

from latexo.ontology import label_spans, lookup_macros
from latexo.segment import segment_source
from latexo.snapshot import take_snapshot

RESUME = rb"""\documentclass{article}
\newcommand{\role}[1]{#1}
\begin{document}
\section{Experience}
\role{Engineer} at Acme.

\section{Education}
B.S. in CS.
\end{document}
"""


def test_labels_existing_spans_and_retrieves_macros(tmp_path: Path) -> None:
    path = tmp_path / "resume.tex"
    path.write_bytes(RESUME)
    snap = take_snapshot(tmp_path)
    spans = segment_source(snap, tmp_path)
    known = {s.span_id for s in spans}
    labeled = label_spans(spans, tmp_path)
    assert {s.span_id for s in labeled} <= known
    labels = {s.semantic_label for s in labeled if s.semantic_label}
    assert "work_experience" in labels or "experience" in labels
    assert "education" in labels
    data = path.read_bytes()
    body = next(
        s
        for s in labeled
        if s.kind == "section" and b"Experience" in data[s.start_byte : s.end_byte]
    )
    macros = lookup_macros(spans, tmp_path, body.span_id)
    assert macros
    hit = next(m for m in macros if m["name"] == "role")
    assert hit["span_id"] in known
    home = next(s for s in spans if s.span_id == hit["span_id"])
    assert b"\\newcommand{\\role}" in data[home.start_byte : home.end_byte]
    assert "\\newcommand{\\role}" in hit["definition"] or "\\role" in hit["definition"]

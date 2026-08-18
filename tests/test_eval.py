from pathlib import Path

from latexo.includes import build_include_map
from latexo.ontology import label_spans
from latexo.segment import segment_source
from latexo.snapshot import take_snapshot

MAIN = rb"""\documentclass{article}
\newcommand{\role}[1]{#1}
\input{chap}
\begin{document}
\section{Experience}
\role{Engineer}
\end{document}
"""

CHAP = rb"""\section{Education}
B.S.
"""


def test_eval_multifile_custom_macro_fixture(tmp_path: Path) -> None:
    (tmp_path / "main.tex").write_bytes(MAIN)
    (tmp_path / "chap.tex").write_bytes(CHAP)
    snap = take_snapshot(tmp_path)
    spans = segment_source(snap, tmp_path)
    mapped = build_include_map(snap, tmp_path)
    assert any(
        e.source == "main.tex" and e.target == "chap.tex" and e.status == "resolved"
        for e in mapped.edges
    )
    labeled = label_spans(spans, tmp_path)
    labels = {s.semantic_label for s in labeled if s.semantic_label}
    assert "experience" in labels
    assert "education" in labels
    assert any(s.kind == "macro_definition" for s in spans)

from pathlib import Path

from latexo.root import resolve_root
from latexo.snapshot import take_snapshot

UNIQUE = rb"""
\documentclass{article}
\begin{document}
Hi
\end{document}
"""

CHAPTER = rb"""
\section{Only a chapter}
"""


def test_unique_documentclass_and_body_is_the_root(tmp_path: Path) -> None:
    (tmp_path / "cv.tex").write_bytes(UNIQUE)
    (tmp_path / "chap.tex").write_bytes(CHAPTER)
    snap = take_snapshot(tmp_path)
    result = resolve_root(snap, tmp_path)
    assert result.root_path == "cv.tex"
    assert result.candidates == ["cv.tex"]
    assert result.requires_clarification is False


def test_multiple_roots_require_clarification(tmp_path: Path) -> None:
    (tmp_path / "a.tex").write_bytes(UNIQUE)
    (tmp_path / "b.tex").write_bytes(UNIQUE)
    snap = take_snapshot(tmp_path)
    result = resolve_root(snap, tmp_path)
    assert result.root_path is None
    assert result.candidates == ["a.tex", "b.tex"]
    assert result.requires_clarification is True


def test_no_root_requires_clarification(tmp_path: Path) -> None:
    (tmp_path / "only.tex").write_bytes(CHAPTER)
    snap = take_snapshot(tmp_path)
    result = resolve_root(snap, tmp_path)
    assert result.root_path is None
    assert result.candidates == []
    assert result.requires_clarification is True

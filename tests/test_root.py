from pathlib import Path

import pytest

from latexo.root import resolve_root
from latexo.snapshot import UnsafePathError, take_snapshot

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


def test_explicit_root_wins_over_multiple_candidates(tmp_path: Path) -> None:
    (tmp_path / "a.tex").write_bytes(UNIQUE)
    (tmp_path / "b.tex").write_bytes(UNIQUE)
    snap = take_snapshot(tmp_path)
    result = resolve_root(snap, tmp_path, explicit_root="b.tex")
    assert result.root_path == "b.tex"
    assert result.requires_clarification is False
    assert result.candidates == ["b.tex"]


def test_confirmed_root_used_when_no_explicit(tmp_path: Path) -> None:
    (tmp_path / "a.tex").write_bytes(UNIQUE)
    (tmp_path / "b.tex").write_bytes(UNIQUE)
    snap = take_snapshot(tmp_path)
    result = resolve_root(snap, tmp_path, confirmed_root="a.tex")
    assert result.root_path == "a.tex"
    assert result.requires_clarification is False


def test_explicit_root_outside_workspace_is_rejected(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    (workspace / "cv.tex").write_bytes(UNIQUE)
    snap = take_snapshot(workspace)
    with pytest.raises(UnsafePathError):
        resolve_root(snap, workspace, explicit_root="../cv.tex")

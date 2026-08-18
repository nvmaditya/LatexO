from pathlib import Path

from latexo.includes import build_include_map
from latexo.root import resolve_root
from latexo.snapshot import take_snapshot

ROOT = rb"""\documentclass{article}
\input{chap}
\begin{document}
Hi
\end{document}
"""

INCLUDE_ROOT = rb"""\documentclass{article}
\include{chap}
\begin{document}
Hi
\end{document}
"""

CHAP = rb"""\section{Chapter}
Body.
"""

CHAP_ROOT = rb"""\documentclass{article}
\begin{document}
Chapter body.
\end{document}
"""

COMMENTED = rb"""\documentclass{article}
% \input{chap}
\begin{document}
Hi
\end{document}
"""


def test_input_and_include_create_snapshot_edges(tmp_path: Path) -> None:
    (tmp_path / "main.tex").write_bytes(ROOT)
    (tmp_path / "chap.tex").write_bytes(CHAP)
    snap = take_snapshot(tmp_path)
    mapped = build_include_map(snap, tmp_path)
    resolved = [(e.source, e.target) for e in mapped.edges if e.status == "resolved"]
    assert ("main.tex", "chap.tex") in resolved
    paths = {f.path for f in snap.files}
    for src, dst in resolved:
        assert src in paths
        assert dst in paths

    (tmp_path / "main.tex").write_bytes(INCLUDE_ROOT)
    snap = take_snapshot(tmp_path)
    mapped = build_include_map(snap, tmp_path)
    resolved = [(e.source, e.target) for e in mapped.edges if e.status == "resolved"]
    assert ("main.tex", "chap.tex") in resolved


def test_commented_input_is_not_an_edge(tmp_path: Path) -> None:
    (tmp_path / "main.tex").write_bytes(COMMENTED)
    (tmp_path / "chap.tex").write_bytes(CHAP)
    snap = take_snapshot(tmp_path)
    mapped = build_include_map(snap, tmp_path)
    resolved = [(e.source, e.target) for e in mapped.edges if e.status == "resolved"]
    assert ("main.tex", "chap.tex") not in resolved


def test_escaped_include_is_not_an_in_workspace_edge(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    ws.mkdir()
    (tmp_path / "outside.tex").write_bytes(CHAP)
    (ws / "main.tex").write_bytes(
        rb"""\documentclass{article}
\input{../outside}
\begin{document}
Hi
\end{document}
"""
    )
    snap = take_snapshot(ws)
    mapped = build_include_map(snap, ws)
    resolved = [e for e in mapped.edges if e.status == "resolved"]
    assert not any("outside" in e.target for e in resolved)
    escaped = [e for e in mapped.edges if e.status == "escaped"]
    assert escaped


def test_missing_include_is_unresolved(tmp_path: Path) -> None:
    (tmp_path / "main.tex").write_bytes(
        rb"""\documentclass{article}
\input{missing}
\begin{document}
Hi
\end{document}
"""
    )
    snap = take_snapshot(tmp_path)
    mapped = build_include_map(snap, tmp_path)
    unresolved = [e for e in mapped.edges if e.status == "unresolved"]
    assert unresolved
    assert all(e.status != "resolved" or e.target != "missing.tex" for e in mapped.edges)


def test_include_graph_picks_unique_including_root(tmp_path: Path) -> None:
    (tmp_path / "main.tex").write_bytes(ROOT.replace(b"\\input{chap}", b"\\input{chap}"))
    (tmp_path / "chap.tex").write_bytes(CHAP_ROOT)
    snap = take_snapshot(tmp_path, active_file="chap.tex")
    result = resolve_root(snap, tmp_path, active_file="chap.tex")
    assert result.requires_clarification is False
    assert result.root_path == "main.tex"


def test_two_unrelated_compilable_files_still_need_clarification(tmp_path: Path) -> None:
    (tmp_path / "a.tex").write_bytes(CHAP_ROOT)
    (tmp_path / "b.tex").write_bytes(CHAP_ROOT)
    snap = take_snapshot(tmp_path)
    result = resolve_root(snap, tmp_path)
    assert result.requires_clarification is True
    assert result.root_path is None


def test_active_file_alone_does_not_break_a_true_tie(tmp_path: Path) -> None:
    (tmp_path / "a.tex").write_bytes(CHAP_ROOT)
    (tmp_path / "b.tex").write_bytes(CHAP_ROOT)
    snap = take_snapshot(tmp_path, active_file="a.tex")
    result = resolve_root(snap, tmp_path)
    assert result.requires_clarification is True
    assert result.root_path is None
    via_kwarg = resolve_root(snap, tmp_path, active_file="b.tex")
    assert via_kwarg.requires_clarification is True
    assert via_kwarg.root_path is None

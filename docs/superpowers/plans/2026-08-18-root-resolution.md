# Root Resolution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Pick the compilation root from a snapshot using the spec order, and ask for clarification instead of guessing when more than one root is plausible.

**Architecture:** `latexo.root.resolve_root` reads already-snapshotted `.tex` files through `resolve_in_workspace`. It does not compile. Include-graph ranking and compilation probes are out of scope (Phase 1.2 ceiling).

**Tech Stack:** Same as 1.1. Stdlib `re` for `\\documentclass` and `\\begin{document}`.

## Global Constraints

- Binding spec: `specs.md` §5.2.
- Order: explicit user/editor root, then previously confirmed root, then unique source containing `\documentclass` and a document body, then clarification.
- Several plausible roots → `requires_clarification=True` and `root_path=None`. Never pick the first match.
- Paths that escape the workspace raise `UnsafePathError`.
- No TeX execution. No new dependencies.

## File structure

- Create: `latexo/root.py`
- Modify: `latexo/__init__.py`
- Test: `tests/test_root.py`

---

### Task 1: Unique documentclass+body, else clarify

**Files:**
- Create: `latexo/root.py`
- Modify: `latexo/__init__.py`
- Test: `tests/test_root.py`

**Interfaces:**
- Consumes: `take_snapshot(workspace_root: Path, *, active_file: str | None = None, selection: dict | None = None) -> WorkspaceSnapshot`
- Produces:
  - `class RootResolution(BaseModel)` with `root_path: str | None`, `candidates: list[str]`, `requires_clarification: bool`, `reason: str`
  - `def resolve_root(snapshot: WorkspaceSnapshot, workspace_root: Path, *, explicit_root: str | None = None, confirmed_root: str | None = None) -> RootResolution`
  - A candidate is a snapshot `.tex` file whose bytes contain `\documentclass` (optional `[...]` then `{`) and `\begin{document}` (whitespace inside the braces allowed).
  - Zero candidates: `root_path=None`, `requires_clarification=True`, `candidates=[]`.
  - One candidate: `root_path` is that POSIX path, `requires_clarification=False`, `candidates` is that one path.
  - Two or more: `root_path=None`, `requires_clarification=True`, `candidates` sorted.

- [ ] **Step 1: Write the failing test**

Create `tests/test_root.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_root.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'latexo.root'` or import error for `resolve_root`.

- [ ] **Step 3: Write minimal implementation**

Create `latexo/root.py`:

```python
from __future__ import annotations

import re
from pathlib import Path

from pydantic import BaseModel

from latexo.snapshot import WorkspaceSnapshot, resolve_in_workspace

_DOCUMENTCLASS = re.compile(rb"\\documentclass(?:\s*\[[^\]]*\])?\s*\{")
_BEGIN_DOCUMENT = re.compile(rb"\\begin\s*\{\s*document\s*\}")


class RootResolution(BaseModel):
    root_path: str | None
    candidates: list[str]
    requires_clarification: bool
    reason: str


def _is_compilable_root(data: bytes) -> bool:
    return bool(_DOCUMENTCLASS.search(data) and _BEGIN_DOCUMENT.search(data))


def _scan_candidates(snapshot: WorkspaceSnapshot, workspace_root: Path) -> list[str]:
    found: list[str] = []
    for record in snapshot.files:
        if not record.path.lower().endswith(".tex"):
            continue
        path = resolve_in_workspace(workspace_root, record.path)
        if _is_compilable_root(path.read_bytes()):
            found.append(record.path)
    found.sort()
    return found


def resolve_root(
    snapshot: WorkspaceSnapshot,
    workspace_root: Path,
    *,
    explicit_root: str | None = None,
    confirmed_root: str | None = None,
) -> RootResolution:
    del explicit_root, confirmed_root
    candidates = _scan_candidates(snapshot, workspace_root)
    if len(candidates) == 1:
        return RootResolution(
            root_path=candidates[0],
            candidates=candidates,
            requires_clarification=False,
            reason="unique documentclass and document body",
        )
    if not candidates:
        return RootResolution(
            root_path=None,
            candidates=[],
            requires_clarification=True,
            reason="no source with documentclass and document body",
        )
    return RootResolution(
        root_path=None,
        candidates=candidates,
        requires_clarification=True,
        reason="multiple plausible compilation roots",
    )
```

Update `latexo/__init__.py` to also export `RootResolution` and `resolve_root`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_root.py tests/test_snapshot.py -v`

Expected: PASS (snapshot symlink test may SKIP).

- [ ] **Step 5: Commit**

```bash
git add latexo/root.py latexo/__init__.py tests/test_root.py
git commit -m "feat: resolve unique compilation root or ask"
```

---

### Task 2: Explicit and confirmed roots win; unsafe paths fail

**Files:**
- Modify: `latexo/root.py`
- Test: `tests/test_root.py`

**Interfaces:**
- Consumes: `resolve_root` from Task 1; `resolve_in_workspace`; `UnsafePathError`.
- Produces: same signature. `explicit_root` if provided is resolved in the workspace and used as `root_path` even when other documentclass files exist. `confirmed_root` is used only when `explicit_root` is None, and only if that file still exists. Either override that escapes the workspace raises `UnsafePathError`. A missing explicit/confirmed file is treated as not provided (fall through to scan), except escape still raises.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_root.py`:

```python
import pytest

from latexo.snapshot import UnsafePathError


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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_root.py::test_explicit_root_wins_over_multiple_candidates tests/test_root.py::test_confirmed_root_used_when_no_explicit tests/test_root.py::test_explicit_root_outside_workspace_is_rejected -v`

Expected: FAIL — explicit/confirmed currently ignored (`del` in Task 1), so multiple-candidate case returns `root_path is None`.

- [ ] **Step 3: Write minimal implementation**

Replace `resolve_root` in `latexo/root.py` with:

```python
def _existing_override(workspace_root: Path, candidate: str) -> str | None:
    path = resolve_in_workspace(workspace_root, candidate)
    if not path.is_file():
        return None
    return path.relative_to(workspace_root.resolve()).as_posix()


def resolve_root(
    snapshot: WorkspaceSnapshot,
    workspace_root: Path,
    *,
    explicit_root: str | None = None,
    confirmed_root: str | None = None,
) -> RootResolution:
    for value, reason in (
        (explicit_root, "explicitly selected"),
        (confirmed_root, "previously confirmed"),
    ):
        if value is None:
            continue
        chosen = _existing_override(workspace_root, value)
        if chosen is None:
            continue
        return RootResolution(
            root_path=chosen,
            candidates=[chosen],
            requires_clarification=False,
            reason=reason,
        )
    candidates = _scan_candidates(snapshot, workspace_root)
    if len(candidates) == 1:
        return RootResolution(
            root_path=candidates[0],
            candidates=candidates,
            requires_clarification=False,
            reason="unique documentclass and document body",
        )
    if not candidates:
        return RootResolution(
            root_path=None,
            candidates=[],
            requires_clarification=True,
            reason="no source with documentclass and document body",
        )
    return RootResolution(
        root_path=None,
        candidates=candidates,
        requires_clarification=True,
        reason="multiple plausible compilation roots",
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_root.py tests/test_snapshot.py -v`

Expected: all PASS except optional symlink skip.

- [ ] **Step 5: Commit**

```bash
git add latexo/root.py tests/test_root.py
git commit -m "feat: honor explicit and confirmed compilation roots"
```

---

## Self-review

**Spec §5.2:** steps 1, 2, 4, 6 covered. Step 3 (root declaration tied to active file) and step 5 (include ranking / compile probes) deferred — no persistence format and no compiler yet.

**Placeholder scan:** none.

**Type consistency:** `resolve_root(snapshot, workspace_root, *, explicit_root=None, confirmed_root=None) -> RootResolution` unchanged across tasks.

# Workspace Snapshot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Status:** Complete on `feat/workspace-snapshot` (2026-08-18). Symlink-escape test skips when the host cannot create symlinks.

**Goal:** Take a revision-scoped snapshot of a LaTeX workspace: editable source files with SHA-256 hashes, a deterministic revision id, editor context, and fail-closed path safety.

**Architecture:** One deep module `latexo.snapshot`. Callers use `take_snapshot(workspace_root, *, active_file=None, selection=None) -> WorkspaceSnapshot`. Enumeration, hashing, generated-artifact exclusion, and path policy stay inside the module. Paths stored in the snapshot are POSIX-relative to the workspace root.

**Tech Stack:** Python 3.12+, Pydantic v2, pytest, stdlib `hashlib` / `pathlib` / `mimetypes`. No LangGraph, no compiler, no LLM.

## Global Constraints

- Binding spec: `specs.md` §5.1 (workspace snapshot) and §13 items 5 (path normalization and symbolic-link checks).
- `FileRecord` fields: `path`, `sha256`, `size_bytes`, `media_type`, `is_generated`.
- `WorkspaceSnapshot` fields: `revision_id`, `files`, `active_file`, `selection`, `created_at`.
- Normalized relative paths (POSIX separators, no leading `./`).
- SHA-256 of file bytes for each record.
- Generated compiler artifacts are excluded from edit scope (not listed as editable files).
- Paths that escape the workspace or resolve through unsafe symbolic links are rejected.
- `span_id` / patches / LangGraph are out of scope for this plan.
- Models never author offsets; this plan does not expose byte offsets.
- Windows-compatible: tests that create symlinks must skip if the OS refuses.
- Fewest files: `latexo/snapshot.py`, `latexo/__init__.py`, `tests/test_snapshot.py`, `pyproject.toml`.

## File structure

- `pyproject.toml` — package metadata, pydantic, pytest, `pythonpath`.
- `latexo/__init__.py` — re-export public types and `take_snapshot`.
- `latexo/snapshot.py` — models, path policy, `take_snapshot`.
- `tests/test_snapshot.py` — all slice 1.1 tests.
- `.gitignore` — `__pycache__/`, `.pytest_cache/`, `*.egg-info/`, `.venv/`.

---

### Task 1: Snapshot core

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `latexo/__init__.py`
- Create: `latexo/snapshot.py`
- Test: `tests/test_snapshot.py`

**Interfaces:**
- Consumes: nothing (greenfield).
- Produces:
  - `class FileRecord(BaseModel)` with `path: str`, `sha256: str`, `size_bytes: int`, `media_type: str`, `is_generated: bool`
  - `class WorkspaceSnapshot(BaseModel)` with `revision_id: str`, `files: list[FileRecord]`, `active_file: str | None`, `selection: dict | None`, `created_at: str`
  - `def take_snapshot(workspace_root: Path, *, active_file: str | None = None, selection: dict | None = None) -> WorkspaceSnapshot`
  - `revision_id` = SHA-256 hex of UTF-8 text `"{path}\t{sha256}\n"` for every included file, sorted by `path`.
  - `created_at` = UTC ISO-8601 ending in `Z`.
  - `files` sorted by `path`.
  - Only files whose suffix is in `{.tex, .sty, .cls, .clo, .bib, .bst, .ltx}` (case-insensitive) are included in this task. Nested directories are walked.

- [ ] **Step 1: Write the failing test**

Create `tests/test_snapshot.py`:

```python
import hashlib
from pathlib import Path

from latexo.snapshot import take_snapshot


def test_snapshot_lists_hashed_tex_files(tmp_path: Path) -> None:
    (tmp_path / "nested").mkdir()
    resume_bytes = b"\\documentclass{article}\n"
    (tmp_path / "resume.tex").write_bytes(resume_bytes)
    (tmp_path / "nested" / "extra.tex").write_bytes(b"% extra\n")
    (tmp_path / "notes.txt").write_bytes(b"not source\n")

    snap = take_snapshot(tmp_path)

    paths = [f.path for f in snap.files]
    assert paths == ["nested/extra.tex", "resume.tex"]
    resume = snap.files[1]
    assert resume.size_bytes == len(resume_bytes)
    assert resume.sha256 == hashlib.sha256(resume_bytes).hexdigest()
    assert resume.is_generated is False
    assert resume.media_type
    assert snap.active_file is None
    assert snap.selection is None
    assert snap.created_at.endswith("Z")
    assert len(snap.revision_id) == 64
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_snapshot.py::test_snapshot_lists_hashed_tex_files -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'latexo'` (or collection error for the same reason).

- [ ] **Step 3: Write minimal implementation**

Create `.gitignore`:

```
__pycache__/
.pytest_cache/
*.egg-info/
.venv/
```

Create `pyproject.toml`:

```toml
[project]
name = "latexo"
version = "0.1.0"
description = "LaTeX resume patch editor"
requires-python = ">=3.12"
dependencies = ["pydantic>=2.0"]

[project.optional-dependencies]
dev = ["pytest>=8.0"]

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
include = ["latexo*"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
```

Create `latexo/snapshot.py`:

```python
from __future__ import annotations

import hashlib
import mimetypes
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, Field

SOURCE_SUFFIXES = {".tex", ".sty", ".cls", ".clo", ".bib", ".bst", ".ltx"}


class FileRecord(BaseModel):
    path: str
    sha256: str
    size_bytes: int
    media_type: str
    is_generated: bool


class WorkspaceSnapshot(BaseModel):
    revision_id: str
    files: list[FileRecord]
    active_file: str | None = None
    selection: dict | None = None
    created_at: str = Field(min_length=1)


def _posix_rel(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def _file_record(root: Path, path: Path) -> FileRecord:
    data = path.read_bytes()
    media, _ = mimetypes.guess_type(path.name)
    return FileRecord(
        path=_posix_rel(root, path),
        sha256=hashlib.sha256(data).hexdigest(),
        size_bytes=len(data),
        media_type=media or "text/plain",
        is_generated=False,
    )


def _revision_id(files: list[FileRecord]) -> str:
    payload = "".join(f"{f.path}\t{f.sha256}\n" for f in files)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def take_snapshot(
    workspace_root: Path,
    *,
    active_file: str | None = None,
    selection: dict | None = None,
) -> WorkspaceSnapshot:
    root = workspace_root.resolve()
    records: list[FileRecord] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix.lower() not in SOURCE_SUFFIXES:
            continue
        records.append(_file_record(root, path))
    records.sort(key=lambda f: f.path)
    return WorkspaceSnapshot(
        revision_id=_revision_id(records),
        files=records,
        active_file=active_file,
        selection=selection,
        created_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    )
```

Create `latexo/__init__.py`:

```python
from latexo.snapshot import FileRecord, WorkspaceSnapshot, take_snapshot

__all__ = ["FileRecord", "WorkspaceSnapshot", "take_snapshot"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_snapshot.py::test_snapshot_lists_hashed_tex_files -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml .gitignore latexo/__init__.py latexo/snapshot.py tests/test_snapshot.py
git commit -m "feat: snapshot editable LaTeX sources with revision id"
```

---

### Task 2: Exclude generated artifacts and ignored directories

**Files:**
- Modify: `latexo/snapshot.py`
- Test: `tests/test_snapshot.py`

**Interfaces:**
- Consumes: `take_snapshot` from Task 1.
- Produces: same function. Walk skips directory names `{.git, __pycache__, .pytest_cache, out, build}` and any name starting with `_minted`. Files whose names end with generated suffixes are not included even if they somehow match a source suffix. A `.tex` file next to compiler junk is still included.

Generated name suffixes (case-insensitive): `.aux`, `.log`, `.out`, `.toc`, `.lof`, `.lot`, `.fls`, `.fdb_latexmk`, `.synctex.gz`, `.bbl`, `.blg`, `.nav`, `.snm`, `.vrb`, `.bcf`, `.run.xml`.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_snapshot.py`:

```python
def test_snapshot_excludes_generated_and_ignored_dirs(tmp_path: Path) -> None:
    (tmp_path / "resume.tex").write_text("% root\n", encoding="utf-8")
    (tmp_path / "resume.aux").write_text("aux\n", encoding="utf-8")
    (tmp_path / "resume.fdb_latexmk").write_text("fdb\n", encoding="utf-8")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "hidden.tex").write_text("% no\n", encoding="utf-8")
    minted = tmp_path / "_minted-resume"
    minted.mkdir()
    (minted / "frag.tex").write_text("% no\n", encoding="utf-8")
    build = tmp_path / "build"
    build.mkdir()
    (build / "out.tex").write_text("% no\n", encoding="utf-8")

    snap = take_snapshot(tmp_path)

    assert [f.path for f in snap.files] == ["resume.tex"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_snapshot.py::test_snapshot_excludes_generated_and_ignored_dirs -v`

Expected: FAIL — assertion on paths, because `.git/hidden.tex`, `_minted-resume/frag.tex`, and/or `build/out.tex` are included.

- [ ] **Step 3: Write minimal implementation**

Replace `latexo/snapshot.py` walk logic. Full file after this task:

```python
from __future__ import annotations

import hashlib
import mimetypes
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, Field

SOURCE_SUFFIXES = {".tex", ".sty", ".cls", ".clo", ".bib", ".bst", ".ltx"}
IGNORED_DIR_NAMES = {".git", "__pycache__", ".pytest_cache", "out", "build"}
GENERATED_SUFFIXES = (
    ".synctex.gz",
    ".fdb_latexmk",
    ".run.xml",
    ".aux",
    ".log",
    ".out",
    ".toc",
    ".lof",
    ".lot",
    ".fls",
    ".bbl",
    ".blg",
    ".nav",
    ".snm",
    ".vrb",
    ".bcf",
)


class FileRecord(BaseModel):
    path: str
    sha256: str
    size_bytes: int
    media_type: str
    is_generated: bool


class WorkspaceSnapshot(BaseModel):
    revision_id: str
    files: list[FileRecord]
    active_file: str | None = None
    selection: dict | None = None
    created_at: str = Field(min_length=1)


def _posix_rel(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def _file_record(root: Path, path: Path) -> FileRecord:
    data = path.read_bytes()
    media, _ = mimetypes.guess_type(path.name)
    return FileRecord(
        path=_posix_rel(root, path),
        sha256=hashlib.sha256(data).hexdigest(),
        size_bytes=len(data),
        media_type=media or "text/plain",
        is_generated=False,
    )


def _revision_id(files: list[FileRecord]) -> str:
    payload = "".join(f"{f.path}\t{f.sha256}\n" for f in files)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _is_generated_name(name: str) -> bool:
    lower = name.lower()
    return any(lower.endswith(suffix) for suffix in GENERATED_SUFFIXES)


def _should_ignore_dir(name: str) -> bool:
    return name in IGNORED_DIR_NAMES or name.startswith("_minted")


def take_snapshot(
    workspace_root: Path,
    *,
    active_file: str | None = None,
    selection: dict | None = None,
) -> WorkspaceSnapshot:
    root = workspace_root.resolve()
    records: list[FileRecord] = []
    for dirpath, dirnames, filenames in root.walk():
        dirnames[:] = [d for d in dirnames if not _should_ignore_dir(d)]
        for name in filenames:
            if _is_generated_name(name):
                continue
            path = dirpath / name
            if not path.is_file():
                continue
            if path.suffix.lower() not in SOURCE_SUFFIXES:
                continue
            records.append(_file_record(root, path))
    records.sort(key=lambda f: f.path)
    return WorkspaceSnapshot(
        revision_id=_revision_id(records),
        files=records,
        active_file=active_file,
        selection=selection,
        created_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    )
```

Note: `Path.walk` requires Python 3.12, which is the package floor.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_snapshot.py -v`

Expected: both tests PASS

- [ ] **Step 5: Commit**

```bash
git add latexo/snapshot.py tests/test_snapshot.py
git commit -m "feat: exclude generated LaTeX artifacts from snapshots"
```

---

### Task 3: Path safety and editor context

**Files:**
- Modify: `latexo/snapshot.py`
- Modify: `latexo/__init__.py`
- Test: `tests/test_snapshot.py`

**Interfaces:**
- Consumes: `take_snapshot` from Task 2.
- Produces:
  - `class UnsafePathError(ValueError)`
  - `def resolve_in_workspace(workspace_root: Path, candidate: str | Path) -> Path` — resolves `candidate` (absolute or relative to the workspace) and returns the resolved path. Raises `UnsafePathError` if the resolved path is outside the workspace or if any symbolic link in the candidate's chain resolves outside the workspace.
  - `take_snapshot` uses `resolve_in_workspace` for `workspace_root` (must exist and be a directory) and for `active_file` when provided. `active_file` is stored as a POSIX path relative to the workspace. `selection` is stored unchanged.
  - During walk, if a file is a symbolic link whose resolve is outside the workspace, raise `UnsafePathError` (do not skip).
  - `take_snapshot` on two trees with identical relative source contents yields the same `revision_id`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_snapshot.py`:

```python
import pytest

from latexo.snapshot import UnsafePathError, resolve_in_workspace, take_snapshot


def test_revision_id_is_stable_across_copies(tmp_path: Path) -> None:
    a = tmp_path / "a"
    b = tmp_path / "b"
    for root in (a, b):
        root.mkdir()
        (root / "cv.tex").write_text("same\n", encoding="utf-8")
    assert take_snapshot(a).revision_id == take_snapshot(b).revision_id


def test_resolve_rejects_path_escape(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    (tmp_path / "outside.tex").write_text("x\n", encoding="utf-8")
    with pytest.raises(UnsafePathError):
        resolve_in_workspace(workspace, tmp_path / "outside.tex")
    with pytest.raises(UnsafePathError):
        resolve_in_workspace(workspace, "../outside.tex")


def test_snapshot_rejects_symlink_escape(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    (workspace / "ok.tex").write_text("ok\n", encoding="utf-8")
    outside = tmp_path / "secret.tex"
    outside.write_text("secret\n", encoding="utf-8")
    link = workspace / "leak.tex"
    try:
        link.symlink_to(outside)
    except OSError:
        pytest.skip("symlinks not available")
    with pytest.raises(UnsafePathError):
        take_snapshot(workspace)


def test_snapshot_records_active_file_and_selection(tmp_path: Path) -> None:
    (tmp_path / "resume.tex").write_text("body\n", encoding="utf-8")
    selection = {"start_byte": 0, "end_byte": 4}
    snap = take_snapshot(
        tmp_path,
        active_file="resume.tex",
        selection=selection,
    )
    assert snap.active_file == "resume.tex"
    assert snap.selection == selection


def test_snapshot_rejects_active_file_outside_workspace(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    (workspace / "resume.tex").write_text("body\n", encoding="utf-8")
    with pytest.raises(UnsafePathError):
        take_snapshot(workspace, active_file="../nope.tex")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_snapshot.py::test_resolve_rejects_path_escape tests/test_snapshot.py::test_snapshot_rejects_symlink_escape tests/test_snapshot.py::test_snapshot_records_active_file_and_selection tests/test_snapshot.py::test_snapshot_rejects_active_file_outside_workspace -v`

Expected: FAIL with `ImportError` / `UnsafePathError` not defined. `test_snapshot_records_active_file_and_selection` may already pass because Task 1 stored `active_file` as given; that is acceptable. The escape tests must fail until `resolve_in_workspace` exists.

- [ ] **Step 3: Write minimal implementation**

Add to `latexo/snapshot.py` (keep existing models and helpers):

```python
class UnsafePathError(ValueError):
    pass


def resolve_in_workspace(workspace_root: Path, candidate: str | Path) -> Path:
    root = workspace_root.resolve()
    raw = Path(candidate)
    probe = raw if raw.is_absolute() else root / raw
    resolved = probe.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise UnsafePathError(f"path escapes workspace: {candidate}") from exc
    return resolved
```

In `take_snapshot`, after `root = workspace_root.resolve()`:

- If `not root.is_dir()`, raise `UnsafePathError`.
- When walking files, if `path.is_symlink()`, call `resolve_in_workspace(root, path)`.
- If `active_file` is not `None`, set `active_file = resolve_in_workspace(root, active_file).relative_to(root).as_posix()`.

Update `latexo/__init__.py`:

```python
from latexo.snapshot import (
    FileRecord,
    UnsafePathError,
    WorkspaceSnapshot,
    resolve_in_workspace,
    take_snapshot,
)

__all__ = [
    "FileRecord",
    "UnsafePathError",
    "WorkspaceSnapshot",
    "resolve_in_workspace",
    "take_snapshot",
]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_snapshot.py -v`

Expected: all tests PASS (symlink test PASS or SKIP).

- [ ] **Step 5: Commit**

```bash
git add latexo/snapshot.py latexo/__init__.py tests/test_snapshot.py
git commit -m "feat: reject unsafe snapshot paths and record editor context"
```

---

## Self-review

**Spec coverage (§5.1, §13.5):**
- Enumerate editable source files — Task 1.
- Normalized relative paths — Task 1 (`as_posix()`).
- SHA-256 — Task 1.
- Revision identifier — Task 1 + stability test in Task 3.
- Active file, selection, cursor context — Task 3 stores `active_file` and `selection`. Cursor can be fields inside `selection`; no separate type in the spec.
- Generated compiler artifacts excluded — Task 2.
- Escape and unsafe symlink rejection — Task 3.

**Not in this plan (later slices):** root resolution, `SourceSpan`, include graph, media types for assets, LangGraph `ensure_snapshot` node.

**Placeholder scan:** none.

**Type consistency:** `take_snapshot(workspace_root: Path, *, active_file: str | None = None, selection: dict | None = None) -> WorkspaceSnapshot` is unchanged after Task 1 except for raising `UnsafePathError`.

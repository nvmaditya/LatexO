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


class UnsafePathError(ValueError):
    pass


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
    if not root.is_dir():
        raise UnsafePathError(f"workspace is not a directory: {workspace_root}")
    stored_active: str | None = None
    if active_file is not None:
        stored_active = resolve_in_workspace(root, active_file).relative_to(root).as_posix()
    records: list[FileRecord] = []
    for dirpath, dirnames, filenames in root.walk(follow_symlinks=False):
        for dirname in dirnames:
            child = dirpath / dirname
            if child.is_symlink():
                resolve_in_workspace(root, child)
        dirnames[:] = [d for d in dirnames if not _should_ignore_dir(d)]
        for name in filenames:
            path = dirpath / name
            if path.is_symlink():
                resolve_in_workspace(root, path)
            if _is_generated_name(name):
                continue
            if not path.is_file():
                continue
            if path.suffix.lower() not in SOURCE_SUFFIXES:
                continue
            records.append(_file_record(root, path))
    records.sort(key=lambda f: f.path)
    return WorkspaceSnapshot(
        revision_id=_revision_id(records),
        files=records,
        active_file=stored_active,
        selection=selection,
        created_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    )

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from latexo.snapshot import UnsafePathError, resolve_in_workspace, take_snapshot


class RepairSession:
    def __init__(self, max_attempts: int = 1) -> None:
        self.attempts = 0
        self.max_attempts = max_attempts


class RepairResult(BaseModel):
    ok: bool
    attempt: int
    error: str | None = None
    requires_clarification: bool = False


class Approval(BaseModel):
    patch_id: str
    base_revision: str
    diff_sha256: str


class VersionRecord(BaseModel):
    record_id: str
    kind: Literal["commit", "undo"]
    old_revision: str
    new_revision: str
    patch_id: str
    approval: Approval | None = None


class CommitResult(BaseModel):
    ok: bool
    error: str | None = None
    record: VersionRecord | None = None


class UndoResult(BaseModel):
    ok: bool
    records: list[VersionRecord] = Field(default_factory=list)
    error: str | None = None


def _diff_sha256(unified_diff: str) -> str:
    return hashlib.sha256(unified_diff.encode("utf-8")).hexdigest()


def _records_path(store_dir: Path) -> Path:
    return store_dir / "records.json"


def load_records(store_dir: Path) -> list[VersionRecord]:
    path = _records_path(store_dir)
    if not path.exists():
        return []
    raw = json.loads(path.read_text(encoding="utf-8"))
    return [VersionRecord.model_validate(item) for item in raw]


def _save_records(store_dir: Path, records: list[VersionRecord]) -> None:
    store_dir.mkdir(parents=True, exist_ok=True)
    _records_path(store_dir).write_text(
        json.dumps([r.model_dump() for r in records], indent=2),
        encoding="utf-8",
    )


def _blob_dir(store_dir: Path, record_id: str) -> Path:
    return store_dir / "blobs" / record_id


def repair_candidate(
    session: RepairSession,
    *,
    reason: str,
    live_root: Path,
    staging_root: Path,
    correction: bytes | None = None,
    path: str = "resume.tex",
) -> RepairResult:
    del live_root
    if reason == "missing_fact":
        return RepairResult(
            ok=False,
            attempt=session.attempts,
            error="missing facts require clarification",
            requires_clarification=True,
        )
    if session.attempts >= session.max_attempts:
        return RepairResult(
            ok=False,
            attempt=session.attempts,
            error="repair budget exhausted",
        )
    if correction is not None:
        try:
            dest = resolve_in_workspace(staging_root, path)
        except UnsafePathError as exc:
            return RepairResult(ok=False, attempt=session.attempts, error=str(exc))
        session.attempts += 1
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(correction)
        return RepairResult(ok=True, attempt=session.attempts)
    session.attempts += 1
    return RepairResult(ok=True, attempt=session.attempts)


def issue_approval(patch_id: str, base_revision: str, unified_diff: str) -> Approval:
    return Approval(
        patch_id=patch_id,
        base_revision=base_revision,
        diff_sha256=_diff_sha256(unified_diff),
    )


def commit_approved(
    live_root: Path,
    staging_root: Path,
    *,
    approval: Approval | None,
    patch_id: str,
    base_revision: str,
    unified_diff: str,
    store_dir: Path,
) -> CommitResult:
    if approval is None:
        return CommitResult(ok=False, error="approval required")
    if approval.patch_id != patch_id:
        return CommitResult(ok=False, error="approval patch id mismatch")
    if approval.base_revision != base_revision:
        return CommitResult(ok=False, error="approval revision mismatch")
    if approval.diff_sha256 != _diff_sha256(unified_diff):
        return CommitResult(ok=False, error="approval diff hash mismatch")
    current = take_snapshot(live_root)
    if current.revision_id != base_revision:
        return CommitResult(ok=False, error="live workspace changed after approval")

    record_id = hashlib.sha256(
        f"{patch_id}\n{base_revision}\n{approval.diff_sha256}".encode()
    ).hexdigest()
    blobs = _blob_dir(store_dir, record_id)
    blobs.mkdir(parents=True, exist_ok=True)
    for record in current.files:
        src = resolve_in_workspace(live_root, record.path)
        dest = blobs / record.path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(src.read_bytes())

    pending: list[tuple[Path, Path]] = []
    for staged in staging_root.rglob("*"):
        if not staged.is_file():
            continue
        rel = staged.relative_to(staging_root).as_posix()
        try:
            dest = resolve_in_workspace(live_root, rel)
        except UnsafePathError:
            return CommitResult(ok=False, error=f"staged path escapes live: {rel}")
        pending.append((staged, dest))
    for staged, dest in pending:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(staged.read_bytes())

    after = take_snapshot(live_root)
    version = VersionRecord(
        record_id=record_id,
        kind="commit",
        old_revision=base_revision,
        new_revision=after.revision_id,
        patch_id=patch_id,
        approval=approval,
    )
    records = load_records(store_dir)
    records.append(version)
    _save_records(store_dir, records)
    return CommitResult(ok=True, record=version)


def undo_last(live_root: Path, store_dir: Path) -> UndoResult:
    records = load_records(store_dir)
    commit = next((r for r in reversed(records) if r.kind == "commit"), None)
    if commit is None:
        return UndoResult(ok=False, records=records, error="no commit to undo")
    blobs = _blob_dir(store_dir, commit.record_id)
    if not blobs.exists():
        return UndoResult(ok=False, records=records, error="missing version blob")
    before = take_snapshot(live_root)
    for blob in blobs.rglob("*"):
        if not blob.is_file():
            continue
        rel = blob.relative_to(blobs).as_posix()
        dest = resolve_in_workspace(live_root, rel)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(blob.read_bytes())
    after = take_snapshot(live_root)
    undo_id = hashlib.sha256(f"undo\n{commit.record_id}\n{after.revision_id}".encode()).hexdigest()
    records.append(
        VersionRecord(
            record_id=undo_id,
            kind="undo",
            old_revision=before.revision_id,
            new_revision=after.revision_id,
            patch_id=commit.patch_id,
            approval=commit.approval,
        )
    )
    _save_records(store_dir, records)
    return UndoResult(ok=True, records=records)

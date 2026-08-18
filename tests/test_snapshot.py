import hashlib
from pathlib import Path

import pytest

from latexo.snapshot import UnsafePathError, resolve_in_workspace, take_snapshot


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


def test_snapshot_excludes_generated_and_ignored_dirs(tmp_path: Path) -> None:
    (tmp_path / "resume.tex").write_bytes(b"% root\n")
    (tmp_path / "resume.aux").write_bytes(b"aux\n")
    (tmp_path / "resume.fdb_latexmk").write_bytes(b"fdb\n")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "hidden.tex").write_bytes(b"% no\n")
    minted = tmp_path / "_minted-resume"
    minted.mkdir()
    (minted / "frag.tex").write_bytes(b"% no\n")
    build = tmp_path / "build"
    build.mkdir()
    (build / "out.tex").write_bytes(b"% no\n")

    snap = take_snapshot(tmp_path)

    assert [f.path for f in snap.files] == ["resume.tex"]


def test_revision_id_is_stable_across_copies(tmp_path: Path) -> None:
    a = tmp_path / "a"
    b = tmp_path / "b"
    for root in (a, b):
        root.mkdir()
        (root / "cv.tex").write_bytes(b"same\n")
    assert take_snapshot(a).revision_id == take_snapshot(b).revision_id


def test_resolve_rejects_path_escape(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    (tmp_path / "outside.tex").write_bytes(b"x\n")
    with pytest.raises(UnsafePathError):
        resolve_in_workspace(workspace, tmp_path / "outside.tex")
    with pytest.raises(UnsafePathError):
        resolve_in_workspace(workspace, "../outside.tex")


def test_snapshot_rejects_symlink_escape(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    (workspace / "ok.tex").write_bytes(b"ok\n")
    outside = tmp_path / "secret.tex"
    outside.write_bytes(b"secret\n")
    link = workspace / "leak.tex"
    try:
        link.symlink_to(outside)
    except OSError:
        pytest.skip("symlinks not available")
    with pytest.raises(UnsafePathError):
        take_snapshot(workspace)


def test_snapshot_records_active_file_and_selection(tmp_path: Path) -> None:
    (tmp_path / "resume.tex").write_bytes(b"body\n")
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
    (workspace / "resume.tex").write_bytes(b"body\n")
    with pytest.raises(UnsafePathError):
        take_snapshot(workspace, active_file="../nope.tex")

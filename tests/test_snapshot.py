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

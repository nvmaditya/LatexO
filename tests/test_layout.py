import sys
from pathlib import Path

from latexo.compile import compile_staging

RECORDER = """\
import os
import sys
raise SystemExit(0)
"""


def test_compile_report_exposes_page_counts(tmp_path: Path) -> None:
    live = tmp_path / "live"
    stage = tmp_path / "stage"
    live.mkdir()
    stage.mkdir()
    tex = b"\\documentclass{article}\\begin{document}Hi\\end{document}\n"
    (live / "resume.tex").write_bytes(tex)
    (stage / "resume.tex").write_bytes(tex)
    recorder = tmp_path / "rec.py"
    recorder.write_text(RECORDER, encoding="utf-8")
    report = compile_staging(
        stage,
        live_root=live,
        root_file="resume.tex",
        compiler=[sys.executable, str(recorder)],
        extra_env={
            "LATEXO_PAGE_COUNT_BEFORE": "2",
            "LATEXO_PAGE_COUNT_AFTER": "1",
        },
    )
    assert report.compile_succeeded is True
    assert report.page_count_before == 2
    assert report.page_count_after == 1
    assert report.layout_warnings
    assert (live / "resume.tex").read_bytes() == tex

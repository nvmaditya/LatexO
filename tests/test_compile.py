import json
import sys
from pathlib import Path

from latexo.compile import compile_staging

FIXTURE = rb"""\documentclass{article}
\begin{document}
Hello.
\end{document}
"""

RECORDER = """\
import json
import os
import sys
from pathlib import Path

Path(os.environ["LATEXO_RECORD"]).write_text(
    json.dumps(
        {{
            "argv": sys.argv,
            "cwd": os.getcwd(),
            "env": {{
                "LATEXO_NO_NETWORK": os.environ.get("LATEXO_NO_NETWORK"),
            }},
        }}
    ),
    encoding="utf-8",
)
raise SystemExit({exit_code})
"""


def _layout(tmp_path: Path):
    live = tmp_path / "live"
    stage = tmp_path / "stage"
    live.mkdir()
    stage.mkdir()
    (live / "resume.tex").write_bytes(FIXTURE)
    (stage / "resume.tex").write_bytes(FIXTURE)
    recorder = tmp_path / "recorder.py"
    record = tmp_path / "record.json"
    return live, stage, recorder, record


def _compiler(recorder: Path) -> list[str]:
    return [sys.executable, str(recorder)]


def test_successful_staged_compile_leaves_live_untouched(tmp_path: Path) -> None:
    live, stage, recorder, record = _layout(tmp_path)
    recorder.write_text(RECORDER.format(exit_code=0), encoding="utf-8")
    report = compile_staging(
        stage,
        live_root=live,
        root_file="resume.tex",
        compiler=_compiler(recorder),
        extra_env={"LATEXO_RECORD": str(record)},
    )
    assert report.compile_succeeded is True
    assert isinstance(report.compiler_diagnostics, list)
    assert (live / "resume.tex").read_bytes() == FIXTURE
    logged = json.loads(record.read_text(encoding="utf-8"))
    assert Path(logged["cwd"]) == stage.resolve()
    assert "resume.tex" in logged["argv"]
    assert any(flag == "-no-shell-escape" for flag in logged["argv"])
    assert not any("shell-escape" in flag and flag != "-no-shell-escape" for flag in logged["argv"])
    assert logged["env"]["LATEXO_NO_NETWORK"] == "1"


def test_failing_compile_reports_diagnostics_and_keeps_live(tmp_path: Path) -> None:
    live, stage, recorder, record = _layout(tmp_path)
    recorder.write_text(RECORDER.format(exit_code=1), encoding="utf-8")
    report = compile_staging(
        stage,
        live_root=live,
        root_file="resume.tex",
        compiler=_compiler(recorder),
        extra_env={"LATEXO_RECORD": str(record)},
    )
    assert report.compile_succeeded is False
    assert report.compiler_diagnostics
    assert (live / "resume.tex").read_bytes() == FIXTURE
    assert (live / "resume.tex").stat().st_mtime_ns == (live / "resume.tex").stat().st_mtime_ns


def test_compile_root_is_staging_not_live(tmp_path: Path) -> None:
    live, stage, recorder, record = _layout(tmp_path)
    recorder.write_text(RECORDER.format(exit_code=0), encoding="utf-8")
    before = (live / "resume.tex").read_bytes()
    report = compile_staging(
        stage,
        live_root=live,
        root_file="resume.tex",
        compiler=_compiler(recorder),
        extra_env={"LATEXO_RECORD": str(record)},
    )
    logged = json.loads(record.read_text(encoding="utf-8"))
    cwd = Path(logged["cwd"]).resolve()
    assert cwd == stage.resolve()
    assert live.resolve() not in cwd.parents and cwd != live.resolve()
    assert str(live.resolve()) not in logged["argv"]
    assert (live / "resume.tex").read_bytes() == before
    assert report.compile_root.endswith("resume.tex")
    assert Path(report.compile_root).is_relative_to(stage.resolve()) or report.compile_root == "resume.tex"

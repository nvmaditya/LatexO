from __future__ import annotations

import os
import subprocess
from pathlib import Path

from pydantic import BaseModel, Field

from latexo.snapshot import UnsafePathError


class ValidationReport(BaseModel):
    compile_succeeded: bool
    compiler_diagnostics: list[dict]
    compile_root: str
    patch_applies_exactly: bool = True
    scope_valid: bool = True
    latex_structure_valid: bool = True
    factuality_valid: bool = True
    unsupported_claims: list[dict] = Field(default_factory=list)
    page_count_before: int | None = None
    page_count_after: int | None = None
    layout_warnings: list[dict] = Field(default_factory=list)
    policy_warnings: list[dict] = Field(default_factory=list)


def _staging_root_file(staging_root: Path, root_file: str) -> Path:
    stage = staging_root.resolve()
    candidate = (stage / root_file).resolve()
    try:
        candidate.relative_to(stage)
    except ValueError as exc:
        raise UnsafePathError(f"compile root escapes staging: {root_file}") from exc
    return candidate


def compile_staging(
    staging_root: Path,
    *,
    live_root: Path | None = None,
    root_file: str = "resume.tex",
    compiler: list[str] | None = None,
    extra_env: dict[str, str] | None = None,
    timeout_sec: float = 30,
) -> ValidationReport:
    del live_root  # never used for writes or cwd
    stage = staging_root.resolve()
    root = _staging_root_file(stage, root_file)
    cmd = list(compiler or ["latexmk", "-pdf", "-interaction=nonstopmode", "-halt-on-error"])
    cmd.extend(["-no-shell-escape", "-interaction=nonstopmode", root.name])
    env = os.environ.copy()
    env["LATEXO_NO_NETWORK"] = "1"
    env["openout_any"] = "p"
    env.pop("http_proxy", None)
    env.pop("https_proxy", None)
    env.pop("HTTP_PROXY", None)
    env.pop("HTTPS_PROXY", None)
    env.pop("ALL_PROXY", None)
    if extra_env:
        env.update(extra_env)
    try:
        proc = subprocess.run(
            cmd,
            cwd=stage,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return ValidationReport(
            compile_succeeded=False,
            compiler_diagnostics=[{"message": str(exc), "exit_code": None}],
            compile_root=str(root),
            latex_structure_valid=False,
        )
    ok = proc.returncode == 0
    diagnostics: list[dict] = []
    if not ok:
        text = (proc.stderr or proc.stdout or "compile failed").strip()
        diagnostics.append({"message": text, "exit_code": proc.returncode})
    return ValidationReport(
        compile_succeeded=ok,
        compiler_diagnostics=diagnostics,
        compile_root=str(root),
        latex_structure_valid=ok,
    )

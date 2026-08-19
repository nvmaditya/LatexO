from __future__ import annotations

import re
from pathlib import Path

from pydantic import BaseModel

from latexo.review import Approval, issue_approval

_METRIC = re.compile(r"\d+(?:\.\d+)?%|\$[\d,]+(?:\.\d+)?")
_EMPLOYER = re.compile(r"\b(?:at|for|joined)\s+([A-Z][\w.&-]+(?:\s+[A-Z][\w.&-]+)*)")
_PREAMBLE = re.compile(
    r"\\(?:documentclass|usepackage|RequirePackage|ProvidesClass|ProvidesPackage)\b"
)
_STYLE_SUFFIXES = (".sty", ".cls", ".clo")


class AutoApprovePolicy(BaseModel):
    enabled: bool = False
    allow_new_facts: bool = False
    allow_preamble: bool = False


class AutoApproveResult(BaseModel):
    issued: bool
    approval: Approval | None = None
    reason: str | None = None


def _added_lines(unified_diff: str) -> str:
    lines = [
        line[1:]
        for line in unified_diff.splitlines()
        if line.startswith("+") and not line.startswith("+++")
    ]
    return "\n".join(lines)


def _high_risk(
    policy: AutoApprovePolicy,
    *,
    request: str,
    unified_diff: str,
    expected_paths: list[str] | None,
) -> str | None:
    blob = f"{request}\n{_added_lines(unified_diff)}"
    if not policy.allow_new_facts and (_METRIC.search(blob) or _EMPLOYER.search(blob)):
        return "new facts are not auto-approved"
    paths = expected_paths or []
    if not policy.allow_preamble:
        if any(p.lower().endswith(_STYLE_SUFFIXES) for p in paths):
            return "preamble or class/style edits are not auto-approved"
        if _PREAMBLE.search(blob):
            return "preamble or class/style edits are not auto-approved"
    return None


def auto_approve(
    *,
    policy: AutoApprovePolicy | None,
    patch_id: str,
    base_revision: str,
    unified_diff: str,
    live_root: Path | None = None,
    expected_paths: list[str] | None = None,
    request: str = "",
) -> AutoApproveResult:
    del live_root
    if policy is None or not policy.enabled:
        return AutoApproveResult(issued=False, reason="no auto-approval policy")
    blocked = _high_risk(
        policy,
        request=request,
        unified_diff=unified_diff,
        expected_paths=expected_paths,
    )
    if blocked:
        return AutoApproveResult(issued=False, reason=blocked)
    approval = issue_approval(patch_id, base_revision, unified_diff)
    return AutoApproveResult(issued=True, approval=approval)

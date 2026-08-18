from latexo.apply import (
    ApplyResult,
    DeleteSpan,
    InsertAtSpan,
    PatchSet,
    ReplaceSpan,
    apply_patchset,
)
from latexo.locate import LocatedTarget, LocationResult, locate_targets
from latexo.plan import (
    EditPlan,
    PlannedChange,
    PlanningResult,
    UserFact,
    plan_edit,
)
from latexo.root import RootResolution, resolve_root
from latexo.segment import SourceSpan, segment_source
from latexo.snapshot import (
    FileRecord,
    UnsafePathError,
    WorkspaceSnapshot,
    resolve_in_workspace,
    take_snapshot,
)

__all__ = [
    "ApplyResult",
    "DeleteSpan",
    "EditPlan",
    "FileRecord",
    "InsertAtSpan",
    "PatchSet",
    "ReplaceSpan",
    "LocatedTarget",
    "LocationResult",
    "PlannedChange",
    "PlanningResult",
    "RootResolution",
    "SourceSpan",
    "UnsafePathError",
    "WorkspaceSnapshot",
    "UserFact",
    "apply_patchset",
    "locate_targets",
    "plan_edit",
    "resolve_in_workspace",
    "resolve_root",
    "segment_source",
    "take_snapshot",
]

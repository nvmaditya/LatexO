from latexo.facts import FactLedger, ResumeFact, build_fact_ledger
from latexo.compile import ValidationReport, compile_staging
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
from latexo.review import (
    Approval,
    CommitResult,
    RepairResult,
    RepairSession,
    UndoResult,
    VersionRecord,
    commit_approved,
    issue_approval,
    load_records,
    repair_candidate,
    undo_last,
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
    "Approval",
    "ApplyResult",
    "CommitResult",
    "DeleteSpan",
    "EditPlan",
    "FactLedger",
    "FileRecord",
    "InsertAtSpan",
    "PatchSet",
    "RepairResult",
    "RepairSession",
    "ReplaceSpan",
    "ResumeFact",
    "LocatedTarget",
    "LocationResult",
    "PlannedChange",
    "PlanningResult",
    "RootResolution",
    "SourceSpan",
    "UndoResult",
    "UnsafePathError",
    "ValidationReport",
    "VersionRecord",
    "WorkspaceSnapshot",
    "UserFact",
    "apply_patchset",
    "build_fact_ledger",
    "commit_approved",
    "compile_staging",
    "issue_approval",
    "load_records",
    "locate_targets",
    "plan_edit",
    "repair_candidate",
    "resolve_in_workspace",
    "resolve_root",
    "segment_source",
    "take_snapshot",
    "undo_last",
]

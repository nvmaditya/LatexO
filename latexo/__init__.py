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
    "FileRecord",
    "RootResolution",
    "SourceSpan",
    "UnsafePathError",
    "WorkspaceSnapshot",
    "resolve_in_workspace",
    "resolve_root",
    "segment_source",
    "take_snapshot",
]

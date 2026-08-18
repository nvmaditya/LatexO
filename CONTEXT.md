# LatexO (LaTeX resume patch editor)

Controlled editing of a LaTeX resume project. Models propose typed patches; deterministic code owns locations, bytes, compilation, factuality, and commit.

## Language

**Workspace**:
The on-disk LaTeX project the user is editing.
_Avoid_: repo, folder, project root (except when naming the compilation root)

**Snapshot**:
A revision-scoped inventory of editable source files, their hashes, and optional editor context.
_Avoid_: checkout, index, listing

**File record**:
One file in a snapshot: normalized relative path, SHA-256, size, media type, generated flag.

**Revision**:
The identifier of one snapshot. Spans and patches are valid only against this revision.
_Avoid_: commit, version (except version record)

**Source span**:
A parser-bounded region of a file in a specific revision, addressed by `span_id` and content hash — never by model-authored line numbers.
_Avoid_: range, selection (selection is editor UI context), region

**Compilation root**:
The source file that should be compiled (contains `\documentclass` and a document body, or is explicitly chosen).
_Avoid_: main, entrypoint, index

**Intent**:
A structured classification of the user request (operation, targets, constraints, facts, scope, risk). Not a write.

**Located target**:
A source span chosen for an edit, with a reason and confidence.

**Edit plan**:
The bounded list of planned changes, expected paths, invariants, and validation requirements.

**Patch set**:
An immutable, revision-bound list of typed operations (`replace`, `insert_before`, `insert_after`, `delete`).
_Avoid_: diff (the unified diff is the human-readable rendering), change set

**Staging**:
Isolated candidate files produced by applying a patch set. Not the live workspace.

**Approval**:
A human decision bound to a patch id, base revision, and exact diff hash. Required before commit in version 1.

**Version record**:
Append-only evidence of an accepted edit (old/new revision, patch, approval, validation). Undo creates a new reverse patch or restores a stored revision.

**Fact**:
A resume claim with provenance: document span or explicit user message. Unsupported claims are not written.

**Fact ledger**:
The set of facts in scope for the current request. Phase 2.

**Single writer**:
Only deterministic application code applies patches and commits. Models propose.

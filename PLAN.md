# LatexO plan

Project-specific phase map. Process: [skills-guide HOW_TO_WORK](https://github.com/nvmaditya/skills-guide/blob/main/HOW_TO_WORK.md). Binding spec: [`specs.md`](./specs.md). Language: [`CONTEXT.md`](./CONTEXT.md).

```
Think → Plan → Implement (small) → Verify → Review → Next
```

## Binding constraints (from `specs.md`)

- Single writer: models propose; deterministic code applies and commits.
- Exactness over convenience: stale and ambiguous patches fail closed. No silent fuzzy writes.
- Validation before mutation: live workspace unchanged until approval + validation.
- Revision awareness: every span and patch belongs to a snapshot. Concurrent edits regenerate.
- Factual provenance: new claims come from an existing source span or an explicit user message.
- Bounded autonomy: patch size, file scope, repair attempts, compiler time, tool access have limits.
- Human approval is mandatory in version 1.
- No unrestricted shell or filesystem writer for model nodes.

## Skill map

| Phase / milestone | Primary skills | Hard rule to test |
|---|---|---|
| 1.1 Workspace snapshot + path safety | `writing-plans`, `test-driven-development`, **ponytail** | Paths that escape the workspace or resolve through unsafe symbolic links are rejected. Generated compiler artifacts are excluded from edit scope. Every file has SHA-256 and a revision-scoped snapshot. |
| 1.2 Root resolution | `test-driven-development`, **ponytail** | Unique `\documentclass` + body wins; several plausible roots require clarification, not a guess. |
| 1.3 Structural segmentation | `test-driven-development`, **ponytail** | Spans are parser-bounded. Models never author offsets or line numbers. `span_id` is valid only within its revision. |
| 1.4 Active-selection-aware location | `test-driven-development`, **ponytail** | Selection/cursor first. Low confidence → interrupt. Patch generator cannot override location. |
| 1.5 Structured planning | `test-driven-development`, **ponytail** | Plan names existing spans, allowed facts, invariants. Missing facts → clarification, not invention. |
| 1.6 Span patches, atomic staging, unified diffs | `test-driven-development`, **ponytail** | Apply all operations or none. Hash mismatch fails closed. Fuzzy match is diagnostic only. |
| 1.7 Sandboxed compilation | `test-driven-development`, **ponytail** | Compiler: no network, no shell escape, staged files only, resource limits. Failed staging leaves live project unchanged. |
| 1.8 Repair (1), approval, version records, undo | `test-driven-development`, **ponytail** | One repair for ordinary edits. Approval bound to patch ID + base revision + diff hash. Every accepted edit is inspectable and reversible. |
| Phase 2 | see `specs.md` §17.2 | Fact ledger + multi-target merge. Highest-severity failure: invented fact. |
| Phase 3 | see `specs.md` §17.3 | Auto-approval only for explicit low-risk policy. |

Phase 1 is one product milestone (`specs.md` §17.1) and several sequential plans. Each plan must produce working, testable software. Do not start Phase 2 until Phase 1 acceptance for that slice is green.

## Current work

**Done:**
- 1.1 [`docs/superpowers/plans/2026-08-18-workspace-snapshot.md`](./docs/superpowers/plans/2026-08-18-workspace-snapshot.md)
- 1.2 [`docs/superpowers/plans/2026-08-18-root-resolution.md`](./docs/superpowers/plans/2026-08-18-root-resolution.md)

**Next:** 1.3 structural segmentation (`SourceSpan` tree).

**Slice 1.2 exit criterion:** unique `\documentclass`+body wins; multiple or zero roots require clarification; explicit/confirmed roots win; escaping paths raise `UnsafePathError`. Met.

## Out of scope until later slices

LangGraph, LLM calls, fact ledger, semantic ontology, fan-out merge, TeX Live image, UI, Git-as-user-repo commits.

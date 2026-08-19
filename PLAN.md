# Plan

How LatexO gets built. Binding spec: [`specs.md`](./specs.md). Language: [`CONTEXT.md`](./CONTEXT.md). Process: [skills-guide HOW_TO_WORK](https://github.com/nvmaditya/skills-guide/blob/main/HOW_TO_WORK.md).

```
Think → Plan → Implement (small) → Verify → Review → Next
```

## Constraints

Copied from the spec, not restated as taste:

- Single writer: models propose; deterministic code applies and commits.
- Exactness over convenience: stale and ambiguous patches fail closed. No silent fuzzy writes.
- Validation before mutation: the live workspace stays unchanged until approval and validation succeed.
- Revision awareness: every span and patch belongs to a snapshot. Concurrent edits regenerate.
- Factual provenance: new claims come from an existing source span or an explicit user message.
- Bounded autonomy: patch size, file scope, repair attempts, compiler time, and tool access have limits.
- Human approval is mandatory in version 1.
- Model nodes do not get an unrestricted shell or filesystem writer.

## Phases

| Slice | Status | Hard rule |
|---|---|---|
| 1.1 Workspace snapshot + path safety | Done | Escaping and unsafe symlink paths are rejected. Generated artifacts are out of edit scope. Every file has a SHA-256. |
| 1.2 Root resolution | Done | Unique `\documentclass` + body wins. Several plausible roots require clarification. |
| 1.3 Structural segmentation | Done | Spans are parser-bounded. Models never author offsets or line numbers. `span_id` is valid only in its revision. |
| 1.4 Active-selection-aware location | Done | Selection and cursor first. Low confidence interrupts. The patch generator cannot override location. |
| 1.5 Structured planning | Done | The plan names existing spans, allowed facts, and invariants. Missing facts ask; they do not invent. |
| 1.6 Span patches, atomic staging, unified diffs | Done | Apply every operation or none. Hash mismatch fails closed. Fuzzy match is diagnostic only. |
| 1.7 Sandboxed compilation | Done | No network, no shell escape, staged files only, resource limits. Failed staging leaves the live project unchanged. |
| 1.8 Repair (1), approval, versions, undo | Done | One repair for ordinary edits. Approval is bound to patch id + base revision + diff hash. Accepted edits are reversible. |
| 2.1 Fact ledger | Done | Document facts bind to existing spans. Unsupported claims are not authorized. Invented facts are the worst failure. |
| 2.2 Include graph | Done | `\input`/`\include` edges stay in-workspace. Escapes are dropped. Missing targets are unresolved. Include ranking breaks a unique includer; true ties still ask. |
| 2.3 Deterministic merge | Done | Two non-overlapping proposals become one atomic candidate. Duplicates, nests, overlaps, and stale hashes fail closed. |
| 2.4 Section operations | Done | Whole-section replace/delete/reorder apply atomically to staging. Overlap fails closed. |
| 2.5 Ontology labels and macros | Done | Deterministic experience/education labels on existing spans. Macro definitions retrieved from snapshot spans. |
| 2.6 Concurrent/stale revision | Done | Apply/commit against a previous revision fail closed after live bytes change. |
| 2.7 Checkpointer | Done | SQLite store writes revision + patch id transactionally and reloads in a new process. |
| 2.8 Layout + eval CI | Done | Compile report exposes page-count fields. CI runs pytest plus a multi-file/custom-macro eval case. |
| 3.1 Low-risk auto-approval | Done | Explicit policy may issue a bound approval for local rewrites with no new facts. High-risk or no policy still requires a human. CAS still holds. |
| Phase 3 remainder | Later | Style annotations, preamble/style edits under stricter review, visual regression, telemetry, independent critic. |

Phase 1 is one product milestone ([`specs.md`](./specs.md) §17.1) split into sequential plans. Each plan has to leave working, tested software. Phase 2 waits until Phase 1 slices are green.

## Skills per slice

| Slice | Primary skills |
|---|---|
| 1.1–1.8 | `writing-plans`, `test-driven-development`, **ponytail** |
| Phase 2–3 | same, plus domain tests for factuality |

## Current work

Done:

- [1.1 workspace snapshot](./docs/superpowers/plans/2026-08-18-workspace-snapshot.md)
- [1.2 root resolution](./docs/superpowers/plans/2026-08-18-root-resolution.md)
- 1.3 structural segmentation (`latexo.segment.segment_source`)
- 1.4 active-selection-aware location (`latexo.locate.locate_targets`)
- 1.5 structured planning (`latexo.plan.plan_edit`)
- 1.6 span patches, atomic staging, unified diffs (`latexo.apply.apply_patchset`)
- 1.7 sandboxed compilation (`latexo.compile.compile_staging`)
- 1.8 repair, approval, version records, undo (`latexo.review`)

Phase 1 slices 1.1–1.8, Phase 2 slices 2.1–2.8, and Phase 3.1 low-risk auto-approval are implemented.

Next: remaining Phase 3 (style annotations, visual regression, telemetry, critic).

## Later

LangGraph wiring, LLM calls, a TeX Live image, UI, and Git commits inside a user's existing repo.

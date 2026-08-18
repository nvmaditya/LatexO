# LatexO

Exact edits for LaTeX resumes. The model proposes a typed patch. Deterministic code decides which bytes change, whether the project still compiles, and whether the patch may be committed.

It does not assume a template, a filename, or a section macro. It does not invent jobs, dates, metrics, or credentials.

```python
from pathlib import Path
from latexo import take_snapshot, resolve_root

workspace = Path("my-resume")
snap = take_snapshot(workspace)
root = resolve_root(snap, workspace)

print(snap.revision_id)
print(root.root_path, root.requires_clarification)
```

`take_snapshot` inventories editable sources (`.tex`, `.sty`, `.cls`, `.bib`, …), hashes each file, and stamps a revision id. Paths that escape the workspace fail closed. Generated compiler junk is left out of edit scope.

`resolve_root` picks the compilation root. A unique `\documentclass` plus `\begin{document}` wins. Several plausible roots require clarification instead of a guess.

`segment_source` walks the snapshotted `.tex` bytes and returns revision-bound spans. Bounds come from the parser. Identifiers are hashes, not line numbers. Unclosed environments and unbalanced braces do not emit a span that pretends they were closed.

`locate_targets` picks among those spans. An active selection or cursor wins when it sits in exactly one span. Otherwise a unique heading or quoted substring can win. Two equal hits require clarification. Location never invents a span the segmenter did not emit.

`plan_edit` turns a unique location plus a request into a typed plan: existing span ids, replace/insert/delete, expected paths, invariants, and required approval. A new metric or employer that is not in the document and not supplied as a user fact causes an ask instead of an invented fact id.

`apply_patchset` checks each operation's span hash, rejects overlap and stale revisions, then writes every change into a staging directory or writes none. The live workspace is not modified. The unified diff is live versus staged.

`compile_staging` runs the compiler against the staging tree only. It adds `-no-shell-escape`, sets `LATEXO_NO_NETWORK=1`, and never writes the live workspace. Tests inject a recorder when TeX is not installed.

`repair_candidate` allows one ordinary repair on staging and refuses a second. Missing facts ask; they do not invent. `issue_approval` / `commit_approved` bind approval to patch id, base revision, and diff hash. A live-file change after approval blocks commit. `undo_last` restores the recorded prior bytes and appends history.

`build_fact_ledger` extracts employers, dates, and quantities from existing spans and records caller-supplied claims as `user_message` facts. Planning only allows ledger ids. A metric that is not in the document and not supplied still requires clarification.

`build_include_map` records `\input`/`\include` edges between snapshot files. Comments do not count. Paths that escape the workspace are not in-workspace edges. A missing relative target is unresolved. `resolve_root` uses that graph when more than one `\documentclass`+body exists.

## Status

Phase 1 (safe single-target MVP) is implemented and tested.

| Slice | What it does |
|---|---|
| 1.1 Snapshot | Revision-scoped file inventory, SHA-256, editor context, path safety |
| 1.2 Root | Explicit / confirmed / unique document root, or ask |
| 1.3 Spans | Deterministic `SourceSpan` tree: preamble, envs, sections, items, paragraphs, macros |
| 1.4 Location | Selection/cursor first, then unique heading or quote; ties ask instead of guessing |
| 1.5 Planning | Unique target plus rewrite/delete becomes an approved plan; missing facts ask |
| 1.6 Apply | Hash-checked ops go to isolated staging plus a unified diff; live files stay put |
| 1.7 Compile | Staging-only compile with no shell escape and no network; live files stay put |
| 1.8 Review | One repair attempt, bound approval, version record, undo |

The highest-severity failure in later slices is a polished, compiling resume that added a fact nobody supplied.

[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/downloads/)
[![tests](https://github.com/nvmaditya/LatexO/actions/workflows/test.yml/badge.svg)](https://github.com/nvmaditya/LatexO/actions/workflows/test.yml)

## Rules the code has to keep

- One writer. Models propose. Application code applies and commits.
- Stale or ambiguous patches fail. There is no silent fuzzy match.
- The live workspace is untouched until validation and human approval succeed.
- Every span and patch is bound to a snapshot revision.
- New claims need an existing source span or an explicit user message.

Full architecture: [`specs.md`](./specs.md).

## Install

Python 3.12+. Pydantic v2.

```bash
pip install -e ".[dev]"
python -m pytest -v
```

## Layout

```
latexo/           snapshot + root resolution
tests/            pytest
specs.md          architecture spec (draft 0.1)
PLAN.md           phase map
CONTEXT.md        domain language
docs/superpowers/ implementation plans
```

## Docs

| | |
|---|---|
| Architecture spec | [`specs.md`](./specs.md) |
| Phase map | [`PLAN.md`](./PLAN.md) |
| Glossary | [`CONTEXT.md`](./CONTEXT.md) |
| Snapshot plan | [`docs/superpowers/plans/2026-08-18-workspace-snapshot.md`](./docs/superpowers/plans/2026-08-18-workspace-snapshot.md) |
| Root plan | [`docs/superpowers/plans/2026-08-18-root-resolution.md`](./docs/superpowers/plans/2026-08-18-root-resolution.md) |
| Agent notes | [`AGENTS.md`](./AGENTS.md) |

## License

MIT.

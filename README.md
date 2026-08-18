# LatexO

Controlled LaTeX resume patch editor. Models propose typed patches; deterministic code owns locations, bytes, compilation, and commit.

- Spec: [`specs.md`](./specs.md)
- Phase map: [`PLAN.md`](./PLAN.md)
- Language: [`CONTEXT.md`](./CONTEXT.md)

## Setup

Python 3.11+. `pydantic>=2` and `pytest>=8`.

```
python -m pytest -v
```

## Current slice

Phase 1.1–1.2 on `feat/workspace-snapshot`: snapshot, revision id, path safety, compilation-root resolution.

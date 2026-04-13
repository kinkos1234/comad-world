# ADR 0005 — Eye Package Layout (Tier 3 Phase 2)

- **Status:** Accepted (scaffold landed 2026-04-14)
- **Date:** 2026-04-14
- **Deciders:** Comad World maintainer (@kinkos1234)
- **Related:** ADR 0001 (Repository Strategy), refact.md Tier 3

## Context

Eye's code lives in a flat `eye/` directory: 60+ modules at the repo
root, a partially-populated `utils/`, plus domain dirs like `analysis/`,
`simulation/`, `pipeline/`. Imports look like `from utils.config import
…`, `from analysis.base import …`. This layout has three problems:

1. **Name collisions.** `eye/config.py` vs `eye/utils/config.py`,
   `eye/impact_analyzer.py` vs `eye/utils/impact_analyzer.py` — nine
   such pairs were identified and purged in the Tier 3 kickoff
   (`897ca4e`). More could drift.
2. **No package boundary.** There is no `comad_eye` namespace. Anything
   at cwd is importable; anything not at cwd isn't.
3. **No install target.** We can't `pip install -e eye/` and get a
   predictable public API. `docker-compose` and scripts rely on cwd
   gymnastics.

## Goals

1. **Canonical src/ layout.** Code lives under `eye/src/comad_eye/`.
   Anything not exported from there is considered private.
2. **Zero breakage during migration.** Every existing import path keeps
   working until its module is moved. Moves land one-at-a-time with a
   shim the old path re-exports from.
3. **Installable.** `pip install -e eye/` pulls in the package
   declared by `eye/pyproject.toml`.
4. **Test continuity.** `pytest tests/` from eye/ keeps working through
   the migration via `eye/conftest.py` adding `src/` to `sys.path`.

## Non-goals

- Rewriting domain module names. `analysis`, `simulation`, `pipeline`
  stay named as they are; they just move under `comad_eye.`.
- Changing public Python APIs. A move is always a rename path, not a
  symbol rename.
- Fixing the brain/eye two-repo split (ADR 0001 topic).

## Decision

### Shape

```
eye/
├── pyproject.toml            # declares the package (src layout)
├── conftest.py               # adds src/ to sys.path for pytest
├── src/
│   └── comad_eye/
│       ├── __init__.py
│       ├── impact_analyzer.py    # migrated 2026-04-14
│       ├── utils/                # (planned) utils.* → comad_eye.utils.*
│       ├── analysis/             # (planned)
│       ├── simulation/           # (planned)
│       └── pipeline/             # (planned)
├── utils/                    # ← shrinks as modules migrate
├── analysis/                 # ← shrinks as modules migrate
├── …
└── tests/                    # imports target both old and new paths
```

### Migration protocol (per module)

1. Copy `eye/<dir>/<module>.py` to `eye/src/comad_eye/<dir>/<module>.py`.
2. Replace the old file with a shim:

   ```python
   """Compatibility shim — canonical impl in comad_eye.<dir>.<module>."""
   from comad_eye.<dir>.<module> import *  # noqa
   ```

3. Add a CHANGELOG entry listing the new canonical path.
4. Leave callsites alone until an intentional rewrite sweep (see below).

### Callsite rewrite sweep

Once ≥70% of modules have migrated, do a single mechanical sweep that
rewrites `from utils.X` / `from analysis.X` → `from comad_eye.utils.X`
etc. The sweep is a separate PR per domain dir, reviewed against the
diff, with zero hand-edits.

### When do the shims go away?

After the sweep, shims stay for one release (backward-compat for any
out-of-tree consumers). The release notes call out the removal date.

## Rollout

- **Phase 2a (this PR):** scaffold only. `pyproject.toml`, `conftest.py`,
  `src/comad_eye/__init__.py`, and one migrated module
  (`impact_analyzer`) as a shape test.
- **Phase 2b:** migrate `utils/` (8 modules). Small PRs, one module
  each.
- **Phase 2c:** migrate domain dirs (`analysis`, `simulation`,
  `pipeline`, `ingestion`, `graph`, `narration`) in that order. Each is
  its own PR.
- **Phase 2d:** callsite rewrite sweep.
- **Phase 2e:** drop shims after one release.

The memory note estimated 1–2 weeks for the whole migration. That still
stands — what lands here is the foundation.

## Alternatives considered

- **Flat → `comad_eye/` (no src/).** Works, but `src/` is the
  conventional boundary between importable code and project metadata;
  it rules out accidental imports from scripts at the repo root.
- **Big-bang rewrite.** Too risky. Eye is live, has 80 tests, and
  docker images ship from its current layout.
- **Move domain dirs without renaming them into `comad_eye/`.** Would
  leave `from analysis import base` ambiguous vs. third-party
  `analysis` packages.

## Open questions

- Does the umbrella need to know about `pyproject.toml`? Only if the
  umbrella ever wants to install `comad_eye` (it doesn't today).
- Do we rename `comad_eye.utils` to `comad_eye.core` to match brain's
  naming? Defer — utils is fine short-term.

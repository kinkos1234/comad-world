# ADR 0002 — `comad.config.yaml` Contract

- **Status:** Accepted (PR 1 landed 2026-04-14)
- **Date:** 2026-04-14
- **Deciders:** Comad World maintainer (@kinkos1234)
- **Depends on:** ADR 0001 (Repository Strategy)
- **Implements:** refact.md §3 (루트 설정/오케스트레이션 재설계)

## Context

`comad.config.yaml` is advertised as the single file a user edits to retarget
the entire system (AI/ML ↔ web dev ↔ finance ↔ biotech). In practice:

- **No schema exists.** A typo in `profile.name` fails silently; an unknown key
  is ignored; a missing required section surfaces only when a downstream
  module crashes.
- **`scripts/apply-config.sh` is narrow.** It regenerates `ear/interests.md`
  and `ear/CLAUDE.md`, and that's it. Brain reads the config at runtime.
  Eye/photo/sleep/voice do not participate.
- **The top-level sections drifted** from their original design. Today the
  file has `profile`, `interests`, `categories`, `sources`,
  `must_read_stack`, `brain`, `eye`, `ear`. No contract says which of these
  is required vs. optional, which modules read which sections, or what the
  cross-language types are.

This ADR defines the contract so that `apply-config.sh` can generalize and
so that users get immediate, specific errors instead of runtime surprises.

## Goals

1. **Single source of truth for the shape.** A JSON Schema generated from the
   same spec that TypeScript (`zod`) and Python (`pydantic`) loaders validate
   against.
2. **Per-section ownership.** Every top-level section is owned by exactly one
   module (or by the umbrella). The schema records this so `apply-config.sh`
   knows what to regenerate when a section changes.
3. **Graceful evolution.** Adding a new optional field must not break an
   existing installation. Removing or renaming is a breaking change that
   triggers a migration note in `CHANGELOG.md`.
4. **Validation is cheap.** `make validate-config` (and the CI job) must run
   in under two seconds, with zero network access.

## Scope

In scope: the shape of `comad.config.yaml`, the validation pipeline, and the
rules `apply-config.sh` uses to regenerate module configs.

Out of scope: module-internal config files (`eye/config/*.yaml`,
`brain/packages/*/config/*.json`, etc.). Those are owned by their modules per
ADR 0001 §1.

## Proposed top-level shape

```yaml
profile:                    # REQUIRED — identity + persona knobs
  name: string              #   preset name shown in logs/UI
  display_name: string      #   human-readable
  description: string
  persona: string           #   prose blurb fed to LLM prompts

interests:                  # REQUIRED — domain anchor list
  keywords:                 #     strings the crawlers key on
    - string
  lenses:                   #     OPTIONAL list of analysis lens IDs
    - string

categories:                 # REQUIRED — classification buckets used by ear
  - id: string
    name: string
    keywords: [string, ...]

sources:                    # REQUIRED — what to crawl
  rss:      [ { url, category?, weight? }, ... ]
  arxiv:    [ { query, category?, weight? }, ... ]
  github:   [ { query, category?, weight? }, ... ]
  hn:       { enabled: bool, daily_limit?: int, keywords?: [string] }

must_read_stack:            # OPTIONAL — ear must-read rules
  min_score: number         #     0.0–1.0
  requires_all: [string, ...]

brain:                      # OPTIONAL — brain module overrides
  extraction:
    model: string
    batch_size: int
  graphrag:
    recall_target: number
    latency_target_ms: int

eye:                        # OPTIONAL — eye module overrides
  simulation:
    rounds: int
    decay: number
  lenses:
    defaults: [string, ...]

ear:                        # OPTIONAL — ear module overrides
  digest:
    enabled: bool
    schedule_cron: string
  archive:
    format: "markdown" | "json"
```

Sections not listed above (`voice`, `photo`, `sleep`, `search`, `browse`) are
**not** valid at the top level under this contract. Those modules are
domain-agnostic; they ingest no per-interest config.

## Ownership matrix

| Section            | Owner   | Regeneration target                           |
|--------------------|---------|-----------------------------------------------|
| `profile`          | umbrella| none — read inline by all modules             |
| `interests`        | umbrella| `ear/interests.md`, `brain/config/keywords.json` (new) |
| `categories`       | ear     | `ear/CLAUDE.md`, `ear/config/categories.yaml`  |
| `sources`          | brain   | `brain/config/sources.yaml`                   |
| `must_read_stack`  | ear     | `ear/config/must_read.yaml`                   |
| `brain.*`          | brain   | `brain/config/runtime.yaml`                   |
| `eye.*`            | eye     | `eye/config/overrides.yaml`                   |
| `ear.*`            | ear     | `ear/config/runtime.yaml`                     |

`apply-config.sh` walks this matrix: for every section present in the user's
`comad.config.yaml`, it regenerates the listed targets. Missing optional
sections are skipped, not errored. Changing any target file by hand is
permitted but loses on next `apply-config.sh` run — that's the tradeoff of
config-driven generation.

## Validation pipeline

1. **Canonical schema:** `schema/comad.config.schema.json` (JSON Schema
   draft-2020-12). Hand-authored. The contract lives here.
2. **Python loader:** `scripts/config/loader.py` — thin `pydantic` model
   generated from the JSON Schema via `datamodel-code-generator`, invoked
   whenever an eye/photo/sleep script needs to read the config.
3. **TypeScript loader:** `brain/packages/core/src/config/loader.ts` —
   `zod` schema generated from the JSON Schema via `json-schema-to-zod`.
4. **CI gate:** `.github/workflows/structure-guard.yml` adds a
   `config-schema-validation` job that runs `ajv validate -s <schema>
   -d comad.config.yaml` on every push.
5. **Local gate:** `make validate-config` runs the same check.

Regeneration of the Python/TypeScript types from the JSON Schema is a
build-time concern (a Makefile target, not a runtime requirement).

## Failure semantics

- **Unknown top-level key** → validation error with the key name.
- **Unknown field under a known section** → warning (forward-compatibility).
- **Missing required field** → validation error with JSON Pointer to the
  location.
- **Type mismatch** (e.g. `rounds: "ten"`) → validation error.
- **Deprecated section** still present → warning + link to the CHANGELOG
  entry that removed it.

## Implementation plan (follow-up PRs)

1. **PR 1 — schema + validation gate** (Tier 2 Step 7 narrow scope):
   - Hand-author `schema/comad.config.schema.json`.
   - Add `make validate-config` using `ajv-cli` (npm, devDep of umbrella).
   - Add CI job.
   - No code changes to modules yet.
2. **PR 2 — apply-config generalization** (Tier 2 Step 8):
   - Rewrite `scripts/apply-config.sh` to consume the ownership matrix
     above. Keep ear outputs byte-identical to the current script.
   - Add `scripts/apply-config.sh --dry-run` for preview.
3. **PR 3 — per-module loaders**:
   - Brain: `zod` schema → typed config loader.
   - Eye: `pydantic` model → typed config loader.
   - Replace ad-hoc YAML reads.
4. **PR 4 — type codegen from schema** (optional, low priority):
   - Makefile target that regenerates the zod + pydantic artifacts whenever
     the JSON Schema changes.

## Open questions

- Should `interests.lenses` live under `eye.lenses.defaults` instead?
  (Lean toward **yes** — lenses are an eye concept; `interests.lenses`
  was a historical shortcut.)
- Should `hn` be part of `sources.rss` with a `type: hn` discriminator?
  Keep separate for now; change later only if we add more bespoke sources.

## Decision

**Accepted.** PR 1 landed in `2026-04-14`:

- `schema/comad.config.schema.json` — canonical JSON Schema (draft-2020-12).
  Validated against the live `comad.config.yaml` and all four
  `presets/*.yaml`.
- `scripts/validate-config.sh` — local/CI validator (python3+PyYAML →
  JSON → `ajv-cli@5`).
- `make validate-config` — Makefile entrypoint.
- `.github/workflows/structure-guard.yml` — new `config-schema-validation`
  job runs the validator on every push/PR.

Remaining work tracked under Phase 3 of `refact.md`: PR 2 (apply-config
generalization), PR 3 (per-module typed loaders), PR 4 (type codegen).

**Update 2026-04-14 (later):** PR 2, PR 3, and PR 4 landed. PR 4 was
reframed from full codegen to a parity gate (`make schema-sync-check`,
`scripts/check-loaders-in-sync.sh`) that fails CI whenever the
hand-authored zod/pydantic loaders drift from the JSON Schema. Full
codegen via `json-schema-to-zod` / `datamodel-code-generator` remains an
option if the hand-authored loaders become burdensome to maintain.

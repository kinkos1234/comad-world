# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added (2026-04-14 session)

- **ADR 0002 PR 2–4 (complete)** — `scripts/apply-config.sh` now generates
  `brain/config/{sources.yaml, keywords.json, runtime.yaml}` and
  `eye/config/overrides.yaml` from the ownership matrix. Hand-authored
  zod (brain) + pydantic (eye) typed loaders validate the umbrella
  config on load; `scripts/check-loaders-in-sync.sh` + `make
  schema-sync-check` + CI job (`schema-loader-parity`) fail if the
  loaders drift from `schema/comad.config.schema.json`.
- **ADR 0003 — Hybrid Synthesis Routing** (`docs/adr/0003-hybrid-synthesis-routing.md`):
  `brain/packages/graphrag/src/synth-classifier.ts` heuristically routes
  easy questions to Ollama / hard to `claude -p`.
  `brain/data/logs/synth-routing.jsonl` captures every decision;
  `scripts/synth-routing-report.sh` summarizes for tuning. Env-gated by
  `SYNTH_ROUTING` (default off). 15 unit tests lock the boundary.
- **ADR 0004 — Search → Brain Feedback Loop** (`docs/adr/0004-search-brain-feedback.md`):
  on successful `/search --apply` verification, `recordAdoptedRepo()`
  writes `brain/data/adopted/<date>-<slug>.md`; ingester's
  `ingestDirectory()` now scans both `ear/archive/` and the adopted dir
  with distinct slug prefixes so Article UIDs never collide. Env-gated
  by `BRAIN_ADOPT_FEEDBACK` (default off).
- **ADR 0005 — Eye Package Layout** (`docs/adr/0005-eye-package-layout.md`):
  flat `eye/*.py` → canonical `eye/src/comad_eye/` layout. Phase 2a–2d
  shipped in-session: `pyproject.toml` + `conftest.py` + 50 modules
  migrated (9 utils flat + 7 domain dirs × 6–11 modules each) +
  callsite sweep across 82 files. Every legacy path gets a 2-line shim
  using `sys.modules[__name__] = canonical` so both public and private
  (`_foo`) names resolve identically.
- **ADR 0006 — Evidence Timeline Retention** (`docs/adr/0006-evidence-retention.md`):
  90d hot Neo4j / 1y warm JSONL.zst / cold S3, with compaction rules
  and ≤ 10 GB/yr budget. `brain/packages/ingester/src/prune-evidence.ts`
  implements the weekly job (--dry-run default). Lands with Issue #2.
- **Issue #2 Preconditions (House/Bach/Kondo) scaffolded**:
  `docs/planning/hallucination-catalog.md` + `scripts/mine-hallucination-candidates.sh`
  + `scripts/score-hallucination-catalog.sh` (House ≥ 80% gate);
  `brain/packages/ingester/src/audit-claim-evidence.ts` emits a JSON
  projection of claim timeline anchors (Bach ≥ 60% gate); ADR 0006
  (Kondo).
- **CI expansion**: `Eye Python Tests` job runs the full 1,336-test
  suite (was hidden behind the nested-repo boundary); `Voice Bats
  Tests` surfaces 12/12 green; `comad.lock freshness` advisory flags
  drift via new `scripts/upgrade.sh --lock-check` flag + `make
  lock-check` target.

### Fixed (2026-04-14 session)

- **Fetch timeouts — "results on schedule or fail loudly"**: the 2026-04-14
  07:00 `com.comad.ear-ingest` run hung 4h29m on a single un-timed
  `fetch()`. New `brain/packages/search/src/fetch-util.ts` wraps every
  outbound HTTP call (`fetchWithTimeout`) with AbortSignal + retry +
  optional job-wide deadline. ear-ingest gets per-query 60s timeout,
  45m job deadline, 60s heartbeat. launchd plists now emit
  `ExitTimeOut=60` + `AbandonProcessGroup=true`; all 10 live agents
  patched + reloaded. ear-ingest also closes the neo4j driver in a
  finally block so the process actually exits (was lingering with an
  ESTABLISHED bolt socket).
- **Offline-first ReportGenerator**: `ReportGenerator(llm=None)` used to
  auto-instantiate a live `LLMClient()`, which tried to connect to
  Ollama and timed out 120s (blamed 33 tests). Now `llm=None` means
  offline; the `_llm` property raises `_NoLLMConfigured` which the
  existing per-section try/except blocks degrade to empty strings. 70
  tests pass in 0.08s.
- **PR 3 dead-code hotfix**: the ADR 0002 PR 3 overrides-merge logic
  had been edited into `eye/config.py` (root) but every callsite
  imports `from utils.config` — the merge had never run. Ported to
  the canonical `eye/utils/config.py`, removed 9 orphan duplicates
  (1,640 LOC deleted), and added a Structure Guard rule to prevent
  recurrence.
- **Voice `install.sh` shellcheck**: `read -p` on lines 138 + 160 gains
  `-r` (SC2162). Voice Bats test 12 now passes.
- **Doc drift**: README + `docs/MCP_TOOLS.md` + `docs/system-intro.html`
  corrected against actual counts — 3 phantom brain MCP tools
  (`_impact_v2`, `_graph_export`, `_ontology_meta`) removed; RSS 22 →
  31, MCP tools brain 20+ → 19, Tests "2,800+ (152 + 2,664)" →
  "1,388+ (200 + 1,188)".

- **ADR 0002 — `comad.config.yaml` Contract** (`docs/adr/0002-config-contract.md`, **Accepted**): canonical JSON Schema (`schema/comad.config.schema.json`) validated against the live config plus all four presets. `make validate-config` (local) and a new CI job (`config-schema-validation` inside Structure Guard) catch typos, missing required fields, and type drift in under two seconds. Follow-up PRs 2–4 (apply-config generalization, per-module typed loaders, codegen) tracked in the ADR.
- **ADR 0001 — Repository Strategy** (`docs/adr/0001-repository-strategy.md`): ratifies "documented hybrid" (nested module `.git` repos kept; umbrella owns wiring + `comad.lock`). Defines the Root=wiring / Module=owned-by-its-git / `comad.lock`=authoritative contract plus three trigger conditions that would force a revisit.
- **Structure Guard CI** (`.github/workflows/structure-guard.yml`): enforces ADR 0001 at PR time — rejects root-level `eye/*.yaml` that shadow `eye/config/`, rejects `eye/test_*.py` orphans, validates `VERSION` semver, checks `comad.lock` module directories exist, and blocks any tracked `__pycache__` / `node_modules` / `.next` / `*.tsbuildinfo` / `*.pyc`.
- **`scripts/lib/common.sh`**: shared shell helpers (colors, `info`/`warn`/`fail`/`step`/`die`, `comad_resolve_script_dir`, git/tool helpers) sourced by `clean-runtime.sh` and `render-templates.sh`. Upgrader and installer will migrate in a follow-up.
- **Repo cleanup**: 7 root-level YAML duplicates deleted from `eye/` (all were byte-identical with `eye/config/`), 59 orphan `eye/test_*.py` files deleted (canonical path is `eye/tests/`), and `eye/tsconfig.tsbuildinfo` untracked. Root `Makefile` + `scripts/clean-runtime.sh` provide dry-run preview and `--deep` mode (3.6 GB reclaimable). `.gitignore` extended for `*.tsbuildinfo`, `data/{scores,benchmarks,runtime}/`, runtime logs. `eye/frontend` ESLint errors reduced 25 → 0.
- **Path-agnostic install**: clone the repo to any folder under any name and everything keeps working. `scripts/comad` follows its symlink to derive the repo root, `scripts/upgrade.sh` uses `BASH_SOURCE`, `brain/scripts/launchd/install.sh` derives `PROJECT` from `${0:A:h}` and detects `node`/`bun` via `command -v` (no more `/Users/<author>` hardcoding). The new `scripts/render-templates.sh` replaces `{{COMAD_ROOT}}` placeholders in `*.example` files at install/upgrade time — first user is `sleep/.mcp.json.example`, which the renderer materializes into the gitignored `sleep/.mcp.json` so each machine gets its own absolute path.
- **`comad` global command**: `scripts/comad` dispatcher installed by `install.sh` as `~/.local/bin/comad`. Resolves its underlying repo via symlink, so you can run `comad upgrade`, `comad status`, `comad backups`, `comad rollback <ts>`, `comad lock`, `comad where`, `comad version`, `comad help` from any directory. Subcommands delegate to `scripts/upgrade.sh` where applicable.
- **Upgrader**: `scripts/upgrade.sh` for one-command upgrades of an existing installation. Handles main repo + six module repos (brain/ear/eye/photo/sleep/voice), re-installs deps (bun/pip/npm), redeploys agents, and re-applies `comad.config.yaml` via `apply-config.sh`. Dirty working trees abort by default (use `--force` to override). `--dry-run` previews without writing, `--rollback <ts>` restores prior snapshots. Every run snapshots `comad.config.yaml` / `comad.lock` / `VERSION` / `.env` / `~/.claude/agents/` into `.comad/backups/<ts>/` before touching anything. Per-module success/failure + elapsed time printed at the end, plus a CHANGELOG excerpt since the previous `VERSION`.
- **VERSION + comad.lock**: root `VERSION` file (semver) and `comad.lock` pinning every module repo's branch and SHA. `scripts/upgrade.sh --lock` regenerates the lockfile from current working-copy SHAs.
- **Upgrade smoke CI**: `.github/workflows/upgrade-smoke.yml` validates `scripts/upgrade.sh` syntax, exercises `--dry-run --force`, `--help`, `--list-backups`, and `--lock` on every PR that touches the upgrader.
- Eye frontend: AI-crawler-readable pages. `/analysis` and `/report` are now server components that inline the analysis data into the initial HTML via a `sr-only` preview (32 KB full report SSR-rendered), with per-page `generateMetadata` driven by the actual findings. OpenGraph + JSON-LD (`SoftwareApplication`) emitted from the root layout. `public/robots.txt` added with explicit Allow for GPTBot, ChatGPT-User, ClaudeBot, Claude-Web, PerplexityBot, Google-Extended. Paste a report URL into any AI and it can read and summarize it without JS execution.
- Eye MCP server: 7 tools (analyze, preflight, Q&A, jobs, report, lenses, status)
- Photo auto-launch: Photoshop opens automatically via computer-use when needed
- All modules now auto-trigger via natural language (no slash commands required)
- 4 MCP servers auto-connect on session start (brain, eye, sleep, photoshop)
- Content guard: prompt injection detection on crawled content (10 threat patterns + invisible Unicode)
- Multi-source search: npm, PyPI, arXiv alongside GitHub
- Neo4j graph storage for search reference cards
- Config-driven relevance scoring from comad.config.yaml
- Weekly CRON for automatic /search PUSH mode
- Explorer package for interactive graph visualization
- CHANGELOG.md

### Fixed
- MCP server: Cypher injection prevention (allowlist validation)
- MCP server: try-catch on all 20 tool handlers
- MCP server: parameterized LIMIT clauses
- Ear daily digest: moved from broken launchd cron to bot session
- Crawlers now load from comad.config.yaml (were hardcoded)
- GeekNews importer archive path corrected
- Sleep MCP: added missing zod dependency
- Eye: enabled_lenses config field now functional
- GitHub crawler: GITHUB_TOKEN injected in cron scripts

### Changed
- Test count updated: 2,800+ (Brain 152 + Eye 2,664)
- Ear "추가 리소스" section now explicitly optional

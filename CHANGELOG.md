# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added
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

# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added
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

<h1 align="center">Comad World</h1>

<p align="center">
  <strong>A self-evolving personal knowledge system —<br>what you read automatically improves your tools.</strong>
</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="License: MIT"></a>
  <img src="https://img.shields.io/badge/Claude%20Code-compatible-blueviolet" alt="Claude Code">
  <img src="https://img.shields.io/badge/config--driven-yes-22D3EE" alt="Config Driven">
</p>

<p align="center">
  6 AI agents that <b>crawl → understand → simulate → curate → remember → evolve</b><br>
  Two feedback loops: the system improves itself, and improves your coding.<br>
  Change one YAML file, get a whole new knowledge system.
</p>

<p align="center">
  <a href="#quickstart">Quickstart</a> · <a href="#architecture">Architecture</a> · <a href="#modules">Modules</a> · <a href="#customization">Customization</a> · <a href="#presets">Presets</a>
</p>

<p align="center">
  <img src="docs/demo.gif" alt="Comad World Demo" width="720">
</p>

---

## What You Get

| | Without Comad World | With Comad World |
|---|---|---|
| **Collecting** | Manually check 20+ sites, forget half | `ear` auto-detects and archives from RSS, HN, arXiv, GitHub |
| **Organizing** | Bookmarks pile up, no connections | `brain` builds a knowledge graph — 10,000+ nodes, searchable via GraphRAG |
| **Analyzing** | Read each article, form opinions alone | `eye` runs simulations through 5 core strategic lenses (tiered system), tracks prediction accuracy |
| **Remembering** | Context lost between sessions | `sleep` consolidates memory, `voice` automates recurring workflows |

<details>
<summary><b>Key numbers from a real deployment</b></summary>

- **60,000+** graph nodes, **150,000+** relationships from ongoing crawling
- **22** RSS feeds monitored (OpenAI, Anthropic, Google, Meta, arXiv, researcher blogs)
- **30+ MCP tools** across 4 servers (brain 20+, eye 7, sleep 2, photoshop) — all auto-connected
- **Entity-level confidence scoring** (0.0–1.0) for trust boundary tracking
- **Content guard** — injection detection on all crawled content (10 threat patterns)
- **Built-in performance monitoring** via `comad_brain_perf` MCP tool
- **$0/day** additional cost with Claude Max subscription (all LLM calls via CLI, local Ollama for eye)
- **2,800+** tests across all modules (Brain 152 + Eye 2,664)

</details>

---

## 🌍 What is Comad World?

Comad World is a modular AI agent system built on [Claude Code](https://docs.anthropic.com/en/docs/claude-code). It connects six specialized agents into a pipeline that collects information, builds a knowledge graph, runs simulations, curates content, manages memory, and automates workflows — all driven by a single configuration file.

```
ear (listen) → brain (think) → eye (predict)
                  ↑
photo (edit)    sleep (remember)    voice (automate)
```

**The key idea:** every domain-specific setting lives in `comad.config.yaml`. Swap the config, and the entire system adapts — from what RSS feeds to crawl, to what arXiv categories to watch, to how articles are classified.

---

## Quickstart

### Prerequisites

- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) (Claude Max subscription recommended)
- [Docker](https://docker.com/) (for Neo4j)
- [Bun](https://bun.sh/) (for brain module)
- [Python 3.13+](https://python.org/) (for eye module)

```bash
git clone https://github.com/kinkos1234/comad-world.git
cd comad-world
cp presets/ai-ml.yaml comad.config.yaml   # or: web-dev, finance, biotech
./install.sh
```

Then start collecting knowledge:

```bash
cd brain && docker compose up -d && bun install && bun run setup
bun run crawl:hn && bun run crawl:ingest   # crawl & ingest
bun run mcp                                 # start MCP server
```

---

## Demo: Swap a Preset, Change Everything

```bash
# Start with AI/ML preset
$ head -5 comad.config.yaml
profile:
  name: "Comad AI Lab"
  language: "en"
  description: "AI/ML knowledge system"

# Crawl AI sources (22 RSS feeds, 10 arXiv categories)
$ cd brain && bun run crawl:hn
[hn-crawler] Keywords: 48, RSS feeds: 22, HN queries: 8
[hn-crawler] HN stories: 347
[hn-crawler] RSS results: 412
[hn-crawler] Wrote 583 articles to data/articles-crawl.json

# Now switch to Finance
$ cp presets/finance.yaml comad.config.yaml
$ ./scripts/apply-config.sh
  ✓ ear/interests.md
  ✓ ear/CLAUDE.md

# Same crawl command, completely different sources
$ bun run crawl:hn
[hn-crawler] Keywords: 31, RSS feeds: 10, HN queries: 7
[hn-crawler] HN stories: 89
[hn-crawler] RSS results: 156
[hn-crawler] Wrote 201 articles to data/articles-crawl.json

# ear/interests.md automatically updated:
$ head -6 ear/interests.md
# User Interest Profile
## High Priority (Core Focus)
- Quantitative Finance (QuantConnect, Zipline, Backtrader)
- Market Data / Analysis
- DeFi / Crypto
- Risk Management
```

One YAML change. Different feeds, different keywords, different categories, different relevance criteria.

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                  comad.config.yaml                   │
│  (interests, sources, keywords, categories, stack)   │
└───────────┬───────────┬───────────┬─────────────────┘
            │           │           │
    ┌───────▼──┐  ┌─────▼────┐  ┌──▼──────┐
    │   ear    │  │  brain   │  │  eye    │
    │ (curate) │→ │ (graph)  │→ │(predict)│
    └──────────┘  └──────────┘  └─────────┘
                       │
    ┌──────────┐  ┌────▼─────┐  ┌─────────┐
    │  photo   │  │  sleep   │  │  voice  │
    │  (edit)  │  │(remember)│  │(automate│
    └──────────┘  └──────────┘  └─────────┘
```

### Data Flow

All modules are accessible via natural language — no slash commands needed. 4 MCP servers auto-connect on session start.

1. **Ear** detects articles in Discord, classifies relevance using your interests, archives to markdown
2. **Brain** crawls RSS/arXiv/GitHub filtered by your keywords, builds a Neo4j knowledge graph with entities and relationships. Content guard scans all crawled data. JS-heavy pages automatically rendered via **Browse**
3. **Eye** takes any text, converts to ontology, runs multi-round simulations, generates analysis through 5 core strategic lenses with prediction tracking (7 MCP tools)
4. **Photo** corrects images via Photoshop MCP — auto-launches Photoshop when needed (domain-agnostic)
5. **Sleep** consolidates Claude Code memory across all projects (domain-agnostic)
6. **Voice** provides workflow automation triggers for Claude Code (domain-agnostic)
7. **Search** discovers repos across GitHub/npm/PyPI/arXiv, evaluates them, generates adoption plans, tests in sandbox — the system improves itself

### What's Config-Driven vs. Domain-Agnostic

| Module | Config-Driven | Domain-Agnostic |
|--------|:---:|:---:|
| **ear** | interests, categories, must-read stack, relevance thresholds | archive format, Discord integration, digest generation |
| **brain** | RSS feeds, HN queries, arXiv categories, GitHub topics, entity extraction prompts | Neo4j schema, GraphRAG, MCP tools, MetaEdge engine |
| **eye** | — | entire engine: ontology, simulation, 5 tiered lenses, prediction tracking |
| **photo** | — | everything (works with any photo) |
| **sleep** | — | everything (manages any Claude Code memory) |
| **voice** | — | everything (workflow triggers are generic) |

---

## Modules

### Brain — Knowledge Graph & GraphRAG

Neo4j-based knowledge graph that crawls, extracts entities, and answers questions via MCP.

- **20+ MCP tools** for querying, searching, and analyzing the graph
- **Dual-retriever GraphRAG** — Local + Global + Temporal 3-way search with quality benchmark (20 fixed questions)
- **MetaEdge engine** — 10 rules for automated relationship inference
- **Entity & claim confidence** — every node scored 0.0–1.0 (explicit mention=0.9+, inferred=0.6–0.8, uncertain=0.3–0.5)
- **Claim tracking** — fact/opinion/prediction with confidence scores, decay, and timelines
- **Performance monitoring** — latency tracking for all MCP tools, GraphRAG pipeline, and crawlers
- **Community detection** — hierarchical clustering for topic discovery
- **Content guard** — prompt injection detection on all crawled content (10 threat patterns + invisible Unicode scanning)
- **Config-driven crawlers** — RSS, arXiv, GitHub crawlers load sources from `comad.config.yaml`

```bash
cd brain
bun install && bun run setup
bun run mcp  # Start MCP server
```

### Ear — Content Curator

Discord bot that detects articles, classifies relevance, and archives with structured metadata.

- **3-tier relevance**: Must-Read (~15%) → Recommended (~65%) → Reference (~20%)
- **Configurable categories** from `comad.config.yaml`
- **Daily digest** auto-generation in HTML (generated on bot session start)
- **YAML frontmatter** for every archived article

### Eye — Prediction Simulation Engine

Ontology-based simulation that converts text to knowledge graph and runs multi-round impact analysis.

- **6 analytical spaces**: hierarchy, temporal, recursive, structural, causal, cross-space
- **Tiered lens system**: 5 core (Sun Tzu, Adam Smith, Taleb, Kahneman, Meadows) + 2 optional (Clausewitz, Darwin) + 3 legacy
- **Prediction tracking**: closed-loop learning — records predictions with verification deadlines, measures accuracy over time
- **Full pipeline**: ingestion → graph → community → simulation → analysis → report
- **7 MCP tools**: analyze, preflight, Q&A, jobs, report, lenses, status — all callable via natural language
- **Web UI**: FastAPI backend + Next.js frontend

```bash
cd eye
pip install -r requirements.txt
make dev  # API (port 8000) + Frontend (port 3000)
```

### Photo — AI Photo Correction

Claude Code agent for photo editing via Photoshop MCP. Auto-launches Photoshop when needed.

- **Auto-launch**: detects Photoshop state, opens via computer-use if not running
- **Non-destructive** editing with backup
- **PIL → Camera Raw → Advanced** priority chain
- **Over-correction guard**: MAE > 20 triggers parameter reduction
- No domain-specific config needed

### Sleep — Memory Consolidation

Agent that cleans up Claude Code auto-memory files across all projects.

- **Merge duplicates**, prune stale refs, clean transient notes
- **Backup first** — timestamped backup with verification before any changes
- **Dry-run mode** — preview without writing
- Trigger: say `dream` in Claude Code

```bash
# Install
cp sleep/comad-sleep.md ~/.claude/agents/
```

### Voice — Workflow Automation

Claude Code harness with auto-triggered workflows.

- **6 triggers**: onboarding, review, full-cycle, parallel detection, repo polish, session save
- **Review Army**: 5 parallel specialist reviewers with adaptive gating
- **Browser QA**: headless testing for navigation, forms, responsive, performance
- **Zero dependencies** — pure markdown/bash
- **Non-developer friendly** — "just say what you want"

```bash
# Install
cd voice && ./install.sh
```

### Browse — Headless Browser

Standalone browser automation for AI agents. Anti-bot stealth, 16 commands.

- **Auto-fallback**: brain/ear use it when native HTTP fetch returns insufficient content
- **Anti-bot stealth**: UA masking, WebDriver flag removal
- **Snapshot @refs**: `@e3 [button] "Submit"` → `click @e3`
- **Minimal**: 787 LOC, Playwright only dependency

```bash
cd browse && bun install
bun run src/cli.ts goto https://example.com
bun run src/cli.ts text  # rendered text extraction
```

### Search — Self-Evolving Reference Discovery

GitHub repo discovery → evaluation → adoption planning → sandbox testing. The system finds patterns to improve itself.

- **Multi-source search**: GitHub, npm, PyPI, and arXiv (papers with code) searched in parallel
- **3-axis evaluation**: trust (stars/forks/activity), quality (tests/CI/README), relevance (config-driven keywords from `comad.config.yaml`)
- **Neo4j graph storage**: reference cards stored as graph nodes for cross-referencing with brain entities
- **Adoption planning**: maps discovered patterns to concrete file changes with risk assessment
- **Sandbox testing**: git worktree isolation for safe verification before merging
- **Self-supervised learning**: git survival analysis tracks whether adopted patterns survive or get reverted
- **Weekly CRON**: automatic PUSH mode diagnosis every Monday
- **6 anti-signals**: marketing README, no license, abandoned repos, star manipulation

```bash
cd brain
bun run packages/search/src/cli.ts "knowledge graph MCP"            # search
bun run packages/search/src/cli.ts "RAG pipeline" --plan             # + adoption plans
bun run packages/search/src/cli.ts "MCP server" --apply 1 --dry-run  # sandbox preview
bun run packages/search/src/cli.ts --stats                           # health dashboard
```

---

## Customization

### Quick: Use a Preset

```bash
cp presets/ai-ml.yaml comad.config.yaml     # AI / Machine Learning
cp presets/web-dev.yaml comad.config.yaml    # Web Development
cp presets/finance.yaml comad.config.yaml    # Finance / Fintech
cp presets/biotech.yaml comad.config.yaml    # Biotech / Life Sciences
```

### Custom: Edit comad.config.yaml

The config file has 5 main sections:

#### 1. Interests (drives ear relevance + brain filtering)

```yaml
interests:
  high:
    - name: "Your Core Topic"
      keywords: ["keyword1", "keyword2", "keyword3"]
      examples: ["Tool A, Tool B, Framework C"]
  medium:
    - name: "Secondary Interest"
      keywords: ["keyword4", "keyword5"]
  low:
    - name: "Filter This Out"
      keywords: ["noise1", "noise2"]
```

#### 2. Sources (drives brain crawlers)

```yaml
sources:
  rss_feeds:
    - { name: "Blog Name", url: "https://example.com/feed.xml" }
  arxiv:
    - { category: "cs.CL", keywords: ["relevant", "terms"], max_results: 500 }
  github:
    topics: ["your-topic", "another-topic"]
    search_queries: ["your search query"]
```

#### 3. Categories (drives ear tagging)

```yaml
categories:
  - "Category A"
  - "Category B"
  - "Category C"
```

#### 4. Must-Read Stack (drives ear priority)

```yaml
must_read_stack:
  - "Tool you use daily"
  - "Framework you depend on"
```

#### 5. Entity Extraction (drives brain knowledge modeling)

```yaml
brain:
  entity_extraction:
    domain_hint: "describe your domain in one sentence"
    relationship_types:
      - "USES_TECHNOLOGY"
      - "COMPETES_WITH"
      - "YOUR_CUSTOM_RELATION"
```

### Create Your Own Preset

1. Copy an existing preset: `cp presets/ai-ml.yaml presets/my-domain.yaml`
2. Edit all sections to match your domain
3. Copy to root: `cp presets/my-domain.yaml comad.config.yaml`
4. Run `./scripts/apply-config.sh` to regenerate module configs

---

## Presets

| Preset | Domain | RSS Feeds | arXiv Categories | GitHub Topics |
|--------|--------|:---------:|:----------------:|:-------------:|
| `ai-ml.yaml` | AI / Machine Learning | 22 | 10 | 20 |
| `web-dev.yaml` | Web Development | 15 | — | 15 |
| `finance.yaml` | Finance / Fintech | 10 | 6 | 10 |
| `biotech.yaml` | Biotech / Life Sciences | 8 | 5 | 10 |

Want to add a preset? PRs welcome.

---

## Project Structure

```
comad-world/
├── comad.config.yaml        # YOUR config (edit this)
├── presets/                  # Ready-made domain configs
│   ├── ai-ml.yaml
│   ├── web-dev.yaml
│   ├── finance.yaml
│   └── biotech.yaml
├── brain/                   # Knowledge graph (Bun/TypeScript)
│   ├── packages/
│   │   ├── core/            # Neo4j client, entity extraction, MetaEdge
│   │   ├── crawler/         # RSS, arXiv, GitHub crawlers (config-driven)
│   │   ├── graphrag/        # Dual-retriever search engine
│   │   ├── ingester/        # Content importer
│   │   ├── mcp-server/      # 20+ MCP tools
│   │   ├── search/          # Self-evolving reference discovery
│   │   └── explorer/        # Interactive graph visualization (D3.js)
│   ├── docker-compose.yml
│   └── package.json
├── ear/                     # Content curator (Claude Code agent)
│   ├── archive/             # Archived articles (YAML frontmatter)
│   ├── digests/             # Daily digest HTML
│   └── templates/           # CLAUDE.md + interests.md templates
├── eye/                     # Simulation engine (Python/FastAPI/Next.js)
│   ├── api/                 # FastAPI backend
│   ├── frontend/            # Next.js web UI
│   ├── config/              # Engine settings
│   └── ontology/            # Domain-agnostic ontology schema
├── photo/                   # Photo correction agent
├── sleep/                   # Memory consolidation agent
├── voice/                   # Workflow automation harness
├── scripts/                 # Utility scripts
│   └── apply-config.sh      # Generate module configs from comad.config.yaml
├── install.sh               # One-command setup
└── docker-compose.yml       # Full stack (Neo4j x2 + Ollama)
```

---

## Requirements

| Component | Required | Optional |
|-----------|:--------:|:--------:|
| Claude Code | Yes | — |
| Docker | Yes (for Neo4j) | — |
| Bun | Yes (for brain) | — |
| Python 3.13+ | For eye module | — |
| Ollama | For eye (local LLM) | — |
| Adobe Photoshop | For photo module | — |
| Discord bot | For ear module | — |
| Codex CLI + tmux | For voice parallel work | — |

---

## FAQ

**Q: Do I need all modules?**
No. Each module works independently. Start with `brain` + `ear` for knowledge collection, add others as needed.

**Q: Can I add my own RSS feeds?**
Yes. Edit `sources.rss_feeds` in `comad.config.yaml` and re-run `./scripts/apply-config.sh`.

**Q: Is this only for tech topics?**
No. The `finance` and `biotech` presets demonstrate non-tech usage. The system adapts to any domain where there are RSS feeds, papers, and GitHub repos to crawl.

**Q: How much does it cost to run?**
With Claude Max subscription, additional cost is $0/day. Brain uses `claude -p --model haiku` (included in Max). Eye uses local Ollama (free). No external API calls.

**Q: Can I contribute a preset for my domain?**
Yes! See [CONTRIBUTING.md](CONTRIBUTING.md).

---

## Credits

Built with [Claude Code](https://docs.anthropic.com/en/docs/claude-code) and the [Model Context Protocol](https://modelcontextprotocol.io/).

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for all notable changes.

## License

[MIT](LICENSE)

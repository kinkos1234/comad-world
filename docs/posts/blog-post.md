# Building a Config-Driven AI Agent System That Adapts to Any Domain

Most knowledge systems are hardcoded for one domain. I built one that isn't.

**Comad World** is a modular AI agent system where 6 specialized agents — crawling, knowledge graphing, simulating, curating, remembering, and automating — all adapt to your interests via a single YAML configuration file.

GitHub: [kinkos1234/comad-world](https://github.com/kinkos1234/comad-world)

## The Problem

I started building a personal knowledge system for AI/ML research. RSS feeds from OpenAI, Anthropic, Google AI. arXiv crawlers for cs.CL and cs.AI. GitHub topic watchers for "llm" and "transformer."

It worked well. Then I wondered: what if I wanted the same system for a completely different domain — say, quantitative finance? Or biotech?

The architecture was sound, but every domain-specific value was scattered across the codebase:
- 40 AI keywords hardcoded in the HN crawler
- 25 RSS feed URLs hardcoded in a TypeScript array
- 10 arXiv category codes hardcoded with associated keywords
- 20 GitHub topics hardcoded for search
- Interest profiles hardcoded in Discord bot rules
- Entity extraction prompts assuming "technical articles"

Changing domains meant editing 6+ files across 3 different languages.

## The Solution: One Config to Rule Them All

I extracted every domain-specific value into `comad.config.yaml`:

```yaml
interests:
  high:
    - name: "Quantitative Finance"
      keywords: ["quant", "algorithmic trading", "backtesting", "alpha"]
    - name: "DeFi / Crypto"
      keywords: ["defi", "blockchain", "smart contract", "yield"]

sources:
  rss_feeds:
    - { name: "Quantocracy", url: "https://quantocracy.com/feed/" }
    - { name: "Risk.net", url: "https://www.risk.net/rss" }
  arxiv:
    - { category: "q-fin.TR", keywords: ["trading", "execution"], max_results: 200 }
  github:
    topics: ["quantitative-finance", "algorithmic-trading", "defi"]

brain:
  entity_extraction:
    domain_hint: "financial technology articles and trading systems"
    relationship_types: ["REGULATES", "COMPETES_WITH", "ACQUIRES"]
```

Now every module reads from this single file:
- **Brain crawlers** import keywords, feeds, and categories from the config
- **Ear** generates its interest profile and relevance criteria from the config
- **Eye** is already domain-agnostic (its ontology uses abstract primitives)
- **Photo, Sleep, Voice** never needed domain config

Swap `presets/ai-ml.yaml` for `presets/finance.yaml` and run `./scripts/apply-config.sh`. Done.

## The Architecture

```
                    comad.config.yaml
                         │
         ┌───────────────┼───────────────┐
         │               │               │
    ┌────▼───┐     ┌─────▼────┐    ┌─────▼───┐
    │  ear   │ →   │  brain   │ →  │  eye    │
    │(curate)│     │ (graph)  │    │(predict)│
    └────────┘     └──────────┘    └─────────┘
```

### Brain: Neo4j Knowledge Graph + GraphRAG

The brain module is a Bun/TypeScript monorepo with 5 packages:

- **core** — Neo4j client, entity extraction (via Claude API), MetaEdge engine (10 rules for automated relationship inference), claim tracking with confidence scores
- **crawler** — Config-driven crawlers for HN, arXiv, GitHub. All keywords and sources come from `comad.config.yaml`
- **graphrag** — Dual-retriever with 3-way search: Local (entity neighborhood), Global (community summaries), Temporal (time-weighted). This is what powers the `comad_brain_ask` MCP tool
- **ingester** — Imports content archives into the graph
- **mcp-server** — 15 MCP tools that connect to Claude Code / Claude Desktop

The MetaEdge engine is interesting: it defines "relationships about relationships." When the graph changes, 10 rules evaluate automatically — inferring transitive dependencies, detecting contradictions between claims, cross-verifying claims from multiple sources.

### Eye: Ontology-Based Simulation

Eye is Python/FastAPI + Next.js. It takes any text, converts it to an ontology graph, runs multi-round influence propagation, then analyzes through 10 strategic lenses:

- **Sun Tzu** — Strategic advantage (势) and misdirection (虛實)
- **Taleb** — Antifragility and Black Swan events
- **Kahneman** — Prospect theory and System 1/2 biases
- **Meadows** — 12 leverage points in complex systems
- ...and 6 more

The ontology schema is fully domain-agnostic: Actor, Artifact, Event, Environment, Concept. These primitives work whether you're analyzing AI research trends or biotech patent landscapes.

### The Preset System

4 presets ship with the project:

| Preset | RSS Feeds | arXiv Categories | GitHub Topics |
|--------|:---------:|:----------------:|:-------------:|
| AI/ML | 22 | 10 | 20 |
| Web Dev | 15 | — | 15 |
| Finance | 10 | 6 | 10 |
| Biotech | 8 | 5 | 10 |

Creating a new preset means copying an existing YAML file and editing the values. No code changes. The `apply-config.sh` script regenerates all module-specific configs.

## What I Learned

**Externalize domain knowledge early.** I wish I'd started with the config-driven approach instead of hardcoding AI keywords into arrays. The refactor wasn't hard, but it would have been trivial if planned from the start.

**Abstract ontology primitives are powerful.** Eye's schema uses generic types (Actor, Artifact, Event) instead of domain-specific ones (Paper, Framework, Researcher). This turned out to be the right call — the simulation engine works across domains without any changes.

**Each module should work independently.** Not everyone needs a simulation engine. Some people just want the knowledge graph. The modular architecture means you can start with Brain + Ear and add others later.

**QA scripts beat manual checking.** I wrote 3 automated QA scripts that verify README quality (25 checks), repo infrastructure (26 checks), and install pipeline correctness (51 checks). They caught issues I would have missed and made iteration fast.

## Try It

```bash
git clone https://github.com/kinkos1234/comad-world
cd comad-world
cp presets/ai-ml.yaml comad.config.yaml  # or: web-dev, finance, biotech
./install.sh
```

MIT licensed. PRs welcome — especially new presets for domains I haven't covered.

---

*Built with [Claude Code](https://docs.anthropic.com/en/docs/claude-code) and the [Model Context Protocol](https://modelcontextprotocol.io/).*

# Launch Strategy — 100 Stars Roadmap

## Target Timeline

| Week | Phase | Goal |
|------|-------|------|
| W1 | Pre-launch | Repo polish, working demo, GIF recording |
| W2 | Soft launch | Reddit r/ClaudeAI + r/LocalLLaMA + X post |
| W3 | HN launch | Show HN post + follow-up blog post |
| W4+ | Community | Presets from community, Discord, ongoing content |

## Pre-Launch Checklist

- [x] README score 100/100 (qa-readme.py)
- [x] Repo polish 26/26 (qa-repo.sh)
- [x] Install QA 51/51 (qa-install.sh)
- [x] 4 domain presets (ai-ml, web-dev, finance, biotech)
- [x] CI/CD pipeline
- [x] Issue/PR templates
- [x] LICENSE, CODE_OF_CONDUCT, SECURITY, CONTRIBUTING
- [ ] Working demo GIF/video (terminal recording)
- [ ] Blog post / article
- [ ] Social media accounts or project site

## Launch Channels (Priority Order)

### 1. Show HN (Target: 40-60 stars)

**Timing:** Tuesday/Wednesday 9-10 AM EST (peak HN traffic)

**Title (under 80 chars):**
```
Show HN: Comad World – Config-driven AI agent system for any domain
```

**Post body:**
```
I built a modular AI agent system on Claude Code that adapts to any domain
via a single YAML config file.

6 agents: crawl (RSS/arXiv/GitHub) → knowledge graph (Neo4j + GraphRAG) →
simulation (10 strategic lenses) → content curation → memory management →
workflow automation.

The key insight: most knowledge systems are hardcoded for one domain.
Comad World lets you swap a preset (AI/ML, web dev, finance, biotech)
and the entire pipeline adapts — what to crawl, how to classify,
what's "must-read."

Stack: Bun/TypeScript (brain), Python/FastAPI (eye), Claude Code (agents).
All config-driven, no code changes needed.

Repo: https://github.com/[user]/comad-world
```

**What makes HN upvote:**
- Novel architecture (config-driven agent system)
- Technical depth (GraphRAG, 10 strategic lenses, MetaEdge engine)
- Practical utility (actually usable, not just a demo)
- Domain flexibility (presets show breadth)

### 2. Reddit (Target: 20-30 stars)

**Subreddits:**
- r/ClaudeAI — primary audience (Claude Code users)
- r/LocalLLaMA — Ollama integration for eye module
- r/MachineLearning — knowledge graph + GraphRAG angle
- r/selfhosted — self-hosted knowledge system angle

**r/ClaudeAI post:**
```
Title: I built a 6-agent system on Claude Code that adapts to any domain via one YAML file

Been working on Comad World — a modular AI agent system where you change
one config file and the entire knowledge pipeline adapts.

What it does:
- Crawls RSS/arXiv/GitHub filtered by YOUR interests
- Builds a Neo4j knowledge graph with 20+ MCP tools
- Curates content with 3-tier relevance scoring
- Runs prediction simulations through 10 strategic lenses
- Manages Claude Code memory across projects
- Automates workflows with zero-config triggers

The cool part: swap `presets/ai-ml.yaml` for `presets/finance.yaml`
and it crawls quant papers instead of AI papers, classifies by
trading relevance instead of tech relevance, etc.

4 presets included: AI/ML, Web Dev, Finance, Biotech.
Create your own in 10 minutes.

[link to repo]
```

### 3. X / Twitter (Target: 10-20 stars)

**Thread format (5 tweets):**

```
1/ I built Comad World — a 6-agent AI system that adapts to any domain
   via a single YAML config.

   crawl → knowledge graph → simulate → curate → remember → automate

   Change one file, get a whole new knowledge system. 🧵

2/ The 6 agents:
   🧠 Brain — Neo4j knowledge graph, 20+ MCP tools, GraphRAG
   👂 Ear — Discord curator, 3-tier relevance
   👁 Eye — Simulation engine, 10 strategic lenses
   📷 Photo — AI photo correction
   💤 Sleep — Memory consolidation
   🗣 Voice — Workflow automation

3/ The key idea: one comad.config.yaml drives everything.

   interests → crawl filtering → relevance scoring → entity extraction

   4 presets: AI/ML, Web Dev, Finance, Biotech
   Or make your own in 10 min.

4/ Built on @ClaudeCode + Neo4j + Ollama.

   - Brain: Bun/TypeScript, 20+ MCP tools
   - Eye: Python/FastAPI + Next.js, runs locally
   - Everything else: just Claude Code agents

5/ Open source (MIT). Try it:

   git clone ... && cp presets/ai-ml.yaml comad.config.yaml && ./install.sh

   GitHub: [link]

   PRs welcome — especially new presets for other domains!
```

### 4. Discord Communities (Target: 5-10 stars)

- Claude Code Discord (if exists)
- MCP community Discord
- Neo4j community
- Relevant domain communities

## Demo Recording

**Tool:** `asciinema` or `vhs` (charmbracelet)

**Script:**
```
1. Show comad.config.yaml (highlight interests section)
2. Run ./install.sh (pick AI/ML preset)
3. Run bun run crawl:hn (show articles being fetched)
4. Switch preset: cp presets/finance.yaml comad.config.yaml
5. Run ./scripts/apply-config.sh (show categories change)
6. Show ear/interests.md diff (AI terms → finance terms)
```

**Duration:** 60-90 seconds

## Post-Launch

### Week 2-4: Community Building
- Respond to every issue within 24h
- Merge preset PRs quickly (low-hanging fruit for contributors)
- Write "How to create a preset" guide
- Add presets: gaming, cybersecurity, design, devops

### Month 2-3: Growth
- Blog post: "Building a config-driven AI agent system"
- Integration guides: Claude Desktop, Cursor, VS Code
- Show real knowledge graphs (screenshots of Neo4j browser)
- Performance benchmarks (crawl speed, graph size, query latency)

## Success Metrics

| Metric | Target | How to Measure |
|--------|--------|----------------|
| GitHub Stars | 100 | GitHub API |
| Forks | 15+ | Shows intent to use |
| Issues | 10+ | Shows engagement |
| PRs (external) | 5+ | Shows community |
| Preset contributions | 3+ | Shows extensibility |

## Risk Factors

| Risk | Mitigation |
|------|------------|
| "Too complex to try" | One-command install, clear preset system |
| "Just another AI wrapper" | Emphasize config-driven architecture + GraphRAG depth |
| "Only works for AI/ML" | 4 diverse presets prove domain flexibility |
| "Needs too many deps" | Each module works independently |
| "Where's the demo?" | Terminal recording in README + screenshots |

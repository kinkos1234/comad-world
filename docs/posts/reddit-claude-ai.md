# Reddit r/ClaudeAI Post

**Subreddit:** r/ClaudeAI

---

**Title:**

```
I built a 6-agent system on Claude Code that adapts to any domain via one YAML file
```

**Body:**

```
Been working on Comad World — a modular AI agent system where you change one config file and the entire knowledge pipeline adapts to your interests.

**What it does:**

- 🧠 **Brain** — Crawls RSS/arXiv/GitHub filtered by YOUR keywords, builds a Neo4j knowledge graph, provides 15 MCP tools with GraphRAG (Local + Global + Temporal 3-way search)
- 👂 **Ear** — Discord bot that detects articles, classifies relevance (Must-Read / Recommended / Reference) based on your interest profile
- 👁 **Eye** — Takes any text, builds ontology graph, runs multi-round simulations through 10 strategic lenses (Sun Tzu, Taleb, Kahneman, etc.)
- 📷 **Photo** — AI photo correction via Photoshop MCP
- 💤 **Sleep** — Consolidates Claude Code memory across all projects (say "dream")
- 🗣 **Voice** — Workflow automation ("검토해봐" → full codebase diagnosis + improvement cards)

**The cool part:**

Everything domain-specific lives in `comad.config.yaml`. Swap `presets/ai-ml.yaml` for `presets/finance.yaml` and it crawls quant papers instead of AI papers, classifies by trading relevance instead of tech relevance, extracts financial entities instead of tech entities.

4 presets included: AI/ML, Web Dev, Finance, Biotech. Create your own in ~10 minutes.

Each module works independently — start with just Brain + Ear, add others as needed.

**Quick start:**

    git clone https://github.com/kinkos1234/comad-world
    cd comad-world
    cp presets/ai-ml.yaml comad.config.yaml
    ./install.sh

MIT licensed, PRs welcome — especially new presets for other domains!

GitHub: https://github.com/kinkos1234/comad-world
```

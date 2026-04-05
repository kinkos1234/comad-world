# Reddit Posts

## r/ClaudeAI

**Title:** I built a personal knowledge system with 6 Claude Code agents — it crawls RSS/arXiv, builds a Neo4j graph, and adapts to any domain via one YAML config

**Body:**

After getting tired of manually tracking AI papers and articles, I built Comad World — a modular agent system where Claude Code agents work together to collect, organize, and analyze information automatically.

**What it does:**
- **ear** — monitors 22+ RSS feeds and auto-archives relevant articles
- **brain** — extracts entities and builds a Neo4j knowledge graph (3,000+ nodes), queryable via 15 MCP tools
- **eye** — runs simulations through 10 strategic lenses (Taleb, Kahneman, Sun Tzu, etc.)
- **photo** — AI photo correction via Photoshop MCP
- **sleep** — memory consolidation (like defrag for Claude's context)
- **voice** — workflow automation with keyword triggers

**The key feature:** everything domain-specific lives in `comad.config.yaml`. Swap a preset and all 6 agents adapt — different RSS feeds, different keywords, different entity types. 4 presets included: AI/ML, Web Dev, Finance, Biotech.

Real deployment: $0.60/day operating cost, 1,422 tests, MIT licensed.

GitHub: https://github.com/kinkos1234/comad-world

Would love to hear if anyone tries a custom preset for their domain!

---

## r/sideproject

**Title:** Comad World — 6 AI agents that build a personal knowledge graph for any domain you care about

**Body:**

Built this over 2 weeks. The problem: I was reading tech articles everywhere but never connecting the dots between them.

The solution: 6 specialized AI agents that crawl → organize → analyze → remember information for you. The whole system adapts to any domain by swapping one YAML config file.

Check out the demo GIF in the README: https://github.com/kinkos1234/comad-world

Stack: Claude Code, Neo4j, Bun/TypeScript, Python/FastAPI, Next.js. MIT licensed.

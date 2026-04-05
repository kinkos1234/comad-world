# Show HN Post

**Post timing:** Tuesday or Wednesday, 9-10 AM EST (6-7 AM PST)

**URL to submit:** https://github.com/kinkos1234/comad-world

---

**Title:**

```
Show HN: Comad World – 6 AI agents that adapt to any domain via one YAML config
```

**Text:**

```
I built a modular AI agent system on Claude Code where you change one YAML file and 6 agents adapt to your domain — what to crawl, how to classify, what entities to extract.

The pipeline:

  ear (curate) → brain (knowledge graph) → eye (simulate)
  photo (edit)   sleep (remember)          voice (automate)

Brain crawls RSS feeds, arXiv papers, and GitHub repos filtered by your interests, then builds a Neo4j knowledge graph with 15 MCP tools and a dual-retriever (Local + Global + Temporal search). Eye takes any text and runs multi-round simulations through 10 strategic lenses (Sun Tzu, Taleb, Kahneman, etc.).

The key insight: most knowledge systems are hardcoded for one domain. I externalized every domain-specific value into comad.config.yaml — keywords, RSS feeds, arXiv categories, GitHub topics, relevance criteria, entity extraction prompts. Swap a preset and the entire system adapts.

4 presets included: AI/ML (22 RSS feeds, 10 arXiv categories), Web Dev, Finance, Biotech. Creating a custom preset takes about 10 minutes.

Stack: Bun/TypeScript (brain), Python/FastAPI + Next.js (eye), Neo4j (graph), Ollama (local LLM). Each module works independently.

https://github.com/kinkos1234/comad-world
```

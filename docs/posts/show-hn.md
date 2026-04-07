# Show HN Post

**Post timing:** Tuesday or Wednesday, 9-10 AM EST (6-7 AM PST)

**URL to submit:** https://github.com/kinkos1234/comad-world

---

**Title:**

```
Show HN: Comad World – Config-driven knowledge system with 6 AI agents, self-evolving repo discovery
```

**Text (first comment):**

```
I was drowning in tech articles. Read something on HN, forgot about it, found the same article a month later. So I built a system that crawls RSS, arXiv, and GitHub for me, extracts entities into a Neo4j knowledge graph, and lets me query everything with natural language.

The twist: everything domain-specific lives in one YAML config file. Swap it, and the same system tracks finance, biotech, web dev — whatever you care about.

What it does:

  ear → auto-curates articles from 22+ RSS feeds
  brain → builds a confidence-scored knowledge graph (60K+ nodes), queryable via 20+ MCP tools
  eye → runs simulations through 5 core strategic lenses (tiered system: Taleb, Kahneman, Sun Tzu, Adam Smith, Meadows), tracks prediction accuracy
  /search → self-evolving repo discovery: finds GitHub repos, evaluates (trust/quality/relevance), generates adoption plans, tests in sandbox, tracks survival
  + photo (AI image editing), sleep (memory consolidation), voice (workflow automation)

The /search skill is what makes it self-evolving: it finds patterns from other repos to improve itself, tests them in isolated git worktrees, and tracks whether adopted patterns survive or get reverted. It's a closed learning loop.

Demo GIF in the README shows the full flow: clone → configure → crawl → query.

Real numbers: 60K+ nodes, 150K+ relationships, $0.60/day, 1,482 tests, every query <100ms, entity confidence scoring (0.0-1.0), built-in performance monitoring.

4 presets included (AI/ML, Web Dev, Finance, Biotech). Creating a custom one takes ~10 minutes — it's just YAML.

Stack: Bun/TypeScript (brain), Python/FastAPI + Next.js (eye), Neo4j, Claude Code. Each module works independently. Designed with input from 6 AI scholar perspectives (Karpathy, Amodei, Sutskever, LeCun, Hickey, Carmack).

Would love feedback on the self-evolving approach and config-driven architecture.
```

---

## Checklist

- [x] Demo GIF in README
- [x] Graph visualization screenshot
- [x] "What You Get" before/after section
- [x] Concrete headline (not abstract)
- [ ] Post on HN (Tuesday AM EST)
- [ ] First comment ready (paste text above)
- [ ] Reddit cross-post (r/ClaudeAI, r/sideproject)
- [ ] Dev.to blog post
- [ ] GeekNews Korean post

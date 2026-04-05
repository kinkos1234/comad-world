# Show HN Post

**Post timing:** Tuesday or Wednesday, 9-10 AM EST (6-7 AM PST)

**URL to submit:** https://github.com/kinkos1234/comad-world

---

**Title:**

```
Show HN: Comad World – Personal knowledge graph that crawls your domain (config-driven, 6 AI agents)
```

**Text (first comment):**

```
I was drowning in tech articles. Read something on HN, forgot about it, found the same article a month later. So I built a system that crawls RSS, arXiv, and GitHub for me, extracts entities into a Neo4j knowledge graph, and lets me query everything with natural language.

The twist: everything domain-specific lives in one YAML config file. Swap it, and the same system tracks finance, biotech, web dev — whatever you care about.

What it does:

  ear → auto-curates articles from 22+ RSS feeds
  brain → builds a knowledge graph (3,000+ nodes), queryable via 15 MCP tools
  eye → runs simulations through 10 strategic lenses (Taleb, Kahneman, Sun Tzu, etc.)
  + photo (image editing), sleep (memory consolidation), voice (workflow automation)

Demo GIF in the README shows the full flow: clone → configure → crawl → query.

Real numbers from my deployment: 3,070 nodes, 4,147 relationships, $0.60/day operating cost, 1,422 tests.

4 presets included (AI/ML, Web Dev, Finance, Biotech). Creating a custom one takes ~10 minutes — it's just YAML.

Stack: Bun/TypeScript (brain), Python/FastAPI + Next.js (eye), Neo4j, Claude Code. Each module works independently.

Would love feedback on the config-driven approach. Is this something you'd use for your domain?
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

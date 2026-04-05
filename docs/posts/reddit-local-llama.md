# Reddit r/LocalLLaMA Post

**Subreddit:** r/LocalLLaMA

---

**Title:**

```
Config-driven knowledge system with Ollama: crawl → graph → simulate → curate (open source)
```

**Body:**

```
Built an open-source system that uses Ollama for local inference in a knowledge simulation pipeline.

**How Ollama fits in:**

The "Eye" module takes any text (article, report, research paper), converts it to a knowledge graph in Neo4j, then runs multi-round simulations using your local Ollama model. It analyzes through 10 strategic lenses (Sun Tzu, Taleb, Kahneman, Darwin, etc.) and generates reports.

Default model: `llama3.1:8b` — works well on Apple Silicon via MPS. No API keys needed for the simulation engine.

**The broader system (6 modules):**

- Brain — crawls RSS/arXiv/GitHub based on your interests, builds Neo4j knowledge graph with GraphRAG
- Ear — curates articles with relevance scoring
- Eye — Ollama-powered simulation engine (this is the local LLM part)
- Photo, Sleep, Voice — utility agents

**Config-driven:** One YAML file controls what to crawl and how to classify. 4 presets: AI/ML, Web Dev, Finance, Biotech.

**Stack:** Bun/TypeScript (graph), Python/FastAPI + Next.js (simulation), Neo4j, Ollama, BGE-M3 embeddings (sentence-transformers, also runs locally on MPS/CUDA).

Everything self-hosted. Zero cloud dependencies for the core pipeline.

GitHub: https://github.com/kinkos1234/comad-world
```

# Eye — Prediction Simulation Engine

Ontology-based simulation engine. Takes any text, converts to knowledge graph, runs multi-round simulations, and generates analysis reports through 10 strategic lenses.

**Fully domain-agnostic** — the ontology schema uses abstract primitives (Actor, Artifact, Event, Concept) that work for any subject matter.

## Quick Start

```bash
# 1. Start infrastructure
docker compose up -d   # Neo4j + Ollama

# 2. Install Python dependencies
pip install -r requirements.txt

# 3. Run
make dev               # API (port 8000) + Frontend (port 3000)
# or
python main.py run     # CLI pipeline
python main.py qa      # Interactive Q&A
```

## Pipeline

```
Text → Ingestion → Graph Loading → Community Detection → Simulation → Analysis → Report
```

### 6 Analytical Spaces

| Space | Weight | Focus |
|-------|--------|-------|
| Causal | 1.0 | Cause-effect chains |
| Structural | 0.9 | Dependencies, architectures |
| Temporal | 0.8 | Timeline, evolution |
| Hierarchy | 0.7 | Taxonomies, compositions |
| Cross-space | 0.6 | Multi-dimensional patterns |
| Recursive | 0.5 | Feedback loops, self-reference |

### 10 Strategic Lenses

- **Sun Tzu** — 势 (strategic advantage), 虛實 (misdirection)
- **Machiavelli** — Virtù/Fortuna, power dynamics
- **Clausewitz** — Fog of war, Schwerpunkt (decisive point)
- **Adam Smith** — Invisible hand, comparative advantage
- **Taleb** — Antifragility, Black Swan events
- **Kahneman** — Prospect theory, System 1/2 biases
- **Hegel** — Thesis/Antithesis/Synthesis dialectic
- **Darwin** — Natural selection, adaptation pressure
- **Meadows** — 12 leverage points in systems
- **Descartes** — Methodical doubt, clarity of evidence

## Stack

- Backend: Python 3.13 + FastAPI
- Frontend: Next.js (React 19)
- Database: Neo4j 5
- LLM: Ollama (local) or any OpenAI-compatible API
- Embeddings: BGE-M3 via sentence-transformers

## Environment

```bash
cp .env.example .env
# Edit NEO4J_PASSWORD, LLM_MODEL, etc.
```

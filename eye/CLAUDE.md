# ComadEye

Ontology-Native Prediction Simulation Engine. 텍스트를 지식 그래프로 변환하고 시뮬레이션 + 분석 + 리포트를 생성한다.

## Stack
- Python 3.13, FastAPI, Next.js 16 (React 19)
- Neo4j 5 (bolt://localhost:7687), Ollama (http://localhost:11434)
- Embeddings: BGE-M3 (sentence-transformers, device=mps)

## Commands
```bash
make dev                    # API + Frontend 동시 실행
make api                    # uvicorn api.server:app --reload --port 8000
make frontend               # cd frontend && npm run dev (port 3000)
docker compose up           # Full stack (Neo4j + Ollama + API + Frontend)
pytest tests/ -v --cov=utils --cov=graph --cov-report=term-missing --cov-fail-under=50
flake8 .                    # Lint
mypy utils/config.py graph/neo4j_client.py  # Type check
cd frontend && npm run lint # Frontend lint
```

## Key Directories
- `api/` — FastAPI routes (pipeline, analysis, QA, report, graph)
- `graph/` — Neo4j client, community detection, summarizer
- `ingestion/` — Text chunking, deduplication, validation
- `analysis/` — 6 analysis spaces (hierarchy, temporal, recursive, structural, causal, cross-space)
- `narration/` — Report generation, Q&A session
- `pipeline/` — Full simulation orchestrator
- `simulation/` — Event propagation engine
- `frontend/` — Next.js web UI
- `config/` — YAML config files
- `tests/` — pytest suite (17 files, 50% coverage target)

## Environment (.env)
```
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=changeme
LLM_BASE_URL=http://localhost:11434/v1
LLM_MODEL=auto
EMBEDDINGS_MODEL=BAAI/bge-m3
EMBEDDINGS_DEVICE=mps
```

## CLI (main.py)
- `python main.py run` — Full pipeline
- `python main.py qa` — Interactive Q&A
- `python main.py analyze` — 6-space analysis
- `python main.py report` — Report generation

## CI
GitHub Actions: Python lint/type/test + Frontend build. Triggers on push to main, autoresearch/** branches.

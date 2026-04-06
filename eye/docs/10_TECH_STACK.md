# 10. 기술 스택 & 환경 설정

## 1. 기술 스택 개요

| 계층 | 컴포넌트 | 도구 | 버전 | 역할 |
|------|----------|------|------|------|
| 런타임 | Python | CPython | 3.11+ | 전체 백엔드 |
| API 서버 | HTTP | FastAPI + Uvicorn | latest | REST API + SSE 스트리밍 |
| 프론트엔드 | 웹 UI | Next.js 15 (App Router) | 15.x | Tailwind CSS v4 |
| LLM | 로컬 추론 | Ollama | latest | 로컬 LLM 서빙 (모델 자동 감지) |
| LLM 모델 | 텍스트 생성 | Ollama 호환 모델 | — | 엔티티 추출, 리포트 생성, Q&A |
| 그래프 DB | 지식그래프 | Neo4j Community | 5.x | 온톨로지 저장, Cypher 쿼리 |
| 임베딩 | 벡터 생성 | sentence-transformers | latest | BGE-M3 로컬 임베딩 |
| 커뮤니티 | Leiden | python-igraph + leidenalg | latest | 계층적 커뮤니티 탐지 |
| 그래프 분석 | 알고리즘 | NetworkX | 3.x | 중심성, DAG, 사이클 탐지 |
| 벡터 검색 | 유사도 | numpy / ChromaDB | — | 코사인 유사도, 로컬 벡터 인덱스 |
| CLI | 인터페이스 | typer + rich | latest | 커맨드라인 UI |
| 설정 | 구성 관리 | PyYAML + pydantic | — | settings.yaml 파싱 + 검증 |
| 텍스트 | 한국어 처리 | kss | latest | 한국어 문장 분리 |
| 토크나이저 | 청킹 | tiktoken | latest | 토큰 수 계산 |

---

## 2. 의존성 (requirements.txt)

```
# LLM 클라이언트
openai>=1.0.0                    # Ollama OpenAI-compatible API

# 그래프 DB
neo4j>=5.0.0                     # Neo4j Python 드라이버

# 임베딩
sentence-transformers>=2.2.0     # BGE-M3 로컬 임베딩
torch>=2.0.0                     # PyTorch (임베딩 추론)

# 그래프 분석
python-igraph>=0.11.0            # Leiden 알고리즘 기반
leidenalg>=0.10.0                # Leiden 커뮤니티 탐지
networkx>=3.0                    # 그래프 분석 알고리즘

# 벡터 검색 (택 1)
numpy>=1.24.0                    # 기본 코사인 유사도
# chromadb>=0.4.0                # 선택: 영속적 벡터 인덱스

# 텍스트 처리
tiktoken>=0.5.0                  # 토큰 카운팅
kss>=6.0.0                       # 한국어 문장 분리

# CLI + 설정
typer>=0.9.0                     # CLI 프레임워크
rich>=13.0.0                     # 터미널 UI (진행률, 테이블)
pyyaml>=6.0                      # YAML 설정 파싱
pydantic>=2.0.0                  # 데이터 검증

# API 서버
fastapi>=0.100.0                 # REST API + SSE 스트리밍
uvicorn>=0.23.0                  # ASGI 서버
httpx>=0.24.0                    # HTTP 클라이언트 (Ollama 모델 감지)

# 유틸리티
orjson>=3.9.0                    # 빠른 JSON 직렬화
tqdm>=4.65.0                     # 진행률 표시
```

---

## 3. 외부 서비스 설치

### 3.1 Ollama + LLM 모델

ComadEye는 Ollama에 설치된 모델을 **자동으로 감지**합니다. `settings.yaml`의 `model: "auto"` 설정 시 사용 가능한 첫 번째 모델을 자동 선택합니다.

```bash
# Ollama 설치 (macOS)
brew install ollama

# Ollama 서버 시작
ollama serve

# 원하는 모델 다운로드 (아무 모델이나 하나 이상)
ollama pull llama3.1:8b
# 또는: ollama pull gemma3:12b
# 또는: ollama pull qwen3.5:35b-a3b

# 확인
ollama list
```

**시스템 요구사항** (모델 크기에 따라 상이):
- RAM: 최소 16GB (큰 모델은 32GB+ 권장)
- 디스크: 모델 파일 크기에 따라 다름
- GPU: Apple Silicon MPS 또는 NVIDIA CUDA (선택, CPU도 가능하나 느림)

### 3.2 Neo4j Community

```bash
# Docker로 실행 (권장)
docker run -d \
  --name comadeye-neo4j \
  -p 7474:7474 \
  -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/comadeye \
  -e NEO4J_PLUGINS='["graph-data-science", "apoc"]' \
  -v comadeye-neo4j-data:/data \
  neo4j:5-community

# 확인: http://localhost:7474 접속
# Username: neo4j / Password: comadeye
```

**필요 플러그인**:
- **APOC**: 동적 관계 생성, 유틸리티 함수
- **GDS** (Graph Data Science): Leiden, PageRank, Betweenness 등 그래프 알고리즘

### 3.3 임베딩 모델

```python
# 첫 실행 시 자동 다운로드 (~2GB)
from sentence_transformers import SentenceTransformer
model = SentenceTransformer("BAAI/bge-m3")
```

---

## 4. 프로젝트 초기화

```bash
# 1. 프로젝트 클론/생성
cd /path/to/comadeye

# 2. Python 가상환경
python3.11 -m venv .venv
source .venv/bin/activate

# 3. 의존성 설치
pip install -r requirements.txt

# 4. 디렉토리 생성
mkdir -p data/{seeds,extraction,communities,snapshots,analysis,reports,logs}
mkdir -p config

# 5. 설정 파일 생성
cp config/settings.example.yaml config/settings.yaml
# → Neo4j 비밀번호, Ollama 모델명 등 확인

# 6. Neo4j 연결 테스트
python -c "from neo4j import GraphDatabase; \
  d = GraphDatabase.driver('bolt://localhost:7687', auth=('neo4j','comadeye')); \
  d.verify_connectivity(); print('OK'); d.close()"

# 7. Ollama 연결 테스트
curl http://localhost:11434/v1/models

# 8. 시드데이터 배치
cp 01_시드데이터.txt data/seeds/
```

---

## 5. 실행 커맨드

### 5.1 CLI 구조

```bash
# 전체 파이프라인 실행 (시드데이터 → 리포트)
python main.py run seed_data.txt

# 라운드 수 지정
python main.py run seed_data.txt --rounds 15

# 리포트 출력 경로 지정
python main.py run seed_data.txt --output ./my_reports

# 리포트 생성 생략
python main.py run seed_data.txt --skip-report

# 분석만 실행 (시뮬레이션 완료 후)
python main.py analyze

# 리포트만 생성 (분석 완료 후)
python main.py report seed_data.txt

# 대화형 Q&A (세션 자동 저장/복원)
python main.py qa
```

### 5.2 웹 UI + API 서버

```bash
# 터미널 1: FastAPI 백엔드 (port 8000)
make api
# 또는: uvicorn api.server:app --reload --port 8000

# 터미널 2: Next.js 프론트엔드 (port 3000)
make frontend
# 또는: cd frontend && npm run dev
```

### 5.3 main.py 구조 (typer 기반)

```python
import typer
app = typer.Typer()

@app.command()
def run(seed: Path, rounds: int = 10, output: Path = ..., skip_report: bool = False):
    """시드 데이터 → 시뮬레이션 → 분석 → 리포트 전체 파이프라인 실행."""
    ...

@app.command()
def analyze(snapshot_dir: Path = ..., output_dir: Path = ...):
    """스냅샷 데이터에 대해 6개 분석공간을 실행한다."""
    ...

@app.command()
def report(seed: Path, analysis_dir: Path = ..., output_dir: Path = ...):
    """분석 결과에서 리포트를 생성한다."""
    ...

@app.command()
def qa(analysis_dir: Path = ...):
    """대화형 Q&A 세션을 시작한다. (세션 자동 저장/복원)"""
    ...

if __name__ == "__main__":
    app()
```

---

## 6. Docker Compose (전체 스택)

```yaml
# docker-compose.yaml
version: '3.8'

services:
  neo4j:
    image: neo4j:5-community
    ports:
      - "7474:7474"
      - "7687:7687"
    environment:
      NEO4J_AUTH: neo4j/comadeye
      NEO4J_PLUGINS: '["graph-data-science", "apoc"]'
    volumes:
      - neo4j-data:/data

volumes:
  neo4j-data:
```

Ollama는 호스트에서 직접 실행한다 (GPU 접근 필요).

---

## 7. 설정 파일 (config/settings.yaml)

```yaml
# config/settings.yaml
neo4j:
  uri: "bolt://localhost:7687"
  user: "neo4j"
  password: "comadeye"
  database: "neo4j"              # Community Edition은 기본 DB만

llm:
  base_url: "http://localhost:11434/v1"
  model: "auto"                  # "auto" = Ollama에서 자동 감지, 또는 특정 모델명 지정
  temperature: 0.3
  max_tokens: 8192
  timeout: 300

embeddings:
  model: "BAAI/bge-m3"
  device: "mps"                  # macOS: mps | Linux: cuda | 범용: cpu
  dimension: 1024
  batch_size: 32

ingestion:
  chunk_size: 600
  chunk_overlap: 100
  max_entity_types: 15
  max_relationship_types: 12
  max_retries: 3

simulation:
  max_rounds: 10
  community_refresh_interval: 3
  propagation_decay: 0.6
  propagation_max_hops: 3
  volatility_decay: 0.1
  convergence_threshold: 0.01
  max_actions_per_entity: 1

analysis:
  enabled_spaces:
    - hierarchy
    - temporal
    - recursive
    - structural
    - causal
    - cross_space

report:
  include_interviews: true
  max_interview_quotes: 3
  max_sections: 5

qa:
  max_conversation_history: 10
  vector_search_top_k: 3
  cypher_max_hops: 5

logging:
  level: "INFO"
  log_llm_calls: true            # LLM 프롬프트+응답 전문 기록
  log_dir: "data/logs"
```

---

## 8. 성능 벤치마크 목표

| 단계 | 시드 10KB 기준 | 시드 50KB 기준 |
|------|---------------|---------------|
| Layer 0 (Ingestion) | ~2분 | ~5분 |
| Layer 2 (Simulation 10R) | ~10초 | ~30초 |
| Layer 3 (Analysis) | ~30초 | ~1분 |
| Layer 4 (Report) | ~2분 | ~3분 |
| **전체** | **~5분** | **~10분** |
| Q&A 1회 | ~15초 | ~20초 |

병목: LLM 추론 속도 (모델 크기와 하드웨어에 따라 상이). 시뮬레이션·분석 자체는 수초 내 완료.

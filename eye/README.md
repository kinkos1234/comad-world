# ComadEye

**Ontology-Native Prediction Simulation Engine**

텍스트를 넣으면 그 안의 엔티티(사람, 조직, 기술 등)와 관계를 자동으로 뽑아내고, 그래프 위에서 시뮬레이션을 돌려서 "이 상황이 어떻게 흘러갈 것인가"를 분석합니다.

예를 들어 반도체 산업 뉴스 10개를 넣으면, 삼성-TSMC-NVIDIA 같은 플레이어 간 역학을 그래프로 구성하고, 영향력 전파를 시뮬레이션한 뒤, 손자병법이나 탈레브 같은 프레임워크로 재해석해서 리포트를 만들어줍니다.

---

## 주요 기능

- **3계층 온톨로지 추출** — Segment → Chunk → Merge 파이프라인으로 텍스트에서 엔티티·관계를 구조화 (1청크씩 안전한 배치 추출 + 자동 병합 + 캐시)
- **스트리밍 LLM 호출** — Ollama 네이티브 API를 stream 모드로 사용하여 대형 모델에서도 timeout 없이 안정적으로 동작. 실패 시 프롬프트 자동 축소 재시도 (60% → 40%)
- **디바이스 스펙 감지** — 서버 시작 시 RAM, CPU, GPU를 자동 감지하고 각 모델의 적합도를 판정 (SAFE / WARNING / DANGER). 과도한 모델 선택으로 인한 500 에러를 사전 방지
- **사전 진단 (Preflight)** — 시드 텍스트 입력 시 토큰 수, 예상 배치, 위험도를 실시간으로 표시. 과도한 입력을 사전에 경고
- **실시간 진행 추적** — SSE로 파이프라인 6단계 + 청크 단위 진행률 바를 실시간 표시
- **그래프 시뮬레이션** — Neo4j 위에서 영향력 전파·메타엣지·액션을 다라운드 반복
- **6개 분석공간** — Hierarchy, Temporal, Recursive, Structural, Causal, Cross-Space
- **10개 분석 렌즈** — 손자병법, 마키아벨리, 탈레브 등으로 분석 결과를 다른 각도에서 다시 읽음
- **렌즈 자동 선별** — 렌즈를 안 고르면 LLM이 시드 데이터 보고 알아서 골라줌 (3~10개)
- **하이브리드 리포트** — 코드 기반 구조 + LLM 해석을 합쳐서 마크다운 보고서 생성
- **Report Quality Gate** — 리포트 생성 후 필수 섹션 누락, 빈 섹션, 환각 여부를 자동 검증
- **Q&A** — 분석 결과를 기반으로 대화형 질의응답. 세션이 자동 저장돼서 이어서 질문 가능
- **실패 복구** — 파이프라인 실패 시 캐시 기반 재시도, 부분 결과 열람 지원
- **LLM 비용 추적** — 단계별 LLM 호출 횟수와 토큰 사용량 집계
- **분석 기록 영속화** — `data/jobs/`에 JSON 저장. 서버 재시작해도 유지됨
- **Ollama 모델 자동 감지** — 설치된 모델 자동 인식 + 디바이스 적합도 배지 표시
- **환경변수 오버라이드** — `.env` 파일로 settings.yaml 안 건드리고 설정 변경

---

## 아키텍처

```
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│   Frontend   │───▶│   FastAPI    │───▶│   Neo4j      │
│  (Next.js)   │    │   Backend    │    │   Graph DB   │
│  port 3000   │    │  port 8000   │    │  port 7687   │
└──────────────┘    └──────┬───────┘    └──────────────┘
                           │
                    ┌──────▼───────┐
                    │    Ollama    │
                    │   Local LLM  │
                    │  port 11434  │
                    └──────────────┘
```

### 파이프라인 (6단계)

```
Ingestion → Graph Loading → Community Detection → Simulation → Analysis → Report
```

| # | 이름 | 설명 |
|:-:|------|------|
| 1 | **Ingestion** | 텍스트를 세그먼트→청크로 쪼개고, LLM이 1개씩 안전하게 엔티티와 관계를 뽑아냄. 중복 제거·보강·캐시까지 |
| 2 | **Graph Loading** | 뽑아낸 엔티티+관계를 Neo4j에 넣음 |
| 3 | **Community Detection** | Leiden 알고리즘으로 엔티티 그룹(커뮤니티)을 잡고, LLM이 각 그룹을 요약 |
| 4 | **Simulation** | 영향력 전파, 메타엣지 발동, 액션 실행을 여러 라운드 반복 |
| 5 | **Analysis** | 6개 분석공간 실행 → 렌즈 딥 필터 → 교차 종합 → Key Findings |
| 6 | **Report** | 마크다운 보고서 생성 + Quality Gate 검증 |

---

## 용어 설명

| 용어 | 의미 |
|------|------|
| **온톨로지** | 엔티티(사람, 조직 등)와 관계를 구조화한 것. "삼성전자 -[경쟁]→ TSMC" 같은 그래프 |
| **시드 데이터** | 분석할 원본 텍스트. 뉴스, 보고서, 논문 등 아무 텍스트나 가능 |
| **Stance** | 엔티티의 입장/태도. -1.0(부정)~+1.0(긍정) |
| **Volatility** | 입장의 불안정성. 0.0(안정)~1.0(불안정) |
| **Propagation** | A의 변화가 연결된 B, C에게 파급되는 것 |
| **메타엣지** | 조건부 관계. "경쟁자 stance > 0.5이면 동맹 형성" 같은 규칙 |
| **분석공간** | 시뮬레이션 결과를 특정 관점(계층, 시간, 인과 등)에서 분석하는 틀 |
| **분석 렌즈** | 분석공간 결과를 손자병법, 탈레브 등의 관점으로 다시 읽는 필터 |
| **커뮤니티** | 밀접하게 연결된 엔티티 그룹. Leiden 알고리즘이 자동으로 잡아냄 |

---

## 분석 렌즈 (딥 필터)

분석공간이 "무슨 일이 일어나고 있는가"를 알려준다면, 렌즈는 "그걸 어떻게 읽을 것인가"를 담당합니다.
독립적인 분석이 아니라, 기존 분석공간 결과를 특정 사상가의 관점으로 다시 해석하는 필터입니다.

### 10개 렌즈 목록

| 분류 | 렌즈 | 사상가 | 프레임워크 | 기본 활성 |
|------|------|--------|-----------|:---------:|
| 전략/권력 | 손자 | 孫子 | 전략적 지형/세력 — 세(勢), 허실(虛實) | ✓ |
| 전략/권력 | 마키아벨리 | Machiavelli | 권력 구조 — 비르투(Virtù), 포르투나(Fortuna) | |
| 전략/권력 | 클라우제비츠 | Clausewitz | 마찰/불확실성 — 전장의 안개, 중심(Schwerpunkt) | ✓ |
| 경제/시장 | 애덤 스미스 | Adam Smith | 자원 흐름 — 보이지 않는 손, 비교우위 | |
| 경제/시장 | 탈레브 | Taleb | 리스크 — 안티프래질, 블랙스완, 꼬리 리스크 | ✓ |
| 경제/시장 | 카너먼 | Kahneman | 인지 편향 — 프로스펙트 이론, 시스템 1·2 | ✓ |
| 시스템/구조 | 헤겔 | Hegel | 변증법 — 정(These)·반(Antithese)·합(Synthese) | |
| 시스템/구조 | 다윈 | Darwin | 진화 — 자연선택, 적응, 도태 | |
| 시스템/구조 | 메도우즈 | Meadows | 시스템 사고 — 12단계 레버리지 포인트 | ✓ |
| 인식론 | 데카르트 | Descartes | 방법적 회의 — 가정 검증, 명석판명 | ✓ |

### 렌즈 선택 방식

- **수동 선택** — 프론트엔드에서 원하는 렌즈를 직접 체크/해제
- **자동 선별** — 렌즈를 선택하지 않으면 LLM이 시드 데이터와 분석 주제를 읽고 최적의 렌즈를 자동 선별
- **렌즈 예산** — 시뮬레이션 깊이 파라미터에 따라 적용할 렌즈 수가 자동 결정됨

| 프리셋 | max_rounds | 렌즈 예산 |
|--------|:----------:|:---------:|
| 빠른 탐색 | 5 | 3개 |
| 균형 | 10 | 5개 |
| 정밀 분석 | 20 | 7개 |
| 고변동성 | 15 | 7개 |

### 렌즈 처리 흐름

```
SimulationData → 5개 분석공간 → 렌즈 딥 필터 (공간별 LLM 분석) → 렌즈 교차 종합 → 교차공간 분석 → 통합 리포트
```

렌즈 하나당 5개 분석공간에 각각 전용 프롬프트가 있어서 총 50개입니다. LLM이 각 조합에 대해 JSON 형식으로 분석 결과를 만들고, 마지막에 렌즈별로 교차 종합해서 공간을 관통하는 패턴을 잡아냅니다.

---

## 시뮬레이션 파라미터

프론트엔드에서 프리셋을 고르거나 직접 숫자를 넣을 수 있습니다.

| 파라미터 | 기본값 | 의미 |
|----------|:------:|------|
| `max_rounds` | 10 | 시뮬레이션 반복 횟수. 높을수록 더 많은 전파·반응 사이클을 거침 |
| `propagation_decay` | 0.6 | 영향력이 한 단계 전파될 때마다 감쇠되는 비율 (0.6 = 60%로 줄어듦) |
| `propagation_max_hops` | 3 | 한 엔티티의 변화가 최대 몇 단계까지 전파되는지 |
| `volatility_decay` | 0.1 | 매 라운드마다 변동성이 감소하는 속도 (안정화 속도) |
| `convergence_threshold` | 0.01 | 전체 시스템 변화량이 이 값 이하가 되면 조기 종료 (수렴 판정) |

### 프리셋

| 프리셋 | rounds | decay | hops | 용도 |
|--------|:------:|:-----:|:----:|------|
| 빠른 탐색 | 5 | 0.7 | 2 | 빠른 프로토타이핑, 데이터 탐색 |
| 균형 (기본) | 10 | 0.6 | 3 | 일반 분석 |
| 정밀 분석 | 20 | 0.4 | 5 | 심층 분석, 장기 동역학 |
| 고변동성 | 15 | 0.3 | 4 | 불안정 시스템, 위기 시나리오 |

> 프리셋 외에도 각 파라미터를 직접 입력하여 최대 50 라운드까지 설정 가능합니다.

---

## 사전 요구사항

| 도구 | 버전 | 용도 | 설치 확인 |
|------|------|------|-----------|
| **Python** | 3.11+ | 백엔드, 시뮬레이션 엔진 | `python --version` |
| **Node.js** | 20+ | 프론트엔드 (Next.js) | `node --version` |
| **Neo4j** | 5.x | 그래프 데이터베이스 | Docker 또는 Neo4j Desktop |
| **Ollama** | latest | 로컬 LLM 추론 | `ollama --version` |

---

## 설치 및 실행 (처음 설정하는 경우)

### 1. 저장소 클론

```bash
git clone https://github.com/your-repo/comadeye.git
cd comadeye
```

### 2. Python 가상환경 생성

```bash
python -m venv .venv
source .venv/bin/activate   # macOS/Linux
# .venv\Scripts\activate    # Windows
```

### 3. Neo4j 실행

Docker를 사용하는 경우:

```bash
docker run -d \
  --name comadeye-neo4j \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/comadeye2026 \
  -e NEO4J_PLUGINS='["apoc"]' \
  neo4j:5-community
```

또는 [Neo4j Desktop](https://neo4j.com/download/)을 설치하여 사용할 수 있습니다.

**확인:** 브라우저에서 http://localhost:7474 접속 → neo4j/comadeye2026 로 로그인 성공하면 OK

> 비밀번호를 변경한 경우 `config/settings.yaml`의 `neo4j.password`를 맞춰 수정하세요.

### 4. Ollama 설치 및 모델 다운로드

```bash
# Ollama 설치 (macOS)
brew install ollama

# Ollama 서버 실행 (별도 터미널 또는 백그라운드로)
ollama serve &

# 모델 다운로드 (하나 이상 필요)
ollama pull llama3.1:8b         # 가볍고 빠름 (추천)
# ollama pull gemma3:12b        # 더 나은 품질
# ollama pull qwen3.5:35b-a3b   # 고품질 (GPU 메모리 필요)
```

**확인:** `ollama list`로 설치된 모델이 보이면 OK

> ComadEye는 Ollama에 설치된 모델을 **자동으로 감지**합니다. 프론트엔드 UI에서 모델을 직접 선택할 수도 있습니다.

### 5. 환경 설정

```bash
# .env 파일 생성 (선택 — settings.yaml 기본값으로도 동작합니다)
cp .env.example .env
# 필요 시 .env 파일을 열어 Neo4j 비밀번호, LLM 모델 등 수정
```

### 6. Python 의존성 설치

```bash
pip install -r requirements.txt

# FastAPI 서버 추가 의존성
pip install fastapi uvicorn httpx
```

### 7. 프론트엔드 의존성 설치

```bash
cd frontend
npm install
cd ..
```

### 8. 서버 실행

터미널 2개에서 각각 실행합니다:

```bash
# 터미널 1: FastAPI 백엔드 (port 8000)
make api

# 터미널 2: Next.js 프론트엔드 (port 3000)
make frontend
```

또는 개별 명령:

```bash
# 백엔드
uvicorn api.server:app --reload --port 8000

# 프론트엔드
cd frontend && npm run dev
```

### 9. 접속 및 확인

브라우저에서 **http://localhost:3000** 접속

사이드바가 보이고, NEW ANALYSIS를 클릭했을 때 LLM 모델 목록에 Ollama 모델이 뜨면 정상입니다.

---

## 빠른 재시작 가이드

이미 설치가 끝난 상태에서 다시 띄울 때.

```bash
# 1. Neo4j 컨테이너 시작 (이미 생성되어 있는 경우)
docker start comadeye-neo4j

# 2. Ollama 서버 시작
ollama serve &

# 3. Python 가상환경 활성화
source .venv/bin/activate

# 4. 백엔드 실행 (터미널 1)
make api

# 5. 프론트엔드 실행 (터미널 2)
make frontend
```

> 이전에 실행했던 분석 기록은 `data/jobs/`에 JSON으로 저장되어 있어 서버 재시작 후에도 Dashboard에서 확인할 수 있습니다.

**문제가 발생하면:**

| 증상 | 해결 방법 |
|------|-----------|
| Neo4j 연결 실패 | `docker ps`로 컨테이너 실행 확인 → `docker start comadeye-neo4j` |
| Ollama 모델 없음 | `ollama list`로 모델 확인 → `ollama pull llama3.1:8b` |
| 프론트엔드 빌드 에러 | `cd frontend && npm install` 후 재시작 |
| Python import 에러 | `source .venv/bin/activate` 확인 → `pip install -r requirements.txt` |
| 포트 충돌 | `lsof -i :8000` 또는 `lsof -i :3000`으로 사용 중인 프로세스 확인 후 종료 |

---

## 사용 방법

### 웹 UI (권장)

1. **http://localhost:3000** 접속
2. 좌측 사이드바에서 **NEW ANALYSIS** 클릭
3. **시드 데이터** 입력 — 분석할 텍스트를 직접 입력하거나 `.txt` 파일 업로드
4. **분석 주제** (선택) — 특정 관점에서 분석하려면 프롬프트 입력
   - 예: `"삼성전자의 AI 반도체 경쟁력에서 TSMC 대비 약점과 기회 분석"`
5. **분석 렌즈** (선택) — 적용할 지적 프레임워크 렌즈 선택
   - 미선택 시 LLM이 시드 데이터에 맞는 렌즈를 자동 선별
   - 시뮬레이션 깊이에 따라 3~10개 렌즈가 적용됨
6. **LLM 모델** 선택 — 각 모델 옆에 SAFE/WARN/DANGER 배지가 표시됨. 디바이스 RAM 대비 모델 크기를 자동 판정
7. 시뮬레이션 파라미터 조정 (프리셋 선택 또는 직접 입력, 기본값으로도 충분합니다)
8. **RUN SIMULATION** 클릭
9. 6단계 파이프라인 진행 상황 + 청크 단위 진행률 바를 실시간으로 확인
10. 완료 후 **ANALYSIS**, **REPORT**, **Q&A** 버튼으로 결과 탐색
11. 실패 시 **캐시 사용 재시도** 또는 **부분 결과 확인** 가능

### 결과 화면

- **Analysis** — 6개 분석공간 카드, Key Findings 순위, 렌즈 인사이트가 한 화면에 정리됨
- **Report** — 전체를 종합한 마크다운 보고서. 그래프 지형부터 렌즈 분석까지 포함
- **Q&A** — 분석 결과 기반으로 자유롭게 질문. 세션 자동 저장돼서 나중에 이어서 물어볼 수 있음

### CLI

```bash
# 기본 실행
python main.py run seed_data.txt

# 라운드 수 지정
python main.py run seed_data.txt --rounds 15

# 리포트 출력 경로 지정
python main.py run seed_data.txt --output ./my_reports
```

### API (curl)

```bash
# 파이프라인 실행 (렌즈 수동 선택)
curl -X POST http://localhost:8000/api/run \
  -H "Content-Type: application/json" \
  -d '{
    "seed_text": "분석할 텍스트 내용...",
    "analysis_prompt": "특정 분석 관점 (선택)",
    "model": "llama3.1:8b",
    "max_rounds": 10,
    "lenses": ["sun_tzu", "taleb", "meadows"]
  }'

# 파이프라인 실행 (렌즈 자동 선별)
curl -X POST http://localhost:8000/api/run \
  -H "Content-Type: application/json" \
  -d '{
    "seed_text": "분석할 텍스트 내용...",
    "lenses": []
  }'

# 실행 상태 스트리밍 (SSE)
curl http://localhost:8000/api/status/{job_id}

# 시스템 상태 + 사용 가능한 모델 확인
curl http://localhost:8000/api/system-status

# 분석 결과 조회
curl http://localhost:8000/api/analysis/aggregated

# 렌즈 카탈로그 조회
curl http://localhost:8000/api/analysis/lenses

# 렌즈 딥 필터 인사이트 조회
curl http://localhost:8000/api/analysis/lens-insights

# 렌즈 교차 종합 조회
curl http://localhost:8000/api/analysis/lens-cross

# Q&A
curl -X POST http://localhost:8000/api/qa/ask \
  -H "Content-Type: application/json" \
  -d '{"job_id": "abc123", "question": "핵심 발견은 무엇인가요?"}'
```

---

## 설정

### config/settings.yaml

```yaml
neo4j:
  uri: "bolt://localhost:7687"
  user: "neo4j"
  password: "comadeye2026"
  database: "neo4j"

llm:
  base_url: "http://localhost:11434/v1"
  model: "auto"              # 또는 특정 모델명 (예: "qwen3.5:32b-a3b")
  temperature: 0.3
  max_tokens: 8192
  timeout: 600             # 로컬 LLM 추론 시간 고려 (초). 스트리밍 모드 토큰 간 60초 별도 적용
  num_ctx: 8192            # Ollama 컨텍스트 윈도우 (RAM 여유에 따라 16384까지 가능)

embeddings:
  model: "BAAI/bge-m3"    # Q&A 벡터 검색에 쓰는 임베딩 모델
  device: "mps"            # Apple Silicon: mps, NVIDIA: cuda, 그 외: cpu
  dimension: 1024
  batch_size: 32

ingestion:
  chunk_size: 600          # 청크 크기
  chunk_overlap: 100
  max_entity_types: 15
  max_relationship_types: 12
  max_retries: 3

simulation:
  max_rounds: 10
  propagation_decay: 0.6
  propagation_max_hops: 3
  volatility_decay: 0.1
  convergence_threshold: 0.01

analysis:
  enabled_spaces:          # 필요 없는 공간은 빼도 됨
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
  log_llm_calls: true
  log_dir: "data/logs"
```

### LLM 모델 설정

| 설정 방식 | 동작 |
|----------|------|
| `model: "auto"` | Ollama에 설치된 첫 번째 모델 자동 선택 |
| `model: "llama3.1:8b"` | 해당 모델 사용, 없으면 자동 fallback |
| 프론트엔드 UI | /new 페이지에서 모델 목록에서 직접 선택 |

### LLM 연동 방식

ComadEye는 Ollama 네이티브 API(`/api/chat`)를 **스트리밍 모드**(`stream: true`)로 사용합니다. 토큰을 하나씩 받기 때문에 로컬 모델이 느려도 연결이 유지되며, timeout으로 인한 500 에러를 방지합니다.

| 설정 | 기본값 | 설명 |
|------|:------:|------|
| `timeout` | 600 | 전체 요청 타임아웃(초). 스트리밍 시 토큰 간 60초 read 타임아웃이 별도 적용 |
| `num_ctx` | 8192 | Ollama 컨텍스트 윈도우. RAM 여유에 따라 16384까지 가능 |

**타임아웃 자동 복구**: LLM 호출이 timeout되면 프롬프트를 자동으로 축소하여 재시도합니다 (1차: 60%, 2차: 40% + 시스템 프롬프트 축소).

> **디바이스 스펙 감지**: 서버가 시작하면 RAM, CPU, GPU를 자동으로 감지하고, 각 Ollama 모델의 파일 크기/파라미터 수를 비교하여 SAFE/WARNING/DANGER 적합도를 판정합니다. 16GB Mac에서 32B 모델을 선택하면 UI에서 경고가 표시됩니다.

### 엔티티 추출 방식 (3계층 파이프라인)

시드 텍스트를 **Segment → Chunk → Merge** 3단계로 처리합니다.

1. **Segment** — 입력 텍스트를 의미 단위로 분할
2. **Chunk Extraction** — 1개 청크씩 LLM에 보내 엔티티/관계 추출 (배치 실패 시 자동 재시도, 캐시 저장)
3. **Reduce/Merge** — 청크별 결과를 전역 온톨로지로 병합 (중복 제거, alias 통합, 신뢰도 기반 필터링)

- 청크 9개 → 9번의 LLM 호출 (1개씩 안전하게 처리)
- 실패 배치는 최대 2회 자동 재시도
- 캐시 적중 시 LLM 호출 생략 (동일 입력 재실행 시 속도 향상)
- 실시간 진행률: 프론트엔드에서 청크 완료/실패/재시도 상태를 바 형태로 표시

### 환경변수 오버라이드

`settings.yaml` 값을 환경변수로 오버라이드할 수 있습니다. `.env.example`을 참고하세요.

| 환경변수 | 설정 항목 | 기본값 |
|----------|-----------|--------|
| `NEO4J_URI` | `neo4j.uri` | `bolt://localhost:7687` |
| `NEO4J_PASSWORD` | `neo4j.password` | `comadeye2026` |
| `LLM_BASE_URL` | `llm.base_url` | `http://localhost:11434/v1` |
| `LLM_MODEL` | `llm.model` | `auto` |
| `LLM_TEMPERATURE` | `llm.temperature` | `0.3` |
| `EMBEDDINGS_MODEL` | `embeddings.model` | `BAAI/bge-m3` |
| `EMBEDDINGS_DEVICE` | `embeddings.device` | `mps` |

---

## 프로젝트 구조

```
comadeye/
├── main.py                  # CLI 진입점 (Typer)
├── requirements.txt         # Python 의존성
├── .env.example             # 환경변수 오버라이드 템플릿
├── Makefile                 # 개발 실행 명령 (make api, make frontend)
├── docker-compose.yaml      # 전체 스택 Docker 구성
├── Dockerfile.api           # FastAPI 컨테이너
│
├── config/                  # 시스템 설정
│   ├── settings.yaml        # 핵심 설정 (Neo4j, LLM, 시뮬레이션)
│   ├── meta_edges.yaml      # 메타엣지 발동 조건 정의
│   ├── action_types.yaml    # 엔티티 액션 타입 정의
│   ├── propagation_rules.yaml
│   └── ...
│
├── api/                     # FastAPI 백엔드
│   ├── server.py            # 앱 설정, CORS, 라우터
│   ├── models.py            # Pydantic 요청/응답 모델
│   └── routes/
│       ├── pipeline.py      # POST /api/run, GET /api/status
│       ├── analysis.py      # GET /api/analysis/* (분석공간 + 렌즈)
│       ├── graph.py         # GET /api/graph/* (엔티티, 관계)
│       ├── qa.py            # POST /api/qa/ask
│       └── report.py        # GET /api/report/{job_id}
│
├── frontend/                # Next.js 15 프론트엔드
│   ├── app/
│   │   ├── page.tsx         # Dashboard (최근 분석 목록, 시스템 상태)
│   │   ├── new/page.tsx     # 시드 입력 + 모델/렌즈 선택
│   │   ├── run/page.tsx     # 파이프라인 실시간 진행
│   │   ├── analysis/page.tsx # 분석 결과 대시보드
│   │   ├── report/page.tsx  # 마크다운 보고서 뷰어
│   │   └── qa/page.tsx      # 대화형 Q&A 인터페이스
│   ├── components/          # UI 컴포넌트
│   └── lib/api.ts           # API 클라이언트
│
├── ingestion/               # 시드 데이터 처리 (3계층 파이프라인)
│   ├── segmenter.py         # Layer A: 의미 단위 세그먼트 분할
│   ├── chunker.py           # 텍스트 청킹 (한국어 문장 분리 지원)
│   ├── extractor.py         # Layer B+C: 청크 추출 + 전역 병합 (진행률 콜백, 캐시)
│   ├── enricher.py          # 엔티티 속성 보강
│   └── deduplicator.py      # 중복 엔티티/관계 병합
│
├── ontology/                # 온톨로지 스키마
│   ├── schema.py            # Entity, Relationship 데이터 모델
│   ├── meta_edge_engine.py  # 조건부 메타엣지 발동 엔진
│   └── action_registry.py   # 엔티티 액션 레지스트리
│
├── graph/                   # Neo4j 그래프 관리
│   ├── neo4j_client.py      # Neo4j 드라이버 래퍼
│   ├── loader.py            # 온톨로지 → 그래프 로딩
│   ├── community.py         # Leiden 커뮤니티 탐지
│   └── summarizer.py        # LLM 기반 커뮤니티 요약
│
├── simulation/              # 시뮬레이션 엔진
│   ├── engine.py            # 핵심 시뮬레이션 루프
│   ├── propagation.py       # 영향력 전파 알고리즘
│   ├── action_resolver.py   # 액션 조건 평가 및 실행
│   ├── event_chain.py       # 이벤트 체인 추적
│   └── snapshot.py          # 라운드별 상태 스냅샷
│
├── analysis/                # 6개 분석공간 + 렌즈 딥 필터
│   ├── aggregator.py        # 통합 분석 + 렌즈 통합 + Key Findings
│   ├── lenses.py            # 10개 분석 렌즈 정의 + LensEngine
│   ├── space_hierarchy.py   # C0-C3 계층 동역학 분석
│   ├── space_temporal.py    # 시간축 패턴, 리드/래그 분석
│   ├── space_recursive.py   # 피드백 루프, 프랙탈 패턴 분석
│   ├── space_structural.py  # 네트워크 중심성, 브릿지 노드 분석
│   ├── space_causal.py      # 인과 DAG, 루트 코즈 분석
│   └── space_cross.py       # 분석공간 간 교차 상관 분석
│
├── narration/               # 리포트 + Q&A
│   ├── report_generator.py  # 하이브리드 리포트 생성기 + Quality Gate
│   ├── qa_session.py        # 대화형 Q&A (세션 자동 저장/복원)
│   └── interview_synthesizer.py  # 커뮤니티 인터뷰 종합
│
├── utils/                   # 공통 유틸리티
│   ├── config.py            # settings.yaml 로더 + 환경변수 오버라이드
│   ├── llm_client.py        # Ollama 네이티브 API 클라이언트 (스트리밍 + 프롬프트 축소 재시도)
│   ├── device.py            # 디바이스 스펙 감지 + 모델 적합도 판정 (SAFE/WARNING/DANGER)
│   ├── preflight.py         # 입력 텍스트 사전 진단 (토큰 추정, 위험도, 예상 배치)
│   ├── embeddings.py        # BGE-M3 임베딩 (벡터 검색용)
│   ├── active_metadata.py   # Active Metadata 이벤트 버스
│   └── logger.py            # 로깅 설정
│
├── docs/                    # 설계 문서
└── data/                    # 런타임 데이터 (gitignore)
    ├── jobs/                # 분석 기록 영속화 (job별 JSON)
    ├── logs/                # LLM 호출 로그
    └── analysis/            # 분석 결과 캐시
```

---

## Docker로 전체 실행

```bash
# 전체 스택 빌드 및 실행 (Neo4j + Ollama + API + Frontend)
make docker

# 종료 및 정리
make clean
```

> Docker 실행 시 Ollama 컨테이너에 GPU가 필요합니다. GPU가 없는 환경에서는 `docker-compose.yaml`의 `deploy.resources` 섹션을 제거하세요.

---

## 라이선스

MIT


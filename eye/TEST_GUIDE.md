# ComadEye 테스트 가이드

> 기능 테스트 및 사용성 테스트를 위한 실행 환경 구성, 테스트 시나리오, 예상 결과 정리

---

## 1. 환경 구성

### 1.1 사전 요구사항

| 항목 | 버전 | 비고 |
|------|------|------|
| Python | 3.11+ | `python --version` |
| Node.js | 20+ | `node --version` |
| Docker | 24+ | Neo4j 컨테이너용 |
| Ollama | latest | 로컬 LLM 서빙 |

### 1.2 인프라 실행 순서

```bash
# 프로젝트 루트로 이동
cd comadeye

# Step 1: Neo4j 실행 (Docker)
docker compose up neo4j -d

# 연결 확인 (http://localhost:7474, 계정: neo4j / comadeye)
# 약 10~15초 후 healthy 상태 확인
docker compose ps

# Step 2: Ollama LLM 실행
ollama serve &

# 모델 확인 (아무 모델이나 하나 이상 있으면 됨)
ollama list

# 모델이 없으면 원하는 모델 pull
ollama pull llama3.1:8b
# 또는: ollama pull gemma3:12b, ollama pull qwen3.5:35b-a3b 등

# Ollama 연결 확인
curl http://localhost:11434/api/tags
```

### 1.3 Python 의존성 설치

```bash
pip install -r requirements.txt
pip install fastapi uvicorn[standard] httpx
```

### 1.4 서버 실행

```bash
# 터미널 1: FastAPI 백엔드 (port 8000)
cd comadeye
uvicorn api.server:app --reload --port 8000

# 터미널 2: Next.js 프론트엔드 (port 3000)
cd comadeye/frontend
npm run dev
```

### 1.5 설정 파일

- 경로: `config/settings.yaml` (환경변수로 오버라이드 가능, `.env.example` 참조)
- LLM: `model: "auto"` — Ollama에 설치된 모델을 자동 감지 (또는 특정 모델명 지정)
- Neo4j: `bolt://localhost:7687` (neo4j / comadeye)
- 임베딩: `BAAI/bge-m3` (MPS 디바이스)

---

## 2. API 엔드포인트 정리

| Method | URL | 기능 |
|--------|-----|------|
| GET | `http://localhost:8000/api/health` | 서버 상태 |
| GET | `http://localhost:8000/api/system-status` | Neo4j + Ollama 연결 상태 |
| POST | `http://localhost:8000/api/run` | 파이프라인 실행 (job_id 반환, analysis_prompt 선택) |
| GET | `http://localhost:8000/api/status/{job_id}` | SSE 진행 스트리밍 |
| GET | `http://localhost:8000/api/jobs` | 전체 작업 목록 |
| GET | `http://localhost:8000/api/jobs/{job_id}` | 작업 상세 |
| GET | `http://localhost:8000/api/analysis/aggregated` | 통합 분석 결과 |
| GET | `http://localhost:8000/api/analysis/{space}` | 개별 분석공간 결과 |
| GET | `http://localhost:8000/api/graph/entities` | 전체 엔티티 목록 |
| GET | `http://localhost:8000/api/graph/entity/{uid}` | 엔티티 상세 + 관계 |
| POST | `http://localhost:8000/api/qa/ask` | Q&A 질문 |
| POST | `http://localhost:8000/api/qa/reset` | Q&A 세션 초기화 |
| GET | `http://localhost:8000/api/report/{job_id}` | 마크다운 리포트 |

---

## 3. 테스트 시나리오

### 시나리오 1: 서버 헬스체크

**목적**: 모든 인프라가 정상 연결되는지 확인

```bash
# API 서버 상태
curl http://localhost:8000/api/health
# 예상: {"status":"ok","service":"comadeye"}

# 시스템 상태 (Neo4j + Ollama)
curl http://localhost:8000/api/system-status
# 예상: {"neo4j":true,"ollama":true,"llm_model":"...(자동감지된 모델명)","available_models":["model1","model2"]}

# 프론트엔드 접속
open http://localhost:3000
# 예상: Dashboard 화면, 시스템 상태 카드 3개 (neo4j connected, ollama connected, llm_model)
```

**확인 포인트**:
- [ ] API 서버 200 응답
- [ ] neo4j: true
- [ ] ollama: true
- [ ] 프론트엔드 Dashboard 렌더링

---

### 시나리오 2: 전체 파이프라인 실행 (API)

**목적**: 시드 데이터 → 분석 → 리포트까지 전체 파이프라인 API 테스트

```bash
# 파이프라인 실행 (분석 주제 없이 — 범용 분석)
curl -X POST http://localhost:8000/api/run \
  -H "Content-Type: application/json" \
  -d '{
    "seed_text": "삼성전자가 AI 반도체 시장에서 TSMC와 경쟁하고 있다. 규제 기관은 반도체 보조금 정책을 검토 중이며, 시장 수요는 증가하고 있다. 공급망 이슈로 인해 생산 차질이 우려된다.",
    "max_rounds": 5,
    "propagation_decay": 0.6,
    "max_hops": 3,
    "volatility_decay": 0.1,
    "convergence_threshold": 0.01
  }'
# 예상: {"job_id":"abc123def456","status":"pending"}

# 파이프라인 실행 (분석 주제 포함 — 주제 초점 분석)
curl -X POST http://localhost:8000/api/run \
  -H "Content-Type: application/json" \
  -d '{
    "seed_text": "삼성전자가 AI 반도체 시장에서 TSMC와 경쟁하고 있다. 규제 기관은 반도체 보조금 정책을 검토 중이며, 시장 수요는 증가하고 있다. 공급망 이슈로 인해 생산 차질이 우려된다.",
    "analysis_prompt": "삼성전자의 AI 반도체 경쟁력에서 TSMC 대비 약점과 기회 분석",
    "max_rounds": 5,
    "propagation_decay": 0.6,
    "max_hops": 3,
    "volatility_decay": 0.1,
    "convergence_threshold": 0.01
  }'
# 예상: {"job_id":"abc123def456","status":"pending"}
# analysis_prompt가 있으면 보고서 해석/인용문이 해당 주제에 초점을 맞춤
```

```bash
# SSE 스트리밍으로 진행 상태 확인 (job_id를 위 응답에서 복사)
curl -N http://localhost:8000/api/status/{job_id}
# 예상: 6개 stage (ingestion → graph → community → simulation → analysis → report) 순차 이벤트
```

**확인 포인트**:
- [ ] job_id 정상 반환
- [ ] SSE 스트리밍 6단계 순차 진행
- [ ] 각 단계별 status: running → completed 전환
- [ ] 최종 done 이벤트 수신
- [ ] `data/analysis/` 디렉토리에 JSON 결과 파일 생성 확인
- [ ] `data/reports/report.md` 생성 확인

**소요 시간**: LLM 호출 포함 약 3~10분 (모델 크기와 하드웨어에 따라 상이)

---

### 시나리오 3: 프론트엔드 전체 흐름 (E2E)

**목적**: 사용자 시점에서 UI 흐름 전체 테스트

#### Step 3-1: Dashboard 확인
1. `http://localhost:3000` 접속
2. 확인: ComadEye 로고, 사이드바, 시스템 상태 3개 카드
3. "첫 분석 시작하기" 또는 "+ new_analysis" 버튼 클릭

**확인 포인트**:
- [ ] Palantir 다크 테마 (#1A1A1A 배경)
- [ ] Oswald 폰트 (헤더), JetBrains Mono (본문)
- [ ] 오렌지(#FF6B35) + 틸(#00D4AA) 액센트 적용
- [ ] 사이드바 네비게이션 동작

#### Step 3-2: New Analysis 시드 입력
1. `/new` 페이지에서 시드 데이터 입력

**테스트 시드 데이터 (짧은 버전)**:
```
삼성전자가 AI 반도체 시장에서 TSMC와 경쟁하고 있다.
규제 기관은 반도체 보조금 정책을 검토 중이며, 시장 수요는 급증하고 있다.
공급망 이슈로 인해 생산 차질이 우려되며, 경쟁사 인텔은 파운드리 사업을 확장 중이다.
국내 반도체 장비 기업들은 수주 호조를 기록하고 있으나 원자재 가격 상승이 변수다.
```

**또는 기존 시드 파일 사용** (파일 업로드):
- `01_시드데이터.txt` — 한국 주식시장 주간 동향 리포트

2. (선택) 시드 데이터 하단의 **분석 주제** 텍스트 영역에 분석 관점 입력:
```
삼성전자의 AI 반도체 경쟁력에서 TSMC 대비 약점과 기회 분석
```
   - 입력 시: 보고서 해석/인용문이 해당 주제에 초점
   - 미입력 시: 시드데이터 기반 범용 분석

3. 우측 패널에서 설정 확인/조정:
   - max_rounds: 5 (테스트용으로 축소)
   - propagation_decay: 0.6
   - max_hops: 3
   - volatility_decay: 0.1
   - convergence_threshold: 0.01

4. "▶ RUN SIMULATION" 버튼 클릭

**확인 포인트**:
- [ ] 텍스트 입력 영역 동작
- [ ] 분석 주제 입력 영역 동작 (teal 포커스 링)
- [ ] 파일 업로드 동작 (.txt 파일)
- [ ] 설정 값 수정 가능
- [ ] RUN 버튼 클릭 → /run?job={id} 자동 이동

#### Step 3-3: Pipeline Progress 모니터링
1. `/run?job={id}` 페이지 자동 이동 확인
2. 6단계 파이프라인 진행 관찰:
   - INGESTION → GRAPH → COMMUNITY → SIMULATION → ANALYSIS → REPORT
3. 실시간 로그 출력 확인
4. 우측 통계 카드 업데이트 확인

**확인 포인트**:
- [ ] SSE 연결 → 실시간 로그 업데이트
- [ ] 스테이지 뱃지 색상 변화 (회색→오렌지→틸)
- [ ] 로그 영역 자동 스크롤
- [ ] 통계 값 (total_rounds, total_events, total_actions) 업데이트
- [ ] 완료 시 "COMPLETE" 뱃지 전환
- [ ] 완료 후 3개 네비게이션 버튼 표시: VIEW REPORT / ANALYSIS DASHBOARD / Q&A SESSION

#### Step 3-3b: Report 확인
1. 완료 후 "VIEW REPORT →" 클릭 → `/report?job={id}` 이동
2. 마크다운 보고서 렌더링 확인

**확인 포인트**:
- [ ] 보고서 제목 (h1) — 2rem, 오렌지 하단 보더
- [ ] 섹션 헤더 (h2) — 오렌지 좌측 바 + 회색 배경
- [ ] 서브 헤더 (h3) — 틸 좌측 바
- [ ] 테이블 — 라운드 코너, 호버 효과
- [ ] 인용문 (blockquote) — 틸 좌측 바, 이탤릭
- [ ] 구분선 (hr) — 그라디언트 효과
- [ ] "DOWNLOAD .MD" 버튼 → .md 파일 다운로드
- [ ] 분석 주제 입력 시 Executive Summary에 "**분석 주제**:" 표시
- [ ] 분석 주제 입력 시 해석/인용문이 해당 주제 관점 반영

#### Step 3-4: Analysis Dashboard 확인
1. `/analysis?job={id}` 페이지 확인
2. 6개 분석공간 카드 그리드 확인
3. Key Findings 랭킹 리스트 확인

**확인 포인트**:
- [ ] 6개 카드: HIERARCHY, TEMPORAL, RECURSIVE, STRUCTURAL, CAUSAL, CROSS-SPACE
- [ ] 각 카드에 신뢰도 뱃지, 요약, 핵심 수치 표시
- [ ] Key Findings 랭킹 (1~5위) 신뢰도 %와 함께 표시
- [ ] "REPORT →" 버튼으로 Report 페이지 이동
- [ ] "Q&A →" 버튼으로 Q&A 페이지 이동

#### Step 3-5: Q&A 대화
1. `/qa?job={id}` 페이지에서 질문 입력
2. 질문 예시:

```
질문 1: "삼성전자가 시스템에서 어떤 역할을 하나요?"
질문 2: "규제 기관과 삼성전자의 관계는?"
질문 3: "시스템에서 가장 영향력 있는 엔티티는?"
질문 4: "공급망 이슈의 근본 원인은?"
```

**확인 포인트**:
- [ ] 사용자 메시지 (오렌지 아바타 U) 표시
- [ ] AI 답변 (틸 아바타 C) 표시 — 수치 인용, 인과 체인 포함
- [ ] 후속 질문 칩 표시 및 클릭 동작
- [ ] 우측 Context 패널 — 관련 분석공간 표시
- [ ] 연속 대화 맥락 유지

---

### 시나리오 4: API 개별 엔드포인트 테스트

**목적**: 파이프라인 완료 후 개별 API 동작 확인

```bash
# 분석 결과 조회
curl http://localhost:8000/api/analysis/aggregated | python -m json.tool

# 개별 분석공간
curl http://localhost:8000/api/analysis/hierarchy
curl http://localhost:8000/api/analysis/temporal
curl http://localhost:8000/api/analysis/recursive
curl http://localhost:8000/api/analysis/structural
curl http://localhost:8000/api/analysis/causal
curl http://localhost:8000/api/analysis/cross_space

# 엔티티 목록
curl http://localhost:8000/api/graph/entities | python -m json.tool

# 리포트
curl http://localhost:8000/api/report/default
```

**확인 포인트**:
- [ ] aggregated.json에 key_findings, spaces, simulation_summary 포함
- [ ] 6개 분석공간 각각 JSON 응답
- [ ] 엔티티 목록에 uid, name, stance, influence_score 포함
- [ ] 리포트 마크다운 텍스트 반환

---

### 시나리오 5: 에러 처리 테스트

```bash
# 빈 시드 데이터
curl -X POST http://localhost:8000/api/run \
  -H "Content-Type: application/json" \
  -d '{"seed_text": "", "max_rounds": 5, "propagation_decay": 0.6, "max_hops": 3, "volatility_decay": 0.1, "convergence_threshold": 0.01}'
# 예상: 422 Validation Error (min_length=10)

# 존재하지 않는 분석공간
curl http://localhost:8000/api/analysis/invalid_space
# 예상: 404

# 존재하지 않는 job_id
curl http://localhost:8000/api/status/nonexistent
# 예상: {"error":"Job not found"}
```

---

## 4. 디렉토리 구조 참조

```
comadeye/
├── api/                    # FastAPI 백엔드
│   ├── server.py           # 앱 진입점
│   ├── models.py           # Pydantic 모델
│   └── routes/
│       ├── pipeline.py     # POST /api/run, GET /api/status/{id}
│       ├── analysis.py     # GET /api/analysis/*
│       ├── graph.py        # GET /api/graph/*
│       ├── qa.py           # POST /api/qa/ask
│       └── report.py       # GET /api/report/{id}
├── frontend/               # Next.js 프론트엔드
│   ├── app/
│   │   ├── layout.tsx      # 루트 레이아웃
│   │   ├── page.tsx        # Dashboard
│   │   ├── new/page.tsx    # 시드 입력
│   │   ├── run/page.tsx    # 파이프라인 진행
│   │   ├── analysis/page.tsx # 분석 대시보드
│   │   ├── report/page.tsx  # 마크다운 리포트 뷰어 + 다운로드
│   │   └── qa/page.tsx     # Q&A
│   ├── components/layout/Sidebar.tsx
│   └── lib/api.ts          # API 래퍼
├── config/settings.yaml    # 설정
├── docker-compose.yaml     # Neo4j + Ollama + API + Frontend
├── Dockerfile.api          # API 컨테이너
├── .env.example            # 환경변수 오버라이드 템플릿
└── data/                   # 런타임 데이터 (파이프라인 실행 후 생성)
    ├── extraction/         # 청크 + 추출 결과
    ├── snapshots/          # 시뮬레이션 라운드별 스냅샷
    ├── analysis/           # 6개 분석공간 + aggregated.json
    ├── reports/            # 마크다운 리포트
    ├── qa_sessions/        # Q&A 대화 이력 (자동 저장)
    └── logs/               # 로그
```

---

## 5. 알려진 제한사항

1. **Job 저장소**: 인메모리 (`_jobs` dict) — 서버 재시작 시 작업 이력 소실
2. **QA 세션**: 대화 이력은 `data/qa_sessions/{job_id}.json`에 자동 저장 — 서버 재시작 후에도 복원됨
3. **LLM 응답 시간**: 모델 크기와 하드웨어에 따라 요청당 10~60초
4. **동시 실행**: 파이프라인은 한 번에 하나씩 실행 권장 (Neo4j 리소스)
5. **CORS**: `http://localhost:3000`만 허용 (api/server.py에서 변경 가능)
6. **분석 주제(analysis_prompt)**: 리포트 생성 단계의 LLM 해석에만 반영됨. 엔티티 추출/시뮬레이션 자체에는 영향 없음

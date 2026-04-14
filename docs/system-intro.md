# COMAD System — AI Agent Ecosystem

> Claude On My Automated Desktop
> 6개의 자율 에이전트가 협력하는 AI 개발 생태계

---

## 1. 시스템 개요

COMAD는 Claude Code를 핵심 런타임으로 활용하여, 뉴스 큐레이션부터 지식 그래프, 시뮬레이션, 사진 보정, 메모리 관리, 워크플로우 자동화까지를 하나의 파이프라인으로 연결하는 **자율 에이전트 생태계**입니다.

```
ear (수집) → brain (지식화) → eye (분석/예측) → photo (창작)
                  ↕                                    ↕
              sleep (기억 정리)              voice (워크플로우 오케스트레이션)
```

### 개발 타임라인

| 시점 | 내용 |
|------|------|
| 2026-03-21 | 프로젝트 시작 (comad-eye 첫 커밋) |
| 2026-03-23 | comad-brain 시작 (Neo4j 지식 그래프) |
| 2026-03-24 | comad-voice 시작 (워크플로우 자동화) |
| 2026-03-25 | comad-sleep 시작 (메모리 관리) |
| 2026-03-30 | comad-photo 시작 (Photoshop MCP + Computer Use) |
| 2026-04-02~03 | 6개 프로젝트 전수 검토 + E2E 60건 + 트렌딩 레포 내재화 5건 |
| 2026-04-04 | 전체 고도화 완료 (테스트, 비용 최적화, 소스 밸런싱, CI 수정) |

**개발 기간: 약 2주 (2026-03-21 ~ 2026-04-04)**

### 핵심 수치

| 지표 | 값 |
|------|-----|
| 프로젝트 수 | 6개 |
| 총 소스 코드 | ~40,000 LOC (brain 9.8K + eye 30.2K + 기타) |
| 총 커밋 | 124회 |
| 그래프 규모 | 61,257 노드 / 151,837 관계 |
| 아카이브 기사 | 182건 (GeekNews + 기술 블로그) |
| 크롤링 소스 | 25개 RSS + HN API + arXiv API + GitHub API |
| 테스트 | 200개 (brain) + 1,188개 (eye) = 1,388개 (2026-04-14) |
| 일일 운영 비용 | ~$0.60 (최적화 후 87% 절감) |
| 개발 방법 | AI-assisted (Claude Code 활용, 사람은 설계/판단/검증) |

---

## 2. 프로젝트 상세

### 2-1. comad-ear — 뉴스 큐레이터 봇

**한 줄 요약:** Discord에서 GeekNews/기술 뉴스를 자동 감지하여 아카이브하는 큐레이션 봇

**기술 스택:** Claude Code Discord 채널 + Bash + Markdown (YAML frontmatter)

**구조:**
```
Discord 메시지 감지
  → WebFetch로 기사 수집
  → 관련성 3단계 분류 (필독 13% / 추천 65% / 참고 22%)
  → 마크다운 아카이브 저장 (archive/YYYY-MM-DD-slug.md)
  → "아카이브 완료!" 응답
```

**아이디어 차용 & 고도화:**
- 관련성 판별 기준은 직접 설계. 초기 필독 비율 40%로 너무 관대 → brain의 dual-retriever 스코어링 테스트에서 발견 → 4가지 엄격 기준(직접 스택 영향/보안 위협/패러다임 변화/내 프로젝트 관련)으로 강화하여 13%로 축소.

**애로사항 & 해결:**
- **스키마 드리프트:** 세션 재시작마다 frontmatter 필드명이 달라짐 (`geeknews_url` vs `geeknews`). → CLAUDE.md에 템플릿 고정 규칙 명시 + 23건 소급 수정.
- **다이제스트 크론 불안정:** crontab 기반 다이제스트 생성이 봇 비활성 시 실패. → 봇 재시작 시 자동 생성으로 전환하여 안정화.

---

### 2-2. comad-brain — 지식 그래프 & GraphRAG

**한 줄 요약:** AI/기술 분야의 기사, 논문, 레포에서 엔티티를 추출하고 Neo4j 온톨로지로 관리하며, GraphRAG로 질의응답을 제공하는 시스템

**기술 스택:** TypeScript, Bun, Neo4j 5, Claude API, MCP (12개 도구)

**구조:**
```
[수집층]  HN API + 25개 RSS + arXiv API + GitHub API + ear 아카이브
    ↓
[추출층]  Claude Haiku로 엔티티/관계/Claim 추출 (JSON 구조화)
    ↓
[그래프층] Neo4j: 13개 노드 타입, 30개 관계 타입, 22개 커뮤니티
    ↓
[추론층]  MetaEdge 10개 규칙 (추론/제약/캐스케이드)
    ↓
[검색층]  Dual-Retriever: Local + Global + Temporal 3갈래 검색
    ↓
[MCP층]   12개 도구로 Claude Desktop/Code에서 직접 질의
```

**모노레포 구조 (5개 패키지):**
- `core` — 엔티티 추출, 중복 감지, Claim 추적, UID 생성, MetaEdge 엔진
- `crawler` — HN/arXiv/GitHub 크롤러, 인제스트 파이프라인
- `graphrag` — Dual-Retriever, 엔티티 해석, 서브그래프 탐색, 답변 합성
- `ingester` — ear 아카이브 → 그래프 임포터
- `mcp-server` — MCP 프로토콜 서버 (15개 도구)

**MCP 도구 목록 (15개):**

| 도구 | 기능 |
|------|------|
| `comad_brain_ask` | GraphRAG 기반 자연어 질의 → 그래프 컨텍스트 답변 |
| `comad_brain_search` | 풀텍스트 검색 (노드 타입 필터) |
| `comad_brain_explore` | 엔티티 중심 관계 탐색 (depth 조절) |
| `comad_brain_stats` | 그래프 통계 (노드/관계 수) |
| `comad_brain_communities` | 22개 커뮤니티 목록 + 구성원 |
| `comad_brain_recent` | 최근 추가된 기사/논문 |
| `comad_brain_trend` | 트렌딩 기술/토픽 |
| `comad_brain_claims` | Claim 검색 (신뢰도 필터) |
| `comad_brain_claim_timeline` | Claim 신뢰도 시계열 추적 |
| `comad_brain_contradictions` | 상충하는 Claim 쌍 탐지 |
| `comad_brain_related` | 관련 엔티티 추천 |
| `comad_brain_impact` | 엔티티 영향도 분석 |
| `comad_brain_dedup` | 중복 엔티티 감지 + 자동 병합 |
| `comad_brain_meta` | MetaEdge 규칙 실행/조회 |
| `comad_brain_export` | 그래프 데이터 내보내기 |

**아이디어 차용 & 고도화:**

| 원본 | 차용 포인트 | COMAD 고유 개선 |
|------|------------|----------------|
| **LightRAG** | 이중 검색 (Local+Global) | Temporal 축 추가 → 3갈래 검색. Claim 신뢰도 스코어링. ear 필독 연동 (+0.2 부스트) |
| **GraphRAG (MS)** | 커뮤니티 기반 요약 | Leiden → 3단계 계층 (22개 커뮤니티). 한국어 최적화 |

**품질 지표 (2026-04-13, 50문항 벤치마크):**
- **Entity Recall 93%** — 기대 엔티티가 답변에 등장하는 비율 (이전 83%)
- **Grounding Rate 93%** — 답변 인용 엔티티가 실제 그래프에 존재하는 비율 (신규)
- **Avg Latency 13.8s** — 질문당 p50 (이전 20.7s)
- **Hard 난이도 Good 72%** — 다중 홉 추론 질문도 대부분 정답 (이전 25%)

**최근 품질 개선 (Phase A/B):**
- **Concept Expansion** — 질문에 엔티티가 직접 나타나지 않아도 연관 엔티티를 그래프 공동등장 기반으로 자동 확장. "hallucination 해결법" → RLHF, Constitutional AI, RAG 추가.
- **3KB Context Cap** — 프롬프트 토큰이 synth 지연의 주요 원인. 컨텍스트를 3KB로 제한하여 레이턴시 33% 감소.
- **Grounding Rate 지표** — 답변의 인용 엔티티가 그래프에 실제 존재하는지 검증하는 hallucination-resistant 메트릭 도입.

**애로사항 & 해결:**
- **CRLF 문제:** Windows에서 작성된 크롤러 스크립트 5개가 macOS cron에서 실행 실패. → 전체 LF 변환으로 해결.
- **크롤러 토큰 낭비:** 크론 스크립트가 `claude -p`(Sonnet)로 WebSearch를 호출 → 이미 구현된 직접 API 크롤러(HN/arXiv/GitHub)가 있었지만 사용되지 않고 있었음. → 크론 스크립트를 bun 크롤러로 교체하여 **크롤링 토큰 100% 절감 (15K/일 → 0)**.
- **HN Fetch 과다:** `--limit 30`으로 30건만 필요한데 930건을 전부 fetch. → 정렬+슬라이스를 fetch 이전으로 이동하여 **2분 29초 → 7.8초 (19배 개선)**.
- **추출 비용:** 엔티티 추출이 Sonnet으로 실행되어 일일 ~$4.50. → 구조화 추출 4곳을 Haiku로 전환, 답변 합성만 Sonnet 유지. **일일 비용 ~87% 절감**.
- **소스 편향:** HN + OpenAI Blog 편중. → 25개 RSS 균등 배분 + 다양성 캡(단일 소스 최대 30%) 적용.
- **Neo4j 메모리 부족:** 61K 노드 그래프와 eye 공유 시 트랜잭션 메모리 초과. → 힙 2GB + 트랜잭션 1GB로 확대.
- **macOS cron이 `claude -p` 인증 실패 (2026-04-13):** cron은 Aqua 세션 밖이라 OAuth keychain을 읽을 수 없어 모든 LLM 호출이 exit 1. → **크로스플랫폼 스케줄러**로 해결: macOS는 LaunchAgent(gui/uid 세션 상속), Linux/WSL은 cron(세션 keychain 전파), Windows는 Task Scheduler(`LogonType=Interactive`). 단일 `schedule-install.sh`가 OS 감지해서 라우팅. Max 구독 OAuth 그대로 사용, 추가 API 키 불필요.

**실제 시연 테스트 결과 (2026-04-04):**

질문: *"MCP란 무엇이고 어떤 기업들이 프로덕션에서 활용하고 있나?"*

- 정의: JSON-RPC 2.0 기반 오픈 표준, OAuth 2.0 통합
- 거버넌스: Anthropic → Agentic AI Foundation (Linux Foundation 산하) 기부
- 9개 기업 식별: Anthropic, OpenAI, Google, Microsoft, Block, Bloomberg, AWS, Cloudflare, Linux Foundation
- 8개 MCP 채택 제품: Claude Code, Cursor, VS Code, Gemini, ChatGPT 등
- 출처 인용 + "그래프에 없는 정보" 명시

---

### 2-3. comad-eye — 온톨로지 기반 예측 시뮬레이션 엔진

**한 줄 요약:** 텍스트에서 엔티티를 추출하고, 전파 시뮬레이션을 돌리고, 10개 분석 프레임워크(손자병법, 탈레브, 카너먼 등)로 해석하는 엔진

**기술 스택:** Python 3.13, FastAPI, Next.js 16, Neo4j 5, Ollama (로컬 LLM), BGE-M3 임베딩

**구조:**
```
텍스트 입력 (뉴스, 보고서, 논문)
  → 인제스션 (3-tier: 문장분리 → 청크 → 병합, LLM이 1청크씩 추출)
  → 그래프 로딩 (Neo4j)
  → 커뮤니티 감지 (Leiden 알고리즘 + LLM 요약)
  → 시뮬레이션 (N라운드: 엔티티 입장, 변동성, 전파)
  → 분석 (6개 공간: 계층/시간/재귀/구조/인과/교차)
  → 렌즈 심층분석 (10개 프레임워크)
  → 보고서 생성 + 품질 게이트 검증
  → Q&A 인터페이스
```

**10개 분석 렌즈:**

| 렌즈 | 관점 | 분석 초점 |
|------|------|----------|
| 손자병법 | 전략 | 경쟁 우위, 지형 분석, 허실 판단 |
| 마키아벨리 | 권력 | 이해관계자 역학, 동맹/적대 구도 |
| 클라우제비츠 | 갈등 | 마찰 요인, 전쟁의 안개, 중심점 |
| 애덤 스미스 | 경제 | 시장 메커니즘, 보이지 않는 손, 분업 |
| 탈레브 | 리스크 | 블랙스완, 안티프래질, 꼬리 리스크 |
| 카너먼 | 인지 | 시스템1/2 편향, 앵커링, 손실회피 |
| 헤겔 | 변증법 | 정-반-합, 모순의 통일, 역사적 필연 |
| 다윈 | 진화 | 적응, 자연선택, 적소 경쟁 |
| 메도우스 | 시스템 | 피드백 루프, 레버리지 포인트, 지연 효과 |
| 데카르트 | 분석 | 분해, 환원, 체계적 회의 |

**실제 시연 테스트 결과 (2026-04-04):**
- 입력: "Anthropic이 MCP를 오픈소스로 공개하면서..." (2문장)
- 파이프라인: 인제스션(4엔티티, 3관계) → 그래프 → 커뮤니티 → 시뮬레이션 10라운드 → 6공간 분석 → 보고서
- 출력: **810줄, 15개 섹션 보고서** (Executive Summary, 인과 분석, 구조 분석, 시스템 다이내믹스, 렌즈 딥 분석, 시나리오 분석, 리스크 매트릭스, 전략적 권고사항 등)
- 핵심 발견: "MCP가 3개 커뮤니티의 브릿지 노드 (신뢰도 70%)"

**아이디어 차용 & 고도화:**

| 원본 | 차용 포인트 | COMAD 고유 개선 |
|------|------------|----------------|
| **GitNexus** | Blast Radius (영향도 분석) | 다차원 영향도로 확장 — 기존 propagation.py에 코드/기술/조직 차원 추가 |

**애로사항 & 해결:**
- **venv 깨짐:** Python 3.13 업그레이드 후 기존 venv가 동작하지 않음. → venv 재생성 + shebang 수정.
- **Neo4j 포트 충돌:** brain(7688)과 eye(7687)가 동일 머신에서 운영 → settings.yaml 포트 분리.
- **장입력 안정화:** 큰 문서 처리 시 OOM 우려 → Preflight 진단, 청크 캐싱, 커뮤니티 요약 분할, 보고서 폴백 구현 (확인 결과 이미 완료 상태였음).
- **AI가 링크를 못 읽음:** 초기 프런트엔드는 모든 페이지가 `"use client"` + `useEffect` 기반이라 AI 크롤러가 빈 스켈레톤만 받았음. → `/analysis`·`/report`를 서버 컴포넌트로 전환해 백엔드 API를 SSR에서 호출, `sr-only` section에 분석 결과·전체 보고서 마크다운을 인라인. per-page `generateMetadata`로 key_findings 기반 description 생성. OpenGraph·JSON-LD·`robots.txt`(GPTBot/ClaudeBot/PerplexityBot 명시 허용) 추가. 결과: report 페이지 SSR 본문 18B → 32,297B, AI에 링크만 던져도 전체 보고서 요약 가능.

---

### 2-4. comad-photo — AI 사진 보정 에이전트

**한 줄 요약:** 사진을 분석하고 보정안을 제안한 후, 승인 시 Photoshop MCP로 비파괴 보정을 실행하는 에이전트

**기술 스택:** Claude Code Agent (33줄), Photoshop MCP, Computer Use (고급 보정)

**구조:**
```
사진 분석 (Claude Vision)
  → 보정안 카드 제안 (번호 + 내용 + 예상 효과)
  → 사용자 승인
  → 실행 (3단계 에스컬레이션)
      1. PIL — 기본 보정 (밝기/대비/채도/Auto Levels)
      2. CU Camera Raw — 프로 보정 (텍스처/명료도/디헤이즈)
      3. CU 고급 — 요청 시만 (생성형 채우기, 유동화, Neural Filters)
  → 검증 (MAE > 20 → 파라미터 축소 재시도)
  → "좋아"가 나올 때까지 반복
```

**설계 철학 — Karpathy 기준 심플리시티:**
- v0.1.0 (82줄) → v0.2.0 (65줄) → v0.3.1 (33줄)로 지속 축소
- 하드코딩 제거 후 에이전트가 오히려 더 보수적 수치 선택 (밝기 1.04~1.08 vs 이전 하드코딩 1.20)
- "에이전트 프롬프트는 짧을수록 좋다" — 원칙만 주면 LLM이 알아서 판단

**아이디어 차용:**
- Computer Use + Photoshop 조합은 자체 실험으로 도출. Camera Raw가 CU 최적 활용처임을 50장 배치 테스트로 검증.

**애로사항 & 해결:**
- **PS 2026 AppleScript 충돌:** AppleScript save가 Photoshop을 블로킹하여 CU 메뉴 고착. → CU Cmd+S만 사용하도록 규칙화.
- **Neural Filters 레이어 문제:** JPEG 저장 시 사일런트 실패. → 저장 전 반드시 레이어 병합 (Flatten) 규칙 추가.
- **PIL + Camera Raw 이중 보정:** PIL 색보정 후 Camera Raw를 쓰면 보정이 누적되어 58점. → "Camera Raw 사용 시 PIL 색보정 스킵" 규칙 추가.
- **과보정 가드:** MAE 35에서 시작 → 실전 테스트로 20으로 강화. 평균 점수 72→90 (+18점).

**실전 검증:**
- 5카테고리 × 10장 = 50장 배치 테스트 PASS
- 인물 15장 평균 92.2점, 최저 86점 (전부 85+)
- 폴더 배치 모드: 첫 1장 제안 → 승인 → 나머지 일괄 적용

---

### 2-5. comad-sleep — 메모리 정리 에이전트

**한 줄 요약:** 인간의 REM 수면처럼, 프로젝트 메모리 파일을 자동으로 스캔·중복 감지·통합·정리하는 에이전트

**기술 스택:** Claude Code Subagent (Markdown), MCP 서버 (Node.js, 122줄)

**구조:**
```
트리거 ("dream" 또는 메모리 > 150줄)
  → Phase 1: Scan (전체 프로젝트 메모리 분석, 중복/비활성 감지)
  → Phase 2: Act (백업 → 통합 → 정리 → 검증)
  → MCP 도구 2개: info(현황), history(이력)
```

**아이디어 차용 & 고도화:**

| 원본 | 차용 포인트 | COMAD 고유 개선 |
|------|------------|----------------|
| **ReMe** | 점진적 압축 정책 | 프로젝트 활성도 + 타입별 차등 + cross-project 승격 |
| **SimpleMem** | 중복 감지 | 프론트매터 필드 매칭 + 타입별 병합 전략 + 인덱스 정합성 검증 |
| **Memory-Keeper** | MCP 서버화 | info + history 2도구로 최소화 (264→120줄 축소) |

**애로사항 & 해결:**
- **Stale Lock:** 이전 세션의 `.consolidate-lock`이 남아 정리 차단. → lock 파일 자동 정리 로직 추가.
- **user_profile 분산:** 여러 프로젝트에 동일 user_profile이 산재. → cross-project 병합 전략 적용.

---

### 2-6. comad-voice — 워크플로우 오케스트레이션 하네스

**한 줄 요약:** 비개발자를 위한 Claude Code 워크플로우 자동화 레이어. 6개 트리거로 개발 프로세스를 자동 제어

**기술 스택:** Markdown 설정 (CLAUDE.md에 삽입), Claude Code 내장 기능

**구조 — 6개 자동 트리거:**

| 트리거 | 감지 | 동작 |
|--------|------|------|
| **T0 온보딩** | `.comad/` 없음 | 프로젝트 탐색 → 환영 메시지 → 안전 프로토콜 |
| **T1 검토** | "검토해봐" | 코드베이스 분석 → 3-5개 개선 카드 제시 |
| **T2 풀사이클** | "풀사이클" | RESEARCH→DECOMPOSE→EXPERIMENT→INTEGRATE→POLISH→DELIVER |
| **T3 병렬** | 독립 작업 감지 | 5-Point Checklist → 독립은 Codex 병렬, 의존은 순차 |
| **T4 광택** | "레포 정리" | README/뱃지/LICENSE/CHANGELOG/CI 자동 생성 |
| **T5 저장** | "여기까지" | 세션 요약 → .comad/sessions/ 저장 → 인수인계 |

**설계 원칙:**
- v2.1.0에서 외부 의존성(OMC, gstack) 완전 제거 → Claude Code만으로 독립 운영
- v3.0.0에서 T6~T10 확장 (현재 T0~T5 활성)

---

## 3. 시스템 간 데이터 흐름

```
[Discord]
    │
    ▼
comad-ear (아카이브)  ──────────→  comad-brain (지식 그래프)
  184건 기사                         60,827 노드
  3단계 관련성                        150,988 관계
  ├── 일일 digest HTML                12 MCP 도구
  └── ear-ingest (daily 07:00)            │
         │                                 ▼
         ▼                             comad-eye (시뮬레이션)
      /search 파이프라인                  10 분석 렌즈
      GitHub/npm/PyPI/arXiv 탐색           전파 시뮬레이션
      → 오프토픽 게이트                      보고서 생성
      → adoption plan
      → sandbox 검증
      → plan-decisions.jsonl

comad-photo (보정)  ←── Claude Vision + Photoshop MCP
  PIL → Camera Raw → 고급 보정
  MAE 가드, 배치 모드

comad-sleep (기억)  ←── 전체 프로젝트 메모리 스캔
  중복 감지, 통합, 정리
  MCP 서버 (info + history)

comad-voice (오케스트레이션)  ←── CLAUDE.md 트리거
  6개 자동 워크플로우
  비개발자 친화적 인터페이스
```

**자가진화 피드백 루프 (2026-04-13 완성):**
- `ear/archive/*.md` 필독 기사 → 기술 토큰 추출 → `/search` 쿼리 자동 생성
- `/search` 평가기 → 오프토픽(genome/finance/game)·저품질 레포 차단 게이트
- 통과한 후보 → `git worktree` sandbox → `bun install + tsc + bun test` (transient fail 시 1회 재시도)
- 결과 → `plan-decisions.jsonl`에 누적 → 다음 evolution-loop의 trend 입력

---

## 4. 공통 설계 원칙

### Karpathy 기준 심플리시티
- 과설계를 경계. 다이어그램/테이블/예시가 정말 필요한지 자문.
- "실전 N장 돌려보고, 실패에서 규칙을 추가" 접근법.
- 에이전트 프롬프트는 짧을수록 좋음 (photo: 82줄→33줄).
- 하드코딩 제거 시 LLM이 오히려 더 나은 판단을 내림.

### 외부 의존성 최소화
- 트렌딩 레포의 **구조만 차용**, 외부 의존성 0.
- LightRAG → 직접 구현한 dual-retriever (303줄)
- ReMe/SimpleMem → 직접 구현한 압축/중복 정책
- voice v2.1.0에서 OMC/gstack 완전 제거

### 비용 최적화
- 크롤링: `claude -p` Sonnet → 직접 API (토큰 100% 절감)
- 추출: Sonnet → Haiku 전환 (~67% 절감)
- HN fetch 최적화: 2분29초 → 7.8초 (19배)
- 종합 일일 비용: ~$4.50 → ~$0.60 (87% 절감)

### 실전 검증 우선
- 모든 규칙은 실전 테스트에서 도출 (photo: 50장 배치, brain: 181건 인제스트)
- E2E 테스트 60건 + brain 90개 + eye 1,332개 = **1,482개 테스트**
- CI 파이프라인: brain (TypeScript + Bun), eye (Python + Next.js), voice (BATS + markdownlint)

### 배포/업그레이드 전략 (v0.2.0, 2026-04-13)
- 루트 `VERSION` 파일(semver) + `comad.lock` (6개 모듈 branch+SHA 고정, `package-lock.json` 방식)
- `scripts/upgrade.sh`: Pre-flight(dirty tree abort, 실행 중 서비스 감지, `.env` 새 키 diff) → Snapshot(`.comad/backups/<ts>/`) → Pull(main + 6 modules) → Deps(bun/pip/npm) → Agents(voice marker 영역만 in-place 교체) → Summary + CHANGELOG 발췌. 플래그: `--dry-run`, `--force`, `--rollback <ts>`, `--list-backups`, `--lock`.
- `scripts/comad` 전역 dispatcher가 `~/.local/bin/comad` 심링크로 설치 → 어느 디렉터리에서도 `comad upgrade`, `comad status`, `comad backups`, `comad rollback <ts>` 동작.
- 설계 과정에서 8 석학 페르소나(Linus/Karpathy/House/Bach/Kondo/Rams/PG/Bush) 리뷰로 Option A/B/C 비교: B(마이그레이션 파이프라인)는 YAGNI로 첫 파괴적 변경 때 승급, C(npm 패키지)는 사용자 1,000+ 시 재고. 현재 Option A' 경량 안전 버전으로 출발.
- CI(`upgrade-smoke.yml`)가 PR마다 `--dry-run --force`, `comad help/version/where/status/backups`까지 검증.
- **경로 무관 설치 (path-agnostic)**: 레포를 어느 폴더/어느 이름으로 클론하든 동작. `scripts/comad`는 자기 심링크를 따라가서 repo root 자동 결정, `scripts/upgrade.sh`는 `BASH_SOURCE` 기준, `brain/scripts/launchd/install.sh`는 `${0:A:h}`로 PROJECT 역산 + `command -v node/bun`으로 인터프리터 감지. `scripts/render-templates.sh`가 `*.example` 안의 `{{COMAD_ROOT}}` 플레이스홀더를 install/upgrade 시점에 절대경로로 치환(첫 사례: `sleep/.mcp.json.example` → `sleep/.mcp.json`, 후자는 gitignore되어 머신별 경로가 커밋 안 됨). `/Users/<author>` 하드코딩 0건.

---

## 5. 주요 애로사항 & 해결 종합

| 분류 | 문제 | 해결 | 프로젝트 |
|------|------|------|---------|
| **환경** | CRLF → macOS cron 실패 | 전체 LF 변환 | brain |
| **환경** | Python venv 깨짐 | venv 재생성 + shebang 수정 | eye |
| **환경** | Neo4j 포트 충돌 | 포트 분리 (7687/7688) | eye/brain |
| **비용** | 크롤링에 LLM 사용 (~15K tok/일) | 이미 있던 API 크롤러로 교체 (0 tok) | brain |
| **비용** | 엔티티 추출 Sonnet 비용 | Haiku 전환 (67% ↓) | brain |
| **품질** | 필독 기준 40%로 구별력 부족 | 4가지 엄격 기준 (13%) | ear |
| **품질** | 스키마 드리프트 (frontmatter) | 템플릿 고정 + 소급 수정 | ear |
| **품질** | PIL+Camera Raw 이중 보정 (58점) | 상호 배타 규칙 추가 | photo |
| **품질** | 과보정 (MAE 35 느슨) | MAE 20 강화 (72→90점) | photo |
| **안정성** | AppleScript + CU 동시 사용 충돌 | CU 전용 저장 규칙 | photo |
| **안정성** | Discord 봇 오프라인 | LAZY 플래그 제거 + 플러그인 충돌 해결 | ear |
| **안정성** | Stale lock 파일 | 자동 정리 로직 | sleep |
| **편향** | HN + OpenAI Blog 편중 | 25 RSS 균등배분 + 30% 캡 | brain |

---

## 6. 개발 방법론 — AI-Assisted Development

### 사람의 역할 vs AI의 역할

| 사람 (설계자) | AI (Claude Code) |
|--------------|------------------|
| 시스템 아키텍처 설계 | 코드 구현 + 테스트 작성 |
| 어떤 문제를 풀 것인지 결정 | 구체적인 해법 코딩 |
| 품질 기준 설정 (MAE 20, 필독 13%) | 기준에 맞는 최적화 실행 |
| 차용할 아이디어 선정 | 차용 포인트 분석 + 자체 구현 |
| 실전 테스트 결과 판단 | 테스트 자동화 + 배치 실행 |
| 시연/발표 기획 | 문서 자동 생성 |

### AI 개발의 교훈

1. **프롬프트는 짧을수록 좋다** — comad-photo: 82줄→33줄로 축소했더니 에이전트가 오히려 더 나은 판단. 하드코딩은 LLM의 판단력을 제한함.
2. **실전 테스트에서 규칙을 도출** — 사전에 규칙을 설계하기보다, 50장 돌려보고 실패 패턴에서 규칙 추가. MAE 가드, CU 규칙, 스키마 고정 모두 이 방식.
3. **이미 있는 것을 먼저 확인** — brain 크롤러 최적화의 핵심 발견: 직접 API 크롤러가 이미 구현되어 있었지만 크론이 무시하고 `claude -p`를 사용 중이었음. 코드를 새로 쓰기 전에 기존 코드 탐색이 먼저.
4. **외부 의존성 0으로 차용** — LightRAG, ReMe, SimpleMem 등의 구조만 참고하고 직접 구현. 의존성 관리 부담 없이 핵심 아이디어만 흡수.
5. **비용은 사후에 최적화** — 먼저 동작하는 시스템을 만들고, 이후 모델 교체(Sonnet→Haiku), 아키텍처 변경(LLM 크롤링→직접 API)으로 87% 절감.

---

## 7. 시연 항목 (별도 진행)

1. **comad-ear** — Discord에서 기사 링크 공유 → 자동 아카이브
2. **comad-brain** — MCP 도구로 지식 그래프 질의 (comad_brain_ask, comad_brain_search)
3. **comad-eye** — 텍스트 입력 → 시뮬레이션 → 보고서 생성
4. **comad-photo** — 사진 보정 제안 → PIL 실행 → 결과 확인
5. **comad-sleep** — "dream" 명령 → 메모리 정리 실행
6. **comad-voice** — "풀사이클" 트리거 → 자동 파이프라인 실행

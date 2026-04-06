# ComadEye 디자인 가이드

> Palantir Foundry/AIP 디자인 언어를 기반으로 한 ComadEye CLI & 리포트 디자인 시스템

---

## 1. 디자인 철학

### 1.1 Palantir 디자인 원칙 추출

Palantir의 웹사이트/제품에서 관찰된 핵심 디자인 원칙:

| 원칙 | Palantir 적용 | ComadEye 적용 |
|------|--------------|--------------|
| **구조 우선 (Structure-first)** | Ontology를 시각적 중심에 배치, 데이터 관계를 시각적으로 표현 | 그래프 구조와 분석공간을 CLI/리포트의 핵심 시각으로 |
| **절제된 미학 (Restrained aesthetics)** | 화이트스페이스, 최소 장식, 콘텐츠 우선 | Rich 터미널 출력에서도 불필요한 장식 배제 |
| **데이터 밀도 (Data density)** | 대시보드에 많은 정보를 구조적으로 배치 | 라운드 요약, 분석 결과를 밀도 높게 표현 |
| **계층적 탐색 (Hierarchical navigation)** | 사이드바 + 브레드크럼 + 상세 패널 | CLI 계층: 전체 요약 → 패키지별 → 개별 Capability |
| **기하학적 은유 (Geometric metaphor)** | 이코사이도데카헤드론(정이십면체), 네트워크 아이콘 | 그래프 연결 구조를 ASCII 시각화 |

### 1.2 ComadEye 디자인 정체성

```
"위상학적 지능의 시각화 — 구조가 곧 인사이트"
```

- **온톨로지 구조**를 시각적 중심에 배치
- **관계의 변화**를 시간축으로 추적 가능하게 표현
- **분석 결과**를 6개 렌즈로 동시에 볼 수 있는 구조

---

## 2. 색상 체계 (Color System)

### 2.1 기본 팔레트

Palantir의 절제된 색상 + 데이터 시각화 색상 결합:

```
Core Colors (터미널 호환)
═══════════════════════════════════════════

Background  : 터미널 기본 배경 (투명/다크)
Text        : #E0E0E0 (밝은 회색, 기본 텍스트)
Muted       : #808080 (회색, 부차 정보)
Accent      : #4A90D9 (팔란티어 블루, 주요 강조)
Success     : #4CAF50 (녹색, 완료/긍정)
Warning     : #FFC107 (황색, 주의)
Error       : #F44336 (적색, 오류/부정)
Info        : #2196F3 (밝은 파랑, 정보)
```

### 2.2 의미 기반 색상 매핑

```
Stance 시각화:
  극부정(-1.0) : ████ #F44336 (red)
  부정(-0.5)   : ████ #FF7043 (orange_red)
  중립(0.0)    : ████ #808080 (grey)
  긍정(+0.5)   : ████ #66BB6A (light_green)
  극긍정(+1.0) : ████ #4CAF50 (green)

Volatility 시각화:
  안정(0.0)    : ████ #4A90D9 (blue)
  보통(0.5)    : ████ #FFC107 (yellow)
  불안정(1.0)  : ████ #F44336 (red)

CMR 성숙도:
  Level 1 (개념)  : ████ #F44336 (red)
  Level 2 (개발)  : ████ #FF9800 (orange)
  Level 3 (검증)  : ████ #FFC107 (yellow)
  Level 4 (안정)  : ████ #4CAF50 (green)
  Level 5 (성숙)  : ████ #2196F3 (blue)

커뮤니티 계층:
  C0 (최세밀)  : 각 커뮤니티별 고유색 (자동 할당)
  C1           : 고유색 밝기 -20%
  C2           : 고유색 밝기 -40%
  C3 (최상위)  : 고유색 밝기 -60%
```

---

## 3. 타이포그래피 (Typography)

### 3.1 CLI 출력 계층

```
H1: ═══ 제목 ═══ (Rich Panel, bold, accent color)
    예: ═══ ComadEye Simulation Report ═══

H2: ── 섹션 제목 ── (Rule, bold)
    예: ── Phase A: 이벤트 주입 ──

H3: ▸ 소제목 (bold, 들여쓰기 2칸)
    예:   ▸ 직접 영향 엔티티

Body: 일반 텍스트 (들여쓰기 4칸)
    예:     WTI유가: volatility 0.45 → 0.89 (+98%)

Data: 테이블/수치 (Rich Table, 모노스페이스)
    예:     │ Entity   │ Stance │ Δ      │ Volatility │
            │ WTI유가  │ -0.72  │ -0.32  │ 0.89       │

Note: 부연 설명 (dim/grey, 들여쓰기 4칸)
    예:     ℹ 전파 감쇠율: 0.6, 최대 3-hop
```

### 3.2 리포트 (.md) 타이포그래피

```
# H1: 시뮬레이션 리포트 제목
## H2: 섹션 (분석공간별)
### H3: 세부 분석
#### H4: 인터뷰 인용문

본문: 분석 서술 (LLM 생성)
> 인용: 에이전트 인터뷰 인용문
| 표: 수치 데이터 |
```

---

## 4. CLI 컴포넌트 디자인

### 4.1 진행률 표시

```
Palantir 스타일: 단계별 파이프라인 시각화

┌─────────────────────────────────────────────────┐
│  ComadEye Pipeline                              │
├─────────────────────────────────────────────────┤
│  [████████████] L0 Ingestion      ✓ 완료  1:42  │
│  [████████░░░░] L2 Simulation     ● 진행  0:08  │
│  [░░░░░░░░░░░░] L3 Analysis       ○ 대기        │
│  [░░░░░░░░░░░░] L4 Narration      ○ 대기        │
├─────────────────────────────────────────────────┤
│  LLM calls: 2/5  │  Elapsed: 1:50              │
└─────────────────────────────────────────────────┘
```

### 4.2 라운드 요약 출력

```
Round 3/10 ──────────────────────────────────────
  Events:  1 injected (유가급등)
  Actions: 4 executed (SELL ×2, FLIGHT_TO_SAFETY ×1, ANNOUNCE ×1)
  Meta-edges: 7 fired (opposition ×3, flight_to_safety ×2, alliance ×2)

  Volatility  avg=0.42 ▲  max=0.89 (WTI유가)
  Stance      +0.15 (원전섹터)  -0.22 (반도체섹터)
  Community   1 migration: 한선엔지니어링 C1_기존 → C1_에너지
  Edges       +3 OPPOSES  +1 ALLIED_WITH  -2 expired
─────────────────────────────────────────────────
```

### 4.3 Impact Analysis 출력

```
Impact Analysis: meta_edges.yaml ──────────────
  변경 영향 범위 14/18 Capabilities (78%)

  Depth 1 (직접):
    ├── meta_edge_engine ·········· CMR 3 ⚠
    └── state_transition_engine ··· CMR 3 ⚠

  Depth 2 (간접):
    ├── propagation_engine ········ CMR 3 ⚠
    ├── action_resolver ··········· CMR 3 ⚠
    ├── snapshot_writer ··········· CMR 4 ✓
    └── community_refresher ······· CMR 3 ⚠

  Depth 3+:
    ├── space_* (6개) ············· CMR 3 ⚠
    ├── aggregator ················ CMR 3 ⚠
    └── report_*, qa_session ······ CMR 2 ●

  권장: 시뮬레이션 재실행 + 리포트 재생성
────────────────────────────────────────────────
```

### 4.4 그래프 요약 출력

```
Knowledge Graph Summary ────────────────────────
  Nodes: 47  │  Edges: 128 (active: 112)
  Communities: C0=12  C1=5  C2=3  C3=1

  Top Entities (by influence):
    1. 삼성전자 ········· 0.92  stance=+0.35
    2. WTI유가 ·········· 0.87  stance=-0.72
    3. 한국은행 ·········· 0.84  stance=+0.12

  Relationship Distribution:
    INFLUENCES ···· 34 (27%)  ████████████░░░░
    DEPENDS_ON ···· 28 (22%)  ██████████░░░░░░
    REACTS_TO ····· 22 (17%)  ████████░░░░░░░░
    COMPETES_WITH · 16 (13%)  ██████░░░░░░░░░░
    others ········ 28 (22%)  ██████████░░░░░░
────────────────────────────────────────────────
```

---

## 5. 리포트 디자인

### 5.1 시뮬레이션리포트.md 구조

Palantir의 "Impact Study" 형식을 차용:

```markdown
# [시드데이터 제목] 시뮬레이션 분석 리포트

> 생성: YYYY-MM-DD | 시뮬레이션: N 라운드 | LLM 호출: M회

## 요약 (Executive Summary)
[1단락 핵심 요약]

## 1. 초기 구조 분석
[시드데이터에서 추출한 온톨로지 구조 설명]

## 2. 시뮬레이션 결과
### 2.1 핵심 이벤트 체인
### 2.2 주요 행위자 동태
### 2.3 커뮤니티 재편

## 3. 6대 분석공간 인사이트
### 3.1 계층 분석 (어느 수준에서?)
### 3.2 시간 분석 (어떤 순서로?)
### 3.3 재귀 분석 (자기강화 루프?)
### 3.4 구조 분석 (관계 구조 변화?)
### 3.5 인과 분석 (원인은?)
### 3.6 교차 분석 (창발 패턴?)

## 4. 예측 및 시나리오
### 4.1 기본 시나리오
### 4.2 상승 시나리오
### 4.3 하락 시나리오

## 5. 주요 행위자 인터뷰
> "..." — [행위자명] (stance: X, influence: Y)

---
*ComadEye v0.1.0 | Ontology-Native Prediction Engine*
```

---

## 6. ASCII 시각화 패턴

### 6.1 그래프 관계 시각화

```
주요 관계 네트워크:

  삼성전자 ──COMPETES_WITH──→ SK하이닉스
      │                          │
      │ DEPENDS_ON               │ DEPENDS_ON
      ▼                          ▼
    반도체섹터 ←──BELONGS_TO── TSMC
      │
      │ REACTS_TO
      ▼
    AI수요급증 ──LEADS_TO──→ 설비투자확대
```

### 6.2 Stance 변화 타임라인

```
Stance Timeline (삼성전자):

  +1.0 ┤
  +0.5 ┤         ╭──╮
   0.0 ┤──╮ ╭───╯  ╰──╮
  -0.5 ┤  ╰╯          ╰───
  -1.0 ┤
       └──┬──┬──┬──┬──┬──┬──
          R1 R2 R3 R4 R5 R6
```

### 6.3 커뮤니티 구조

```
Community Structure (C1 level):

  ┌─ C1_반도체 ────────────┐
  │  삼성전자, SK하이닉스    │
  │  TSMC, 인텔             │
  └────────────────────────┘
         │ INFLUENCES
         ▼
  ┌─ C1_에너지 ────────────┐
  │  한전, 두산에너빌리티    │
  │  WTI유가                │
  └────────────────────────┘
```

---

## 7. Rich 컴포넌트 매핑

ComadEye CLI에서 사용할 Rich 라이브러리 컴포넌트:

| 용도 | Rich 컴포넌트 | 예시 |
|------|-------------|------|
| 파이프라인 진행 | `Progress` + `SpinnerColumn` | L0→L4 진행률 |
| 라운드 요약 | `Panel` + `Table` | 라운드별 통계 |
| 엔티티 정보 | `Table` | stance/volatility 테이블 |
| 트리 구조 | `Tree` | 커뮤니티 계층, Impact Analysis |
| 경고/오류 | `Console.print` + `Rule` | 수렴 경고, 에러 |
| 분석 결과 | `Columns` + `Panel` | 6개 분석공간 동시 표시 |
| 그래프 요약 | `Panel` + inline bar chart | 관계 분포 |
| Q&A 대화 | `Prompt` + `Markdown` | 대화형 인터페이스 |

---

## 8. 파일 출력 규칙

### 8.1 JSONL 로그

```json
{"type":"snapshot","round":3,"timestamp":"2026-03-18T14:30:00","data":{...}}
```
- 한 줄 = 한 이벤트
- ISO 8601 타임스탬프
- `type` 필드로 이벤트 분류

### 8.2 분석 결과 JSON

```json
{
  "analysis_space": "causal",
  "version": "0.1.0",
  "generated_at": "2026-03-18T14:35:00",
  "results": { ... }
}
```
- 최상위에 메타정보 포함
- `version`으로 재현성 보장

### 8.3 리포트 Markdown

- UTF-8 인코딩
- GitHub Flavored Markdown 호환
- 표는 `|` 구분자 사용
- 인용문은 `>` 블록 사용
- 코드/수치 블록은 ` ``` ` 사용

---

## 9. 접근성 & 호환성

- **터미널 호환**: Rich의 `Console(force_terminal=True)` 사용, 256색 이상 지원
- **다크/라이트 테마**: 터미널 기본 배경색에 적응 (Rich auto-detect)
- **한국어 지원**: 폭 계산 시 동아시아 문자 2칸 처리 (`unicodedata.east_asian_width`)
- **파이프 호환**: `--no-color` 플래그로 plain text 출력 지원 (CI/파이프라인용)

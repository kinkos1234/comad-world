# 08. 리포트 생성 명세 (Layer 4 — 서술)

## 1. 목표

Layer 3의 **구조적 분석 결과**(JSON)를 기존 시뮬레이션리포트.md와 동등한 품질의 마크다운 리포트로 변환한다.

핵심 원칙: **LLM은 서술(narration)만 담당한다. 분석(analysis)은 이미 완료되어 있다.**

---

## 2. 리포트 구조

### 2.1 최종 리포트 골격

```markdown
# {시뮬레이션 주제} 시뮬레이션 보고서

> {1~2문장 요약 — 핵심 발견과 시뮬레이션 범위}

---

## {섹션 1 제목} — 인과공간에서 도출

{인과 DAG의 핵심 체인을 서술}
{근본 원인 → 중간 매개 → 최종 결과 흐름}

> "{에이전트 인용문 1}"
> — {엔티티명}, {관점 설명}

## {섹션 2 제목} — 구조공간에서 도출

{그래프 토폴로지 변화, 브릿지 노드, 중심성 변화 서술}

> "{에이전트 인용문 2}"
> — {엔티티명}, {관점 설명}

## {섹션 3 제목} — 시간공간에서 도출

{이벤트 시퀀스, 선행지표, 반응 시차 서술}

> "{에이전트 인용문 3}"
> — {엔티티명}, {관점 설명}

## {섹션 4 제목} — 재귀+계층 교차 분석에서 도출

{피드백 루프, 프랙탈 패턴, 계층 간 전파 서술}

## {섹션 5 제목} — 다중공간 창발 패턴

{교차 분석 인사이트, 메타 패턴 서술}

---

## 부록: 시뮬레이션 메타데이터

- 시드데이터: {파일명}
- 시뮬레이션 라운드: {N}
- 총 엔티티: {N} | 총 관계: {N}
- 이벤트: {N}개 | Action 실행: {N}회 | 메타엣지 발동: {N}회
- 커뮤니티 재편: {N}회
- LLM 호출: 총 {N}회
```

### 2.2 섹션 구성 원칙

1. **분석공간 기반 구성**: 각 섹션은 하나 이상의 분석공간에서 도출된 발견을 중심으로
2. **key_findings 우선**: aggregated.json의 key_findings를 rank 순으로 섹션 배정
3. **교차 분석 강조**: cross_space 인사이트는 독립 섹션 또는 관련 섹션 말미에 배치
4. **3~5개 섹션**: 지나치게 많지 않게 핵심만

---

## 3. 리포트 생성 파이프라인

```
aggregated.json
     │
     ├─[Step 1]─→ 아웃라인 생성 (LLM 1회)
     │             섹션 제목 + 각 섹션에 포함될 분석 결과 매핑
     │
     ├─[Step 2]─→ 섹션 서술 생성 (LLM 1~2회)
     │             각 섹션의 분석 JSON → 서술 텍스트
     │             에이전트 인터뷰 인용문 생성 포함
     │
     └─[Step 3]─→ 마크다운 조립 (LLM 0회)
                   템플릿 기반 최종 문서 조합
```

### 3.1 Step 1: 아웃라인 생성

**LLM 입력**:
- aggregated.json의 `key_findings` + `spaces` 요약
- 시드데이터 원문의 첫 500자 (맥락 파악용)

**LLM 출력** (JSON):
```json
{
  "title": "3월 16~22일 KOSPI 드라마틱 성장 종목 예측 시뮬레이션 보고서",
  "subtitle": "중동 사태 확산과 유가 급등을 계기로...",
  "sections": [
    {
      "title": "WTI 유가 100달러 돌파와 KOSPI 급변동의 시점 정렬 분석",
      "source_spaces": ["causal", "temporal"],
      "key_finding_ranks": [1],
      "interview_candidates": ["wti_price", "foreign_investor", "kospi"]
    },
    {
      "title": "외국인 수급 전환 신호 하에서 반도체 에이전트의 기술적 저항선 테스트",
      "source_spaces": ["structural", "recursive"],
      "key_finding_ranks": [3],
      "interview_candidates": ["samsung", "sk_hynix", "foreign_investor"]
    }
  ]
}
```

### 3.2 Step 2: 섹션 서술 생성

각 섹션에 대해 LLM에게 제공하는 컨텍스트:

```python
def build_section_context(section, analysis_results, graph):
    context = {
        # 해당 분석공간의 상세 결과
        "analysis": {
            space: analysis_results[space]
            for space in section["source_spaces"]
        },

        # 인터뷰 후보 엔티티의 속성
        "interview_entities": [
            {
                "uid": uid,
                "name": graph.get(uid).name,
                "object_type": graph.get(uid).object_type,
                "stance": graph.get(uid).stance,
                "stance_initial": snapshots[0].get(uid).stance,
                "volatility": graph.get(uid).volatility,
                "community": graph.get(uid).community_id,
                "influence_score": graph.get(uid).influence_score,
                "key_relationships": graph.get_relationships(uid, limit=5),
                "action_history": actions_log.filter(actor=uid),
            }
            for uid in section["interview_candidates"]
        ],

        # 관련 커뮤니티 요약
        "community_summaries": get_relevant_summaries(section, communities),

        # 관련 원문 청크 (근거)
        "source_chunks": get_relevant_chunks(section, chunks),
    }
    return context
```

**인터뷰 인용문 생성 규칙**:

```
LLM에게 제공하는 인용문 제약:
1. 각 인용은 해당 엔티티의 stance 값에 일관되어야 한다
   - stance > 0.3: 긍정적/낙관적 어조
   - stance < -0.3: 부정적/비관적 어조
   - -0.3 ~ 0.3: 중립적/분석적 어조

2. influence_score에 따른 어조 강도
   - 높은 영향력: 단정적, 선언적 어조
   - 낮은 영향력: 관찰적, 조심스러운 어조

3. 인용 내용은 해당 섹션의 분석 결과에 근거해야 한다
   - 인과 체인에 참여한 엔티티 → 원인-결과 관점 인용
   - 브릿지 노드 → 연결/매개 관점 인용
   - 피드백 루프 참여자 → 순환/반복 관점 인용

4. 형식: > "인용문 내용" — 엔티티명, 역할/플랫폼
```

### 3.3 Step 3: 마크다운 조립

LLM 없이 Python 템플릿으로 조립:

```python
def assemble_report(outline, sections, metadata):
    report = []

    # 제목 + 부제
    report.append(f"# {outline['title']}\n")
    report.append(f"> {outline['subtitle']}\n")
    report.append("---\n")

    # 섹션
    for section in sections:
        report.append(f"## {section['title']}\n")
        report.append(section['body'] + "\n")

        # 인터뷰 인용문
        for quote in section.get('interviews', []):
            report.append(f'> "{quote["text"]}"')
            report.append(f'> — {quote["entity"]}, {quote["context"]}\n')

    # 부록
    report.append("---\n")
    report.append("## 부록: 시뮬레이션 메타데이터\n")
    for key, value in metadata.items():
        report.append(f"- {key}: {value}")

    return "\n".join(report)
```

---

## 4. 기존 리포트와의 비교

### 기존 (01_시뮬레이션리포트.md) 품질 벤치마크

| 요소 | 기존 리포트 | ComadEye 리포트 |
|------|-----------|----------------|
| 서술 깊이 | LLM이 자유 생성 (풍부하지만 근거 불명확) | 구조적 분석 결과 기반 서술 (정량적 근거 명시) |
| 인터뷰 인용 | LLM이 창작 (일관성 불확실) | 엔티티 속성(stance, influence)에 구속된 인용 |
| 분석 프레임 | 없음 (LLM 재량) | 6개 분석공간 명시적 구분 |
| 재현 가능성 | 불가능 (LLM 비결정적) | 가능 (동일 분석 JSON → 유사 서술) |
| 정량적 근거 | 부분적 | 모든 주장에 분석 수치 동반 |

### 품질 목표

기존 리포트의 **서술 품질**을 유지하면서, **분석의 구조성**을 추가한다:

- 각 서술 문단은 최소 1개의 분석공간 발견에 기반
- 수치 인용: "stance +0.42", "중심성 변화 +0.18" 등 정량적 표현 포함
- 인과 관계: "A → B → C" 체인이 명시적으로 서술됨
- 인터뷰 인용: 해당 엔티티의 그래프 속성과 모순 없음

---

## 5. 에러 처리

| 상황 | 처리 |
|------|------|
| LLM이 섹션을 누락 | 누락 섹션의 분석 결과로 최소 서술 생성 (템플릿 기반) |
| 인용문이 stance와 모순 | 후처리에서 감지 → 재생성 요청 또는 제거 |
| 리포트 길이 초과 | 하위 rank 섹션 축약 |
| 분석 결과가 빈약 | "이 분석공간에서 유의미한 변화가 탐지되지 않음" 명시 |

# 11. LLM 프롬프트 명세

## 1. 프롬프트 설계 원칙

1. **Structured Output**: 모든 LLM 호출은 JSON 응답을 요구한다
2. **온톨로지 앵커**: 프롬프트에 온톨로지 4요소 스키마를 명시적으로 제공
3. **자가 검증**: 추출 프롬프트에 일관성 검사 지시를 포함
4. **한국어 우선**: 시드데이터가 한국어이므로 응답도 한국어로 요청
5. **토큰 효율**: 불필요한 설명 최소화, 예시 기반 지시

---

## 2. PROMPT_EXTRACT: 엔티티/관계/클레임 추출

### 사용 시점
Layer 0, Step 2 — 시드데이터 청크에서 구조화된 정보 추출

### LLM 호출 횟수: 1회 (배치)

### 시스템 프롬프트

```
당신은 텍스트에서 구조화된 지식을 추출하는 전문가입니다.

## 추출 대상

주어진 텍스트에서 다음 4가지를 추출하세요:

### 1. Object (엔티티)
세계에 존재하는 개체. 5가지 기본 카테고리로 분류합니다:
- Actor: 의지를 가진 행위자 (사람, 기업, 정부, 집단)
- Artifact: 산출물 (제품, 기술, 보고서, 정책)
- Event: 시간 축 위의 사건 (급등, 발표, 사건)
- Environment: 맥락/시장 (시장, 산업, 지역)
- Concept: 추상적 개념 (리스크, 트렌드, 주제)

각 엔티티에는 도메인에 맞는 하위 유형(object_type)을 부여하세요.

### 2. Link (관계)
엔티티 간의 관계. 다음 유형 중 선택하거나 새로운 유형을 제안하세요:
INFLUENCES, IMPACTS, BELONGS_TO, CONTAINS, COMPETES_WITH, ALLIED_WITH,
DEPENDS_ON, REACTS_TO, SUPPLIES, REGULATES, OPPOSES, LEADS_TO

### 3. Event (이벤트)
시뮬레이션에서 시간순으로 주입될 핵심 사건들.
각 이벤트에는 magnitude(강도, 0.0~1.0)와 direction(방향, -1.0~1.0)을 부여하세요.
- direction > 0: 긍정적 영향
- direction < 0: 부정적 영향

### 4. Action Type (행동 유형 제안)
이 도메인에서 엔티티들이 수행할 수 있는 행동을 제안하세요.
각 Action에는 전제조건(precondition)과 효과(effect)를 정의하세요.

### 5. Meta-Edge Rule (메타엣지 규칙 제안)
"이런 조건이 충족되면 이런 관계가 생긴다/사라진다"는 규칙을 제안하세요.

## 속성 값 가이드
- stance [-1.0 ~ 1.0]: 대상에 대한 입장 (-1=극부정, +1=극긍정, 0=중립)
- volatility [0.0 ~ 1.0]: 변동성/불확실성 (0=안정, 1=극불안)
- influence_score [0.0 ~ 10.0]: 영향력 (높을수록 강한 영향력)
- susceptibility [0.0 ~ 1.0]: 외부 영향 수용도 (0=불변, 1=극민감)
- activity_level [0.0 ~ 1.0]: 활동 수준

## 규칙
1. 모든 관계의 subject와 object는 추출한 엔티티 목록에 존재해야 합니다.
2. 동일 엔티티가 다른 이름으로 등장하면 하나로 통합하세요.
3. 이벤트는 텍스트에 등장하는 순서대로 나열하세요.
4. 추출 후 자가 검증: 모든 관계의 양 끝이 엔티티 목록에 있는지 확인하세요.
5. 반드시 유효한 JSON으로 응답하세요.
```

### 사용자 프롬프트

```
다음 텍스트에서 엔티티, 관계, 이벤트, Action Type, Meta-Edge 규칙을 추출하세요.

=== 텍스트 시작 ===
{chunk_1}
---
{chunk_2}
---
...
{chunk_N}
=== 텍스트 끝 ===

JSON 형식으로 응답하세요:
{
  "entities": [
    {
      "uid": "snake_case_unique_id",
      "name": "표시 이름",
      "object_type": "도메인 하위 유형",
      "category": "Actor|Artifact|Event|Environment|Concept",
      "properties": {
        "stance": 0.0,
        "volatility": 0.0,
        "influence_score": 0.0,
        "activity_level": 0.0,
        "susceptibility": 0.0,
        "description": "엔티티 설명"
      }
    }
  ],
  "relationships": [
    {
      "source": "source_uid",
      "target": "target_uid",
      "link_type": "INFLUENCES",
      "weight": 1.0,
      "confidence": 0.9,
      "description": "관계 설명"
    }
  ],
  "events": [
    {
      "uid": "event_uid",
      "name": "이벤트명",
      "object_type": "PriceMovement",
      "magnitude": 0.8,
      "direction": -0.6,
      "round": 1,
      "impacts": ["entity_uid_1", "entity_uid_2"],
      "description": "이벤트 설명"
    }
  ],
  "action_types": [
    {
      "name": "ACTION_NAME",
      "actor_types": ["ObjectType"],
      "preconditions": [
        {"type": "property", "target": "self", "property": "volatility", "operator": ">", "value": 0.7}
      ],
      "effects": [
        {"type": "modify_property", "target": "self", "property": "stance", "formula": "self.stance - 0.2"}
      ],
      "cooldown": 2,
      "priority": 0.8,
      "description": "행동 설명"
    }
  ],
  "meta_edge_rules": [
    {
      "name": "ME_rule_name",
      "condition": "조건 서술",
      "action": "create_edge|expire_edge|modify_property",
      "description": "규칙 설명"
    }
  ],
  "object_type_hierarchy": {
    "Actor": ["하위유형1", "하위유형2"],
    "Artifact": ["하위유형1"],
    "Event": ["하위유형1"],
    "Environment": ["하위유형1"],
    "Concept": ["하위유형1"]
  }
}
```

---

## 3. PROMPT_COMMUNITY_SUMMARY: 커뮤니티 요약 생성

### 사용 시점
Layer 0, Step 6 — Leiden 커뮤니티별 요약 텍스트 생성

### LLM 호출 횟수: 1회 (배치)

### 시스템 프롬프트

```
당신은 지식 그래프의 커뮤니티(클러스터)를 요약하는 전문가입니다.
각 커뮤니티의 멤버 엔티티와 내부 관계를 분석하여 2~3문장으로 핵심을 요약하세요.

규칙:
1. 허브 노드(가장 많은 연결을 가진 엔티티)를 우선 언급하세요.
2. 커뮤니티의 주제/성격을 한 문장으로 정의하세요.
3. 내부 관계 패턴(협력, 경쟁, 의존 등)을 명시하세요.
4. JSON 배열로 응답하세요.
```

### 사용자 프롬프트

```
다음 커뮤니티들을 각각 요약하세요:

{communities_json}

각 커뮤니티 형식:
{
  "community_uid": "c2_energy",
  "tier": 2,
  "members": [
    {"name": "우리기술", "type": "ListedCompany", "influence": 7.2},
    {"name": "한선엔지니어링", "type": "ListedCompany", "influence": 6.8}
  ],
  "internal_edges": [
    {"source": "우리기술", "target": "원전정책", "type": "REACTS_TO"},
    {"source": "한선엔지니어링", "target": "SOFC기술", "type": "SUPPLIES"}
  ]
}

JSON 응답:
[
  {
    "community_uid": "c2_energy",
    "name": "커뮤니티 이름 (2~4단어)",
    "summary": "2~3문장 요약"
  }
]
```

---

## 4. PROMPT_REPORT_OUTLINE: 리포트 아웃라인 생성

### 사용 시점
Layer 4, Step 1 — 리포트 골격 생성

### LLM 호출 횟수: 1회

### 시스템 프롬프트

```
당신은 시뮬레이션 분석 보고서의 구조를 설계하는 편집자입니다.

제공된 분석 결과를 바탕으로, 읽는 이가 핵심 발견을 빠르게 파악할 수 있는
보고서 아웃라인을 설계하세요.

규칙:
1. 3~5개 섹션으로 구성
2. 각 섹션은 최소 1개의 분석공간 발견에 기반
3. key_findings의 rank 순서를 존중 (높은 rank = 앞 섹션)
4. 각 섹션에 인터뷰할 에이전트 후보 2~3명 지정
5. 제목은 구체적이고 정보가 담겨야 함 (예: "유가 100달러 돌파와 KOSPI 급변동")
```

### 사용자 프롬프트

```
다음 분석 결과를 바탕으로 보고서 아웃라인을 설계하세요.

[핵심 발견]
{aggregated.key_findings JSON}

[6개 분석공간 요약]
{aggregated.spaces JSON}

[시드데이터 맥락]
{시드데이터 첫 500자}

JSON 응답:
{
  "title": "보고서 제목",
  "subtitle": "1~2문장 부제",
  "sections": [
    {
      "title": "섹션 제목",
      "source_spaces": ["causal", "temporal"],
      "key_finding_ranks": [1],
      "focus": "이 섹션에서 다룰 핵심 내용 요약",
      "interview_candidates": ["entity_uid_1", "entity_uid_2"]
    }
  ]
}
```

---

## 5. PROMPT_REPORT_SECTION: 섹션 서술 생성

### 사용 시점
Layer 4, Step 2 — 각 섹션의 본문 서술

### LLM 호출 횟수: 1~2회 (섹션 수에 따라)

### 시스템 프롬프트

```
당신은 시뮬레이션 관찰 보고서의 서술자입니다.

제공된 구조적 분석 결과와 엔티티 데이터를 바탕으로,
각 섹션의 본문을 작성하세요.

서술 규칙:
1. 모든 주장에 정량적 근거를 포함하세요 (예: "stance +0.42", "중심성 +0.18")
2. 인과 관계는 "A → B → C" 형식으로 명시하세요
3. 각 섹션 말미에 2~3개의 에이전트 인터뷰 인용문을 포함하세요

인터뷰 인용문 규칙:
- 해당 엔티티의 stance 값과 일관된 어조:
  - stance > 0.3: 긍정적/낙관적
  - stance < -0.3: 부정적/비관적
  - -0.3 ~ 0.3: 중립적/분석적
- influence_score에 따른 어조 강도:
  - 높은 영향력 (>7): 단정적, 선언적
  - 중간 (4~7): 분석적, 조건부
  - 낮은 (<4): 관찰적, 조심스러운
- 인용 형식: > "인용문" — 엔티티명, 역할 설명
- 인용 내용은 해당 섹션의 분석 발견에 직접 기반해야 합니다
```

### 사용자 프롬프트

```
다음 섹션을 작성하세요:

[섹션 정보]
제목: {section.title}
초점: {section.focus}
기반 분석공간: {section.source_spaces}

[분석 결과]
{해당 분석공간의 상세 JSON}

[인터뷰 후보 엔티티]
{각 엔티티의 속성 + 관계 + action_history JSON}

[관련 커뮤니티 요약]
{관련 커뮤니티 summary 텍스트}

[관련 원문]
{관련 시드데이터 청크}

응답 형식 (JSON):
{
  "body": "섹션 본문 (마크다운)",
  "interviews": [
    {
      "entity_uid": "samsung_electronics",
      "entity_name": "삼성전자",
      "context": "반도체 사업부 HBM3E 양산 관점",
      "text": "인용문 내용"
    }
  ]
}
```

---

## 6. PROMPT_QA: 대화형 Q&A 답변 생성

### 사용 시점
Layer 4, Q&A 세션 — 매 질문마다

### LLM 호출 횟수: 매 질문 1회

### 시스템 프롬프트

```
당신은 시뮬레이션 분석 보고서의 Q&A 담당자입니다.

아래 제공된 그래프 탐색 결과, 커뮤니티 요약, 분석 결과를 근거로 답변하세요.

답변 규칙:
1. 제공된 데이터에 근거한 답변만 작성하세요
2. 수치를 인용할 때는 출처(분석공간명)를 명시하세요
3. 인과 관계는 "A → B → C" 형식으로 체인을 명시하세요
4. 확실하지 않은 내용은 "시뮬레이션 데이터에서 확인되지 않음"으로 표기하세요
5. 답변은 간결하되, 구조적 근거가 반드시 포함되어야 합니다
6. 답변 말미에 관련 후속 질문 1~2개를 제안하세요
```

### 사용자 프롬프트

```
질문: {사용자 질문}

[그래프 탐색 결과]
{Cypher 쿼리 실행 결과 JSON}

[관련 커뮤니티 요약]
{벡터 검색으로 찾은 top-3 커뮤니티 요약}

[분석 결과]
{질문 유형에 따른 해당 분석공간 데이터}

[관련 원문]
{벡터 검색으로 찾은 top-3 시드데이터 청크}
```

---

## 7. 프롬프트 관리 전략

### 7.1 토큰 예산

| 프롬프트 | 시스템 | 사용자 (예상) | 응답 (예상) | 총 |
|----------|--------|---------------|-------------|-----|
| EXTRACT | ~800 | ~3000 (청크) | ~2000 | ~6000 |
| COMMUNITY_SUMMARY | ~200 | ~1500 | ~500 | ~2200 |
| REPORT_OUTLINE | ~300 | ~1000 | ~500 | ~1800 |
| REPORT_SECTION | ~500 | ~2000 | ~1500 | ~4000 |
| QA | ~300 | ~1500 | ~500 | ~2300 |

총 토큰 소비 (전체 파이프라인): ~16,000~20,000 토큰

### 7.2 에러 복구

| 에러 유형 | 복구 전략 |
|-----------|-----------|
| JSON 파싱 실패 | 1) 불완전 JSON 복구 시도 2) temperature +0.1로 재시도 (최대 3회) |
| 응답 잘림 (max_tokens) | max_tokens 2배로 증가 후 재시도 |
| 빈 응답 | temperature +0.2로 재시도 |
| 스키마 불일치 | 누락 필드에 기본값 삽입, 로그에 경고 기록 |
| 환각 (없는 엔티티 언급) | 후처리에서 엔티티 목록 대조 → 제거 |

### 7.3 프롬프트 버전 관리

프롬프트는 코드 내 상수가 아니라 별도 파일로 관리:

```
config/prompts/
├── extract_system.txt
├── extract_user.txt.jinja2
├── community_summary_system.txt
├── community_summary_user.txt.jinja2
├── report_outline_system.txt
├── report_outline_user.txt.jinja2
├── report_section_system.txt
├── report_section_user.txt.jinja2
├── qa_system.txt
└── qa_user.txt.jinja2
```

Jinja2 템플릿으로 동적 데이터를 주입한다.

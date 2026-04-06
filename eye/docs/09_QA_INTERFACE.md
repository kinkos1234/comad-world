# 09. 대화형 Q&A 인터페이스 명세

## 1. 목표

시뮬레이션 완료 후, 사용자가 분석 결과에 대해 **자연어로 추가 질문**을 할 수 있는 대화형 인터페이스.

GraphRAG 기반으로, 질문을 그래프 탐색 + 벡터 검색으로 분해하여 **구조적 근거가 포함된 답변**을 생성한다.

---

## 2. 질의 처리 파이프라인

```
사용자 질문 (자연어)
     │
     ├─[Step 1]─→ 질문 분류 + 의미 풍부화
     │
     ├─[Step 2]─→ 그래프 쿼리 생성 (Cypher)
     │
     ├─[Step 3]─→ 컨텍스트 수집
     │             ├── Neo4j Cypher 실행 → 그래프 결과
     │             ├── 벡터 검색 → 관련 청크/요약
     │             └── 분석 결과 참조 → 해당 분석공간 데이터
     │
     ├─[Step 4]─→ LLM 답변 생성 (1회)
     │
     └─[Step 5]─→ 응답 후처리 + 출력
```

---

## 3. Step 1: 질문 분류 + 의미 풍부화

### 3.1 질문 유형 분류

| 유형 | 예시 | 처리 전략 |
|------|------|-----------|
| **엔티티 질문** | "삼성전자는 어떤 영향을 받았는가?" | 특정 노드 중심 서브그래프 탐색 |
| **관계 질문** | "원전 섹터와 반도체 섹터의 관계는?" | 두 노드/커뮤니티 간 경로 탐색 |
| **인과 질문** | "유가 급등이 왜 원전주에 호재인가?" | 인과 DAG 경로 추출 |
| **비교 질문** | "에너지 섹터 vs 방산 섹터 반응 차이?" | 두 커뮤니티 속성 비교 |
| **예측 질문** | "이 추세가 계속되면 어떻게 되나?" | 피드백 루프 + 시뮬레이션 외삽 |
| **메타 질문** | "어떤 분석공간에서 이 결론이 나왔나?" | 분석 결과 JSON 직접 참조 |

분류는 **키워드 매칭 + 간단한 규칙**으로 수행 (LLM 미사용):

```python
def classify_question(question: str) -> QuestionType:
    if any(w in question for w in ["왜", "원인", "때문"]):
        return QuestionType.CAUSAL
    if any(w in question for w in ["관계", "연결", "사이"]):
        return QuestionType.RELATIONSHIP
    if any(w in question for w in ["비교", "차이", "vs"]):
        return QuestionType.COMPARISON
    if any(w in question for w in ["앞으로", "계속", "예측", "전망"]):
        return QuestionType.PREDICTION
    # 기본: 엔티티 질문
    return QuestionType.ENTITY
```

### 3.2 벡터 의미 풍부화

S.O.S "벡터 의미 풍부화" 3단계 적용:

```python
def enrich_query(question: str, ontology) -> EnrichedQuery:
    # 1. 유사단어 확장
    keywords = extract_keywords(question)
    expanded = []
    for kw in keywords:
        expanded.extend(synonym_dict.get(kw, [kw]))

    # 2. 의미 다층화 — 추상↔구체 매핑
    layers = []
    for kw in keywords:
        entity = ontology.find_entity(kw)
        if entity:
            layers.append({
                "abstract": entity.community_c2_name,  # 섹터 수준
                "concrete": entity.name,                # 개체 수준
                "type": entity.object_type
            })

    # 3. 도메인 온톨로지 앵커
    anchored_terms = ontology.resolve_ambiguity(keywords)

    return EnrichedQuery(
        original=question,
        keywords=keywords,
        expanded_keywords=expanded,
        semantic_layers=layers,
        anchored_terms=anchored_terms
    )
```

---

## 4. Step 2: Cypher 쿼리 생성

질문 유형별 Cypher 템플릿:

### 4.1 엔티티 질문

```cypher
-- "{entity_name}은/는 어떤 영향을 받았는가?"
MATCH (n:Entity)
WHERE n.name CONTAINS $entity_name OR n.uid = $entity_uid
OPTIONAL MATCH (n)-[r]-(m:Entity)
WHERE r.expired_at IS NULL
RETURN n, collect({
  related: m.name,
  relation: type(r),
  weight: r.weight,
  direction: CASE WHEN startNode(r) = n THEN 'outgoing' ELSE 'incoming' END
}) AS relationships
```

### 4.2 인과 질문

```cypher
-- "A가 왜 B에 영향을 미치는가?"
MATCH path = shortestPath(
  (a:Entity {name: $source})-[*..5]->(b:Entity {name: $target})
)
RETURN [node IN nodes(path) | node.name] AS causal_chain,
       [rel IN relationships(path) | type(rel)] AS relation_types,
       length(path) AS hops
```

### 4.3 비교 질문

```cypher
-- "A 섹터 vs B 섹터"
MATCH (a:Entity)-[:MEMBER_OF]->(ca:Community {name: $community_a})
MATCH (b:Entity)-[:MEMBER_OF]->(cb:Community {name: $community_b})
RETURN
  ca.name AS community_a,
  avg(a.stance) AS avg_stance_a,
  avg(a.volatility) AS avg_volatility_a,
  cb.name AS community_b,
  avg(b.stance) AS avg_stance_b,
  avg(b.volatility) AS avg_volatility_b
```

---

## 5. Step 3: 컨텍스트 수집

3가지 소스에서 컨텍스트를 수집하여 LLM에 제공:

```python
def collect_context(enriched_query, question_type, graph):
    context = {}

    # 1. 그래프 쿼리 결과
    cypher = generate_cypher(enriched_query, question_type)
    context["graph_result"] = graph.query(cypher)

    # 2. 벡터 검색 — 관련 커뮤니티 요약 + 원문 청크
    query_embedding = embed(enriched_query.original)
    context["relevant_summaries"] = vector_search(
        query_embedding, index="community_summaries", top_k=3
    )
    context["relevant_chunks"] = vector_search(
        query_embedding, index="chunk_texts", top_k=3
    )

    # 3. 분석 결과 참조
    if question_type == QuestionType.CAUSAL:
        context["analysis"] = load_json("data/analysis/causal.json")
    elif question_type == QuestionType.COMPARISON:
        context["analysis"] = load_json("data/analysis/structural.json")
    else:
        context["analysis"] = load_json("data/analysis/aggregated.json")["key_findings"]

    return context
```

---

## 6. Step 4: LLM 답변 생성

### 프롬프트 구조

```
시스템 프롬프트:
"당신은 시뮬레이션 분석 보고서의 Q&A 담당자입니다.
아래 제공된 그래프 탐색 결과, 커뮤니티 요약, 분석 결과를 근거로 답변하세요.

답변 규칙:
1. 제공된 데이터에 근거한 답변만 작성하세요.
2. 수치를 인용할 때는 출처(분석공간명)를 명시하세요.
3. 인과 관계를 설명할 때는 A → B → C 형식으로 체인을 명시하세요.
4. 확실하지 않은 내용은 '시뮬레이션 데이터에서 확인되지 않음'으로 표기하세요.
5. 답변은 간결하되, 구조적 근거가 반드시 포함되어야 합니다."

사용자 프롬프트:
"질문: {원문 질문}

[그래프 탐색 결과]
{graph_result JSON}

[관련 커뮤니티 요약]
{relevant_summaries}

[분석 결과]
{analysis JSON}

[관련 원문]
{relevant_chunks}"
```

### LLM 호출: 매 질문 1회

---

## 7. Step 5: 응답 후처리

```python
def postprocess_response(response: str, context: dict) -> str:
    # 1. 근거 확인: 응답에 언급된 엔티티가 context에 존재하는지
    mentioned_entities = extract_entity_mentions(response)
    for entity in mentioned_entities:
        if entity not in context["graph_result"]:
            response += f"\n\n(주의: '{entity}'는 현재 그래프에서 직접 확인되지 않은 엔티티입니다)"

    # 2. 후속 질문 제안
    follow_ups = suggest_follow_ups(response, context)
    if follow_ups:
        response += "\n\n**추가로 물어볼 수 있는 질문:**\n"
        for q in follow_ups:
            response += f"- {q}\n"

    return response
```

---

## 8. 대화 세션 관리

### 8.1 세션 상태

```python
@dataclass
class QASession:
    session_id: str
    graph: Neo4jClient
    analysis_results: dict           # 6개 분석공간 결과 캐시
    conversation_history: list[dict] # {role, content} 리스트
    max_history: int = 10            # 컨텍스트에 포함할 최대 이전 대화 수
```

### 8.2 대화 히스토리 관리

이전 대화를 LLM 컨텍스트에 포함하되, 윈도우 크기를 제한:

```python
def build_conversation_context(session, new_question):
    messages = []

    # 시스템 프롬프트 (매번)
    messages.append({"role": "system", "content": SYSTEM_PROMPT})

    # 이전 대화 (최근 N개만)
    for turn in session.conversation_history[-session.max_history:]:
        messages.append(turn)

    # 새 질문 + 컨텍스트
    messages.append({"role": "user", "content": new_question_with_context})

    return messages
```

### 8.3 CLI 인터페이스

```
$ python main.py qa

ComadEye Q&A Session
Type 'exit' to quit, 'reset' to clear history.

You: 삼성전자가 받은 영향을 요약해줘
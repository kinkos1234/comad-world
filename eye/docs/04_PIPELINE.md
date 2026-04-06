# 04. 입력 파이프라인 명세 (Layer 0 → Layer 1)

## 1. 개요

시드데이터.txt 파일을 읽어 Neo4j 지식그래프 + Leiden 커뮤니티를 구축하는 파이프라인.
GraphRAG 인덱싱 6단계를 로컬 환경에 맞게 구현한다.

```
시드데이터.txt
    │
    ├─[Step 1]─→ 텍스트 청킹
    ├─[Step 2]─→ 엔티티/관계/클레임 추출 (LLM 배치 1회)
    ├─[Step 3]─→ 중복 제거 + 엣지 가중치
    ├─[Step 4]─→ Neo4j 적재 + Leiden 커뮤니티 탐지
    ├─[Step 5]─→ 벡터 의미 풍부화
    └─[Step 6]─→ 커뮤니티 요약 생성 (LLM 배치 1회)
```

---

## 2. Step 1: 텍스트 청킹

### 입력
- 시드데이터.txt 파일 (1개 이상, UTF-8)

### 처리
```
1. 파일 읽기 + 인코딩 정규화
2. 전처리:
   - 연속 공백/줄바꿈 정규화
   - 구분선(===, ---) 제거
   - 출처/참고자료 섹션 분리 보존
3. 토큰 기반 청킹:
   - 청크 크기: 600 토큰
   - 오버랩: 100 토큰
   - 분할 기준: 문장 경계 우선, 불가시 단어 경계
   - 각 청크에 원본 파일명, 위치 정보 부여
```

### 출력
- `data/extraction/chunks.jsonl`

### 구현 노트
- 토크나이저: `tiktoken`의 `cl100k_base` (GPT-4 호환) 또는 Qwen 토크나이저
- 한국어 문장 분리: `kss` (Korean Sentence Splitter) 라이브러리 사용
- 복수 시드파일은 파일 경계에서 청크를 분리 (교차 청킹 금지)

---

## 3. Step 2: 엔티티/관계/클레임 추출

### 입력
- `chunks.jsonl`

### 처리

**배치 전략**: 전체 청크를 하나의 LLM 호출로 처리하되, 컨텍스트 윈도우 초과 시 청크 그룹으로 분할한다.

```
1. 프롬프트 구성 (→ 11_PROMPTS.md의 PROMPT_EXTRACT 참조):
   - 시스템 프롬프트: 온톨로지 4요소 스키마 설명 + 추출 규칙
   - 사용자 프롬프트: 전체 청크 텍스트 (구분자로 연결)

2. LLM 응답 파싱:
   - JSON 형식 응답 기대
   - 파싱 실패 시: JSON 복구 시도 → 재시도 (temperature +0.1)

3. 추출 대상:
   a) Object 목록: {name, object_type, category, properties, description}
   b) Link 목록: {subject, predicate, object, weight, confidence}
   c) Claim 목록: {content, source_chunk, related_entities}
   d) Event 목록: {name, magnitude, direction, timing, impacts}
   e) Action Type 제안: {name, actor_types, preconditions, effects}
   f) Meta-Edge 규칙 제안: {condition, action, description}
```

### 출력
- `data/extraction/triples.jsonl` — 추출된 트리플
- `data/extraction/ontology.json` — 자동 생성된 도메인 온톨로지

### LLM 호출: 1회 (배치)

### 품질 보장
- **자가 검증**: LLM에게 추출 결과의 일관성 검사를 같은 호출 내에서 요청
  - "추출한 관계의 subject/object가 추출한 엔티티 목록에 존재하는지 확인"
  - "역방향 관계가 누락되지 않았는지 확인"
- **후처리 검증** (코드):
  - 관계의 양 끝이 엔티티 목록에 존재하는지 확인
  - 엔티티 유형이 Object Type 계층에 적합한지 확인

---

## 4. Step 3: 중복 제거 + 엣지 가중치

### 입력
- `triples.jsonl`

### 처리

```python
# 의사코드
def deduplicate(triples):
    entity_map = {}   # name → canonical entity
    edge_map = {}     # (src, pred, tgt) → aggregated edge

    for triple in triples:
        # 1. 엔티티 정규화
        src = normalize_entity(triple.subject)
        tgt = normalize_entity(triple.object)

        # 2. 동일 엔티티 병합 (이름 유사도 > 0.85)
        src = merge_if_similar(src, entity_map)
        tgt = merge_if_similar(tgt, entity_map)

        # 3. 동일 관계 가중치 누적
        edge_key = (src.uid, triple.predicate, tgt.uid)
        if edge_key in edge_map:
            edge_map[edge_key].weight += triple.weight
            edge_map[edge_key].confidence = max(
                edge_map[edge_key].confidence,
                triple.confidence
            )
            edge_map[edge_key].source_chunks.append(triple.source_chunk)
        else:
            edge_map[edge_key] = triple

    return entity_map, edge_map
```

### 엔티티 정규화 규칙
1. 이름 정규화: 공백 정리, 괄호 안 코드 분리 (예: "우리기술(032820)" → name="우리기술", code="032820")
2. 동의어 탐지: 한영 변환 (삼성전자 ↔ Samsung Electronics), 약어 확장
3. 유사도 임계값: 자카드 유사도 > 0.85 또는 임베딩 코사인 > 0.9

### 출력
- `data/extraction/triples_deduped.jsonl`

---

## 5. Step 4: Neo4j 적재 + Leiden 커뮤니티 탐지

### 입력
- `triples_deduped.jsonl`
- `ontology.json`

### 처리

#### 5.1 Neo4j 적재

```cypher
-- 1. 온톨로지 제약 조건 생성
CREATE CONSTRAINT entity_uid IF NOT EXISTS
FOR (n:Entity) REQUIRE n.uid IS UNIQUE;

-- 2. 엔티티 노드 생성 (MERGE로 중복 방지)
UNWIND $entities AS e
MERGE (n:Entity {uid: e.uid})
SET n += e.properties
SET n:${e.category}
SET n:${e.object_type};

-- 3. 관계 생성
UNWIND $edges AS e
MATCH (src:Entity {uid: e.source_uid})
MATCH (tgt:Entity {uid: e.target_uid})
CALL apoc.create.relationship(src, e.link_type, e.properties, tgt) YIELD rel
RETURN rel;

-- 4. 커뮤니티 노드 생성 (Leiden 결과)
UNWIND $communities AS c
MERGE (comm:Community {uid: c.uid})
SET comm += c.properties;

-- 5. 엔티티-커뮤니티 관계
UNWIND $memberships AS m
MATCH (n:Entity {uid: m.entity_uid})
MATCH (c:Community {uid: m.community_uid})
MERGE (n)-[:MEMBER_OF]->(c);
```

#### 5.2 Leiden 커뮤니티 탐지

```python
# python-igraph를 사용한 Leiden 알고리즘
import igraph as ig

def detect_communities(graph_data):
    # 1. igraph 그래프 구성
    g = ig.Graph.TupleList(
        [(e["source"], e["target"], e["weight"]) for e in graph_data["edges"]],
        weights=True
    )

    # 2. 4계층 Leiden 실행
    communities = {}
    current_graph = g

    for tier in range(4):  # C0, C1, C2, C3
        partition = current_graph.community_leiden(
            objective_function="modularity",
            resolution_parameter=1.0 / (2 ** tier),  # 상위 tier일수록 coarse
            n_iterations=10
        )
        communities[f"C{tier}"] = partition

        # 다음 tier를 위해 커뮤니티를 노드로 축약
        current_graph = partition.cluster_graph(
            combine_edges={"weight": "sum"}
        )

    return communities
```

### 출력
- Neo4j에 적재된 그래프
- `data/communities/communities.json`

---

## 6. Step 5: 벡터 의미 풍부화

### 입력
- Neo4j의 엔티티 목록
- `ontology.json`

### 처리

S.O.S의 "벡터 의미 풍부화 3단계 파이프라인" 적용:

```
1. 유사단어 목록 생성 (Lexical Expansion)
   - 엔티티명의 동의어·유의어·관련어 확장
   - 예: "코스피" → ["KOSPI", "한국종합주가지수", "Korean stock index"]
   - 방법: LLM 없이 사전 기반 + 한영 사전 + 약어 DB

2. 의미 다층화 (Semantic Layering)
   - 추상 → 구체 계층 매핑
   - 예: "에너지 안보" (추상) → "원전 건설" (중간) → "우리기술 MMIS" (구체)
   - 방법: Leiden 커뮤니티 계층 C0~C3을 의미 계층으로 활용

3. 도메인 온톨로지 정렬
   - ontology.json의 Object Type 계층이 앵커 역할
   - 임베딩 생성 시 "유형: ListedCompany, 섹터: 반도체, 관계: HBM 공급" 등
     구조적 컨텍스트를 텍스트에 포함하여 임베딩
```

### 임베딩 생성

```python
from sentence_transformers import SentenceTransformer

model = SentenceTransformer("BAAI/bge-m3")

for entity in entities:
    # 구조적 컨텍스트를 포함한 텍스트 구성
    enriched_text = (
        f"{entity.name}. "
        f"유형: {entity.object_type}. "
        f"설명: {entity.description}. "
        f"관련: {', '.join(entity.related_entities)}. "
        f"동의어: {', '.join(entity.synonyms)}"
    )
    entity.embedding = model.encode(enriched_text)
```

### 출력
- 엔티티 임베딩 인덱스 (numpy .npy 또는 ChromaDB)

---

## 7. Step 6: 커뮤니티 요약 생성

### 입력
- `communities.json`
- Neo4j에서 각 커뮤니티의 멤버 엔티티 + 내부 관계

### 처리

```
1. 각 커뮤니티에 대해:
   a) 멤버 엔티티 목록 + 속성 수집
   b) 내부 관계(엣지) 목록 수집
   c) 관련 원문 청크 수집

2. LLM 배치 호출 (→ 11_PROMPTS.md의 PROMPT_COMMUNITY_SUMMARY 참조):
   - 모든 커뮤니티를 하나의 프롬프트에 포함
   - 각 커뮤니티에 대해 2~3문장 요약 생성
   - 허브 노드(높은 중심성) 우선 언급

3. 요약 저장 + Neo4j Community 노드에 summary 속성 업데이트
```

### LLM 호출: 1회 (배치)

### 출력
- `data/communities/summaries.json`
- Neo4j Community 노드의 `summary` 속성 업데이트

---

## 8. 파이프라인 오케스트레이션

### 실행 흐름

```python
async def run_ingestion_pipeline(seed_files: list[str]):
    # Step 1: 청킹 (병렬 가능)
    all_chunks = []
    for f in seed_files:
        chunks = chunker.process(f)
        all_chunks.extend(chunks)
    save_jsonl("data/extraction/chunks.jsonl", all_chunks)

    # Step 2: 추출 (LLM 1회)
    extraction = await extractor.extract(all_chunks)
    save_jsonl("data/extraction/triples.jsonl", extraction.triples)
    save_json("data/extraction/ontology.json", extraction.ontology)

    # Step 3: 중복 제거
    entities, edges = deduplicator.process(extraction.triples)
    save_jsonl("data/extraction/triples_deduped.jsonl", edges)

    # Step 4: Neo4j 적재 + Leiden
    await graph_loader.load(entities, edges, extraction.ontology)
    communities = community_detector.detect()
    save_json("data/communities/communities.json", communities)

    # Step 5: 벡터 풍부화 (LLM 0회)
    enricher.enrich(entities)

    # Step 6: 커뮤니티 요약 (LLM 1회)
    summaries = await summarizer.summarize(communities)
    save_json("data/communities/summaries.json", summaries)

    return PipelineResult(
        entity_count=len(entities),
        edge_count=len(edges),
        community_count=sum(len(c) for c in communities.values()),
        llm_calls=2
    )
```

### 에러 처리

| 에러 유형 | 처리 |
|-----------|------|
| LLM JSON 파싱 실패 | JSON 복구 시도 → temperature +0.1로 재시도 (최대 3회) |
| LLM 타임아웃 | 청크 그룹 크기 절반으로 줄여 재시도 |
| Neo4j 연결 실패 | 설정 확인 메시지 출력 후 종료 |
| 엔티티 0건 추출 | 경고 출력 + 시드데이터 품질 점검 안내 |
| Leiden 수렴 실패 | resolution_parameter 조정 후 재시도 |

### 멱등성

파이프라인은 **멱등**하게 설계한다:
- Neo4j 적재는 `MERGE`로 중복 방지
- 동일 시드데이터 재실행 시 기존 결과 덮어쓰기 (timestamps로 구분)
- 중간 결과 파일이 존재하면 해당 Step부터 재개 가능 (체크포인트)

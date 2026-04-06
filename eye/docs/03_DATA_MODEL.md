# 03. 데이터 모델 명세

## 1. Neo4j 그래프 스키마

### 1.1 노드 라벨 체계

모든 엔티티 노드는 **2개 라벨**을 가진다: 기본 카테고리 + 도메인 유형

```cypher
-- 예시: 삼성전자 노드
(:Actor:ListedCompany {
  uid: "samsung_electronics",
  name: "삼성전자",
  object_type: "ListedCompany",
  category: "Actor",
  stance: 0.2,
  volatility: 0.6,
  influence_score: 8.5,
  activity_level: 0.7,
  susceptibility: 0.4,
  community_id: "c1_semiconductor",
  community_tier: 1,
  description: "HBM3E 양산, 반도체 사업부 핵심",
  source_chunks: ["chunk_003", "chunk_015"],
  created_at: -1
})
```

### 1.2 노드 인덱스

```cypher
CREATE INDEX node_uid FOR (n:Entity) ON (n.uid);
CREATE INDEX node_type FOR (n:Entity) ON (n.object_type);
CREATE INDEX node_community FOR (n:Entity) ON (n.community_id);
CREATE FULLTEXT INDEX node_name FOR (n:Entity) ON EACH [n.name, n.description];
```

### 1.3 관계 스키마

```cypher
-- 예시: 외국인투자자 -[SELLS]-> 삼성전자
(:Investor)-[:SELLS {
  weight: 5.3,
  confidence: 0.95,
  created_at: -1,
  expired_at: null,
  source_chunk: "chunk_007",
  metadata: {amount: "5.3조원", period: "주간"}
}]->(:ListedCompany)
```

### 1.4 커뮤니티 노드

Leiden 커뮤니티 계층은 별도 노드로 저장한다:

```cypher
(:Community {
  uid: "c2_energy",
  tier: 2,
  name: "에너지·원전 섹터",
  summary: "유가 급등 수혜, 원전 필수 인프라화...",
  member_count: 8,
  members: ["우리기술", "한선엔지니어링", ...],
  parent_community: "c3_korean_market",
  child_communities: ["c1_nuclear", "c1_fuel_cell"]
})

-- 엔티티 → 커뮤니티 관계
(:Entity)-[:MEMBER_OF]->(:Community)
(:Community)-[:CHILD_OF]->(:Community)
```

---

## 2. 파일 기반 데이터 구조

### 2.1 디렉토리 레이아웃

```
data/
├── seeds/                         # 입력 시드데이터
│   ├── 01_시드데이터.txt
│   └── 02_시드데이터.txt
│
├── extraction/                    # Layer 0 중간 결과
│   ├── chunks.jsonl               # 텍스트 청크
│   ├── triples.jsonl              # 추출된 트리플
│   ├── triples_deduped.jsonl      # 중복 제거 후 트리플
│   └── ontology.json              # 자동 생성된 도메인 온톨로지
│
├── communities/                   # Leiden 커뮤니티
│   ├── communities.json           # 커뮤니티 구조 (C0~C3)
│   └── summaries.json             # 커뮤니티별 요약 텍스트
│
├── snapshots/                     # 시뮬레이션 스냅샷
│   ├── round_000.jsonl            # 초기 상태
│   ├── round_001.jsonl            # 라운드 1 후 상태
│   ├── ...
│   ├── events.jsonl               # 이벤트 주입 로그
│   └── actions.jsonl              # Action 실행 로그
│
├── analysis/                      # 분석 결과
│   ├── hierarchy.json             # 계층공간 분석
│   ├── temporal.json              # 시간공간 분석
│   ├── recursive.json             # 재귀공간 분석
│   ├── structural.json            # 구조공간 분석
│   ├── causal.json                # 인과공간 분석
│   ├── cross_space.json           # 다중공간 분석
│   └── aggregated.json            # 통합 분석 결과
│
├── reports/                       # 최종 리포트
│   ├── 01_시뮬레이션리포트.md
│   └── ...
│
├── qa_sessions/                   # Q&A 세션 이력
│   └── {job_id}.json              # 대화 이력 (자동 저장/복원)
│
└── logs/                          # 시스템 로그
    ├── llm_calls.jsonl            # LLM 호출 전문
    └── pipeline.log               # 파이프라인 실행 로그
```

### 2.2 JSONL 포맷 정의

#### 청크 (chunks.jsonl)

```json
{
  "chunk_id": "chunk_001",
  "seed_file": "01_시드데이터.txt",
  "text": "2026년 3월 둘째 주 한국 증시는 중동발 지정학적 리스크와...",
  "token_count": 587,
  "start_char": 0,
  "end_char": 1200,
  "overlap_prev": null,
  "overlap_next": "chunk_002"
}
```

#### 트리플 (triples.jsonl)

```json
{
  "triple_id": "t_001",
  "subject": {
    "name": "WTI유가",
    "object_type": "PriceMovement",
    "category": "Event",
    "properties": {
      "stance": 0.0,
      "volatility": 0.9,
      "magnitude": 0.85,
      "description": "WTI 유가 배럴당 100달러 돌파"
    }
  },
  "predicate": {
    "link_type": "IMPACTS",
    "weight": 0.9,
    "confidence": 0.95
  },
  "object": {
    "name": "코스피",
    "object_type": "Market",
    "category": "Environment"
  },
  "claim": "WTI 유가가 일주일 새 13.7% 폭등하며 코스피 급변동 유발",
  "source_chunk": "chunk_001"
}
```

#### 시뮬레이션 스냅샷 (round_NNN.jsonl)

한 라운드 종료 후 **변경된 노드만** 기록한다:

```json
{
  "round": 3,
  "timestamp": "2026-03-18T14:30:00",
  "node_uid": "samsung_electronics",
  "changes": {
    "stance": {"before": 0.2, "after": -0.1},
    "volatility": {"before": 0.6, "after": 0.8}
  },
  "caused_by": {
    "event": "foreign_sell_off",
    "action": "SELL",
    "actor": "foreign_investor"
  }
}
```

#### Action 실행 로그 (actions.jsonl)

```json
{
  "round": 3,
  "action": "SELL",
  "actor": "foreign_investor",
  "target": "samsung_electronics",
  "preconditions_met": [
    {"type": "property", "check": "stance < -0.3", "value": -0.4},
    {"type": "property", "check": "volatility > 0.5", "value": 0.7}
  ],
  "effects_applied": [
    {"property": "price_pressure", "change": -0.3}
  ],
  "meta_edges_triggered": ["ME_flight_to_safety"]
}
```

#### 이벤트 주입 로그 (events.jsonl)

```json
{
  "round": 1,
  "event_uid": "wti_100_breakthrough",
  "name": "WTI 유가 100달러 돌파",
  "magnitude": 0.85,
  "direction": -0.6,
  "impacted_nodes": [
    {"uid": "kospi", "distance": 1, "effect": 0.85},
    {"uid": "samsung_electronics", "distance": 2, "effect": 0.51},
    {"uid": "uri_tech", "distance": 2, "effect": 0.60}
  ]
}
```

---

## 3. 도메인 온톨로지 파일 (ontology.json)

Layer 0에서 LLM이 자동 생성하는 도메인 온톨로지:

```json
{
  "domain": "korean_stock_market_weekly",
  "version": "1.0",
  "created_from": ["01_시드데이터.txt"],

  "object_types": [
    {
      "name": "ForeignInvestor",
      "parent": "Investor",
      "category": "Actor",
      "required_properties": ["stance", "volatility", "influence_score"],
      "allowed_actions": ["SELL", "BUY", "FLIGHT_TO_SAFETY"],
      "description": "외국인 투자자 집단"
    }
  ],

  "link_types": [
    {
      "name": "SELLS",
      "source_types": ["Investor"],
      "target_types": ["ListedCompany", "Market"],
      "directed": true,
      "description": "투자자가 종목/시장을 매도"
    }
  ],

  "action_types": [
    {
      "name": "FLIGHT_TO_SAFETY",
      "actor_types": ["Investor"],
      "preconditions": [
        {"type": "property", "target": "self", "property": "volatility", "operator": ">", "value": 0.7}
      ],
      "effects": [
        {"type": "reweight", "pattern": "high_risk_edges", "factor": 0.5},
        {"type": "reweight", "pattern": "low_risk_edges", "factor": 1.5}
      ],
      "cooldown": 2,
      "priority": 0.9
    }
  ],

  "meta_edge_rules": [
    {
      "name": "ME_opposition_formation",
      "condition": "abs(source.stance - target.stance) > 0.7",
      "action": "create_edge",
      "edge_type": "OPPOSES",
      "description": "입장 차이가 극심하면 대립 관계 형성"
    }
  ],

  "initial_events": [
    {
      "uid": "wti_100_breakthrough",
      "name": "WTI 유가 100달러 돌파",
      "object_type": "PriceMovement",
      "magnitude": 0.85,
      "direction": -0.6,
      "round": 1,
      "impacts": ["kospi", "energy_sector", "airline_sector"]
    }
  ]
}
```

---

## 4. 설정 파일 (config/settings.yaml)

```yaml
neo4j:
  uri: "bolt://localhost:7687"
  user: "neo4j"
  password: "comadeye2026"
  database: "comadeye"

llm:
  base_url: "http://localhost:11434/v1"  # Ollama
  model: "auto"                  # "auto" = Ollama에서 자동 감지, 또는 특정 모델명 지정
  temperature: 0.3
  max_tokens: 8192
  timeout: 300  # seconds

embeddings:
  model: "BAAI/bge-m3"
  device: "mps"  # macOS Apple Silicon
  dimension: 1024

ingestion:
  chunk_size: 600          # tokens
  chunk_overlap: 100       # tokens
  max_entity_types: 15     # 도메인당 최대 Object Type 수
  max_relationship_types: 12

simulation:
  max_rounds: 10
  community_refresh_interval: 3  # 매 N 라운드마다 Leiden 재계산
  propagation_decay: 0.6         # hop당 영향 감쇠율
  volatility_decay: 0.1          # 라운드당 volatility 자연 감쇠

analysis:
  enabled_spaces:
    - hierarchy
    - temporal
    - recursive
    - structural
    - causal
    - cross_space

report:
  template: "default"
  include_interviews: true
  max_interview_quotes: 3  # 섹션당 최대 인용문 수
```

---

## 5. 임베딩 인덱스 구조

벡터 의미 풍부화와 Q&A 검색을 위한 로컬 임베딩 인덱스:

```python
# 인덱스 대상
embedding_targets = {
    "entity_names": {
        # 엔티티명 + 동의어/유의어 확장
        "삼성전자": [embedding_vector],
        "Samsung Electronics": [embedding_vector],  # 풍부화
    },
    "chunk_texts": {
        # 원문 청크 임베딩
        "chunk_001": [embedding_vector],
    },
    "community_summaries": {
        # 커뮤니티 요약 임베딩
        "c2_energy": [embedding_vector],
    }
}

# 저장: numpy .npy + FAISS 또는 단순 cosine similarity
# MVP에서는 ChromaDB 또는 numpy 기반 brute-force로 시작
```

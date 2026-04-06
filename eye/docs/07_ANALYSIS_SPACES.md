# 07. 6개 분석공간 명세 (Layer 3)

## 1. 개요

시뮬레이션 결과(스냅샷 시퀀스)를 **6개의 독립적 위상학적 렌즈**로 동시 분석한다.

S.O.S의 "위상학적 지능" 프레임워크:
> "지능을 해체하고 측정하는 6개의 독립적이면서 상호연결된 위상적 차원"

각 분석공간은:
- 독립적으로 실행 가능 (병렬화 가능)
- JSON 형식의 정량적 분석 결과를 출력
- LLM 호출 없이 그래프 알고리즘과 통계 연산으로 수행

---

## 2. 입력: 시뮬레이션 스냅샷

모든 분석공간이 공유하는 입력 데이터:

```python
@dataclass
class SimulationData:
    snapshots: list[RoundSnapshot]      # 라운드별 스냅샷 (round_000~round_NNN)
    events_log: list[EventEntry]        # 이벤트 주입 로그
    actions_log: list[ActionEntry]      # Action 실행 로그
    meta_edges_log: list[MetaEdgeEntry] # 메타엣지 발동 로그
    communities_initial: dict           # 초기 커뮤니티 구조
    communities_final: dict             # 최종 커뮤니티 구조
    community_migrations: list[dict]    # 커뮤니티 이동 이력
    graph: Neo4jClient                  # 현재 그래프 (최종 상태)
```

---

## 3. 분석공간 1: 계층공간 (Hierarchy Space)

### 핵심 질문
**"이 현상은 어느 수준에서 발생했는가?"**

### 분석 항목

#### 3.1 커뮤니티 계층별 변화량

```python
def analyze_hierarchy(data: SimulationData) -> dict:
    results = {}

    for tier in range(4):  # C0, C1, C2, C3
        tier_key = f"C{tier}"
        communities = get_communities_at_tier(data, tier)

        for comm in communities:
            # 멤버 노드의 속성 변화량 집계
            member_changes = aggregate_member_changes(data, comm)

            results[tier_key][comm.uid] = {
                "name": comm.name,
                "member_count": len(comm.members),
                "stance_delta": member_changes.avg_stance_delta,
                "volatility_delta": member_changes.avg_volatility_delta,
                "internal_cohesion_change": calc_cohesion_delta(data, comm),
                "dominant_event": find_dominant_event(data, comm),
                "action_count": count_actions_in_community(data, comm),
            }

    # 계층 간 변화량 비교
    results["tier_comparison"] = {
        "most_changed_tier": max(tiers, key=lambda t: t.total_delta),
        "top_down_propagation": detect_top_down_flow(results),
        "bottom_up_emergence": detect_bottom_up_flow(results),
    }

    return results
```

#### 3.2 계층 간 전파 방향 감지

- **Top-Down**: C3→C2→C1→C0 순서로 변화가 전파되는 경우 (거시 정책이 미시에 영향)
- **Bottom-Up**: C0→C1→C2→C3 순서로 변화가 전파되는 경우 (개별 사건이 전체로 확산)

### 출력 (hierarchy.json)

```json
{
  "tier_analysis": {
    "C3": {"korean_market": {"stance_delta": -0.15, "volatility_delta": 0.35}},
    "C2": {
      "energy_sector": {"stance_delta": 0.42, "volatility_delta": 0.28},
      "semiconductor": {"stance_delta": -0.31, "volatility_delta": 0.55}
    },
    "C1": { ... },
    "C0": { ... }
  },
  "propagation_direction": "mixed",
  "most_dynamic_tier": "C2",
  "most_dynamic_community": "energy_sector",
  "key_insight": "C2 섹터 수준에서 가장 극적인 분화가 발생. 에너지 섹터 stance +0.42 vs 반도체 -0.31"
}
```

---

## 4. 분석공간 2: 시간공간 (Temporal Space)

### 핵심 질문
**"언제, 어떤 시간 순서로 발생했는가?"**

### 분석 항목

#### 4.1 이벤트-반응 시차 분석

```python
def analyze_temporal(data: SimulationData) -> dict:
    results = {}

    # 이벤트별 반응 시차 측정
    for event in data.events_log:
        reactions = []
        for action in data.actions_log:
            if is_caused_by(action, event, data):
                reactions.append({
                    "action": action.name,
                    "actor": action.actor,
                    "delay_rounds": action.round - event.round,
                })
        results["event_reactions"][event.uid] = {
            "event_name": event.name,
            "injection_round": event.round,
            "reaction_count": len(reactions),
            "avg_delay": mean(r["delay_rounds"] for r in reactions),
            "first_reactor": min(reactions, key=lambda r: r["delay_rounds"]),
            "reactions": reactions
        }

    return results
```

#### 4.2 선행지표 탐지

어떤 노드의 변화가 다른 노드보다 **지속적으로 먼저** 움직이는 패턴:

```python
def detect_leading_indicators(data):
    # 각 노드 쌍의 stance 변화 시계열 교차상관 분석
    for node_a, node_b in all_pairs:
        correlation, lag = cross_correlate(
            node_a.stance_history, node_b.stance_history
        )
        if correlation > 0.7 and lag > 0:
            leading_indicators.append({
                "leader": node_a.uid,
                "follower": node_b.uid,
                "correlation": correlation,
                "lag_rounds": lag
            })
```

#### 4.3 생명주기 단계 분류

각 엔티티의 시뮬레이션 내 생명주기:

```
활성화 → 과열 → 냉각 → 안정화
(activity↑)  (vol↑)  (vol↓)  (vol→0)
```

### 출력 (temporal.json)

```json
{
  "event_reactions": {
    "wti_100": {
      "injection_round": 1,
      "first_reactor": {"actor": "foreign_investor", "delay": 1},
      "avg_delay": 1.8,
      "cascading_order": ["foreign_investor", "kospi", "samsung", "uri_tech"]
    }
  },
  "leading_indicators": [
    {"leader": "wti_price", "follower": "energy_sector", "lag": 0, "correlation": 0.95},
    {"leader": "foreign_investor", "follower": "semiconductor", "lag": 1, "correlation": 0.82}
  ],
  "lifecycle_phases": {
    "uri_tech": ["inactive", "activated", "overheated", "cooling", "stable"]
  }
}
```

---

## 5. 분석공간 3: 재귀공간 (Recursive Space)

### 핵심 질문
**"자기강화/자기억제 피드백 루프가 있는가?"**

### 분석 항목

#### 5.1 피드백 루프 탐지

```python
def detect_feedback_loops(data: SimulationData) -> dict:
    # 그래프에서 사이클 탐지
    cycles = find_cycles(data.graph, max_length=5)

    loops = []
    for cycle in cycles:
        # 사이클 내 속성 변화 방향 분석
        changes = [get_stance_change(node, data) for node in cycle]

        if all(c > 0 for c in changes) or all(c < 0 for c in changes):
            loop_type = "positive"  # 양의 피드백 (자기강화)
        elif alternating_signs(changes):
            loop_type = "negative"  # 음의 피드백 (자기억제)
        else:
            loop_type = "mixed"

        loops.append({
            "nodes": [n.uid for n in cycle],
            "edges": [e.link_type for e in cycle_edges(cycle)],
            "type": loop_type,
            "strength": mean(abs(c) for c in changes),
            "stability": "unstable" if loop_type == "positive" else "stable",
            "description": describe_loop(cycle, loop_type)
        })

    return {"feedback_loops": loops}
```

#### 5.2 프랙탈 패턴 탐지

동일 패턴이 서로 다른 계층(C0~C3)에서 반복되는지:

```python
def detect_fractal_patterns(data):
    patterns = []
    for tier in range(3):  # C0~C2
        tier_pattern = extract_change_pattern(data, tier)
        next_tier_pattern = extract_change_pattern(data, tier + 1)
        similarity = pattern_similarity(tier_pattern, next_tier_pattern)
        if similarity > 0.6:
            patterns.append({
                "tiers": [tier, tier + 1],
                "similarity": similarity,
                "description": f"C{tier}과 C{tier+1}에서 동일한 {tier_pattern.name} 패턴 반복"
            })
    return patterns
```

### 출력 (recursive.json)

```json
{
  "feedback_loops": [
    {
      "nodes": ["foreign_investor", "samsung", "kospi"],
      "edges": ["SELLS", "BELONGS_TO", "IMPACTS"],
      "type": "positive",
      "strength": 0.45,
      "stability": "unstable",
      "description": "외국인 매도 → 주가 하락 → 추가 매도 (자기강화 루프)"
    },
    {
      "nodes": ["kospi", "retail_investor", "samsung"],
      "edges": ["IMPACTS", "BUYS", "BELONGS_TO"],
      "type": "negative",
      "strength": 0.32,
      "stability": "stable",
      "description": "주가 하락 → 저가 매수 유입 → 주가 반등 (자기억제 루프)"
    }
  ],
  "fractal_patterns": [
    {
      "tiers": [1, 2],
      "similarity": 0.78,
      "description": "개별 종목(C1)과 섹터(C2) 수준에서 동일한 급락-반등 패턴 반복"
    }
  ]
}
```

---

## 6. 분석공간 4: 구조공간 (Structural Space)

### 핵심 질문
**"엔티티 간 관계 구조가 어떻게 변했는가?"**

### 분석 항목

#### 6.1 중심성 변화 분석

```python
def analyze_structural(data: SimulationData) -> dict:
    # 시뮬레이션 전후 중심성 비교
    initial_centrality = compute_centrality(data.snapshots[0])
    final_centrality = compute_centrality(data.snapshots[-1])

    centrality_changes = {}
    for node_uid in initial_centrality:
        centrality_changes[node_uid] = {
            "betweenness": {
                "before": initial_centrality[node_uid]["betweenness"],
                "after": final_centrality[node_uid]["betweenness"],
                "delta": final_centrality[node_uid]["betweenness"]
                         - initial_centrality[node_uid]["betweenness"]
            },
            "pagerank": { ... },
            "degree": { ... },
        }

    return {
        "centrality_changes": centrality_changes,
        "top_risers": top_n(centrality_changes, key="betweenness.delta", n=5),
        "top_fallers": bottom_n(centrality_changes, key="betweenness.delta", n=5),
    }
```

#### 6.2 브릿지 노드 식별

커뮤니티 간 연결 역할을 하는 노드:

```cypher
MATCH (a:Entity)-[:MEMBER_OF]->(c1:Community),
      (b:Entity)-[:MEMBER_OF]->(c2:Community),
      (a)-[r]-(b)
WHERE c1 <> c2
WITH a, count(DISTINCT c2) AS bridge_count
WHERE bridge_count >= 2
RETURN a.uid, a.name, bridge_count
ORDER BY bridge_count DESC
```

#### 6.3 구조적 공백 (Structural Holes)

연결이 약하거나 없는 영역:

```python
def find_structural_holes(graph):
    # 커뮤니티 간 연결 밀도 매트릭스
    inter_community_density = {}
    for c1, c2 in community_pairs:
        density = count_edges_between(c1, c2) / (len(c1) * len(c2))
        inter_community_density[(c1.uid, c2.uid)] = density

    # 밀도가 매우 낮은 쌍 = 구조적 공백
    holes = [pair for pair, d in inter_community_density.items() if d < 0.05]
    return holes
```

#### 6.4 엣지 생성/소멸 패턴

```python
def edge_dynamics(data):
    created_by_type = Counter()
    expired_by_type = Counter()

    for snapshot in data.snapshots:
        for edge in snapshot.edge_created:
            created_by_type[edge.link_type] += 1
        for edge in snapshot.edge_expired:
            expired_by_type[edge.link_type] += 1

    return {
        "edge_creation_rate": created_by_type,
        "edge_expiration_rate": expired_by_type,
        "net_growth_by_type": {
            t: created_by_type[t] - expired_by_type[t]
            for t in set(created_by_type) | set(expired_by_type)
        }
    }
```

### 출력 (structural.json)

```json
{
  "centrality_changes": {
    "top_risers": [
      {"node": "ai_datacenter", "betweenness_delta": +0.18, "role": "bridge"}
    ],
    "top_fallers": [
      {"node": "samsung", "pagerank_delta": -0.12}
    ]
  },
  "bridge_nodes": [
    {"node": "ai_datacenter", "bridges": ["semiconductor", "energy"], "description": "반도체↔전력 브릿지"}
  ],
  "structural_holes": [
    {"pair": ["defense_sector", "battery_sector"], "density": 0.02}
  ],
  "edge_dynamics": {
    "net_growth": {"OPPOSES": +3, "ALLIED_WITH": -1, "DEPENDS_ON": +2}
  }
}
```

---

## 7. 분석공간 5: 인과공간 (Causal Space)

### 핵심 질문
**"무엇이 원인이고, 무엇이 결과인가?"**

### 분석 항목

#### 7.1 인과 DAG 구축

이벤트-반응-결과의 방향 비순환 그래프:

```python
def build_causal_dag(data: SimulationData) -> nx.DiGraph:
    dag = nx.DiGraph()

    # 이벤트 → 영향 노드
    for event in data.events_log:
        for impact in event.impacted_nodes:
            dag.add_edge(event.uid, impact.uid,
                         weight=impact.effect, type="direct_impact")

    # 메타엣지 발동 체인
    for me in data.meta_edges_log:
        dag.add_edge(me.trigger_source, me.affected_target,
                     weight=me.effect_magnitude, type="meta_edge")

    # Action 인과
    for action in data.actions_log:
        dag.add_edge(action.actor, action.target or action.actor,
                     weight=action.effect_magnitude, type="action")

    # 순환 제거 (시간순으로 방향 결정)
    remove_cycles_by_time(dag, data)

    return dag
```

#### 7.2 Impact Analysis

특정 노드를 제거하면 무엇이 변하는지:

```python
def impact_analysis(dag, target_node):
    """target_node의 모든 하류(downstream) 영향 계산"""
    downstream = nx.descendants(dag, target_node)
    impact_scores = {}

    for node in downstream:
        paths = nx.all_simple_paths(dag, target_node, node)
        total_impact = sum(
            prod(dag[u][v]["weight"] for u, v in zip(path, path[1:]))
            for path in paths
        )
        impact_scores[node] = total_impact

    return {
        "root_cause": target_node,
        "downstream_count": len(downstream),
        "impact_scores": impact_scores,
        "most_affected": max(impact_scores, key=impact_scores.get)
    }
```

#### 7.3 근본 원인 식별

```python
def find_root_causes(dag):
    """진입 차수(in-degree)가 0인 노드 = 근본 원인"""
    roots = [n for n in dag.nodes if dag.in_degree(n) == 0]
    return sorted(roots, key=lambda n: len(nx.descendants(dag, n)), reverse=True)
```

### 출력 (causal.json)

```json
{
  "causal_dag": {
    "nodes": 24,
    "edges": 38,
    "root_causes": ["wti_100_breakthrough", "iran_cia_negotiation"],
    "terminal_effects": ["uri_tech_surge", "samsung_resistance_test"]
  },
  "impact_analysis": {
    "wti_100_breakthrough": {
      "downstream_count": 18,
      "most_affected": "energy_sector",
      "causal_chains": [
        "wti→kospi→foreign_investor→samsung→semiconductor_sector",
        "wti→energy_sector→uri_tech→nuclear_policy"
      ]
    }
  },
  "root_cause_ranking": [
    {"node": "wti_100_breakthrough", "downstream": 18, "total_impact": 4.2},
    {"node": "iran_cia_negotiation", "downstream": 8, "total_impact": 1.8}
  ]
}
```

---

## 8. 분석공간 6: 다중공간 (Cross-Space)

### 핵심 질문
**"5개 공간의 분석을 교차하면 어떤 창발적 인사이트가 나오는가?"**

### 분석 항목

#### 8.1 공간 간 상관관계

```python
def analyze_cross_space(hierarchy, temporal, recursive, structural, causal):
    insights = []

    # 계층 × 시간: 상위 계층이 먼저 변화하는가?
    h_t = correlate_hierarchy_temporal(hierarchy, temporal)
    if h_t["top_down_correlation"] > 0.7:
        insights.append({
            "spaces": ["hierarchy", "temporal"],
            "finding": "거시(C3) 변화가 미시(C0)에 선행",
            "correlation": h_t["top_down_correlation"],
            "implication": "정책/거시 이벤트가 개별 종목에 탑다운으로 영향"
        })

    # 구조 × 인과: 브릿지 노드가 인과 체인의 매개체인가?
    s_c = correlate_structural_causal(structural, causal)
    for bridge in structural["bridge_nodes"]:
        if bridge["node"] in causal["causal_dag"]["intermediate_nodes"]:
            insights.append({
                "spaces": ["structural", "causal"],
                "finding": f"{bridge['node']}가 구조적 브릿지이자 인과적 매개체",
                "implication": "이 노드의 변화가 섹터 간 영향 전파의 핵심"
            })

    # 재귀 × 시간: 피드백 루프의 주기와 시장 변동 주기의 상관
    r_t = correlate_recursive_temporal(recursive, temporal)

    # 계층 × 인과: 인과 체인이 특정 계층에 집중되는가?
    h_c = correlate_hierarchy_causal(hierarchy, causal)

    # 구조 × 재귀: 구조적 공백이 피드백 루프를 차단하는가?
    s_r = correlate_structural_recursive(structural, recursive)

    return {
        "cross_insights": insights,
        "meta_patterns": extract_meta_patterns(insights),
        "emergent_findings": [i for i in insights if i.get("emergent", False)]
    }
```

#### 8.2 메타 패턴 추출

단일 공간에서는 보이지 않지만 교차 분석에서 드러나는 패턴:

```python
def extract_meta_patterns(insights):
    patterns = []

    # 패턴 1: "브릿지-인과-피드백 삼중주"
    # 구조적 브릿지 노드가 인과 DAG의 매개이면서 동시에 피드백 루프의 일부
    # → 이 노드는 시스템의 핵심 레버리지 포인트

    # 패턴 2: "계층-시간 역전"
    # 하위 계층(C0)의 변화가 상위 계층(C2)보다 먼저 발생
    # → 바텀업 창발 현상의 증거

    # 패턴 3: "인과-재귀 공명"
    # 인과 체인의 종점이 피드백 루프의 시작점과 일치
    # → 한 번 시작되면 자기 증폭하는 위험 구조

    return patterns
```

### 출력 (cross_space.json)

```json
{
  "cross_insights": [
    {
      "spaces": ["structural", "causal"],
      "finding": "AI 데이터센터가 반도체↔전력 브릿지이자 인과 매개체",
      "implication": "에너지 정책 변화가 반도체 섹터에 미치는 영향의 핵심 경로"
    },
    {
      "spaces": ["hierarchy", "temporal"],
      "finding": "C2 섹터 변화가 C0 개별 종목보다 평균 0.8라운드 선행",
      "implication": "섹터 수준 분석이 개별 종목 예측에 선행지표로 활용 가능"
    }
  ],
  "meta_patterns": [
    {
      "name": "bridge_leverage_point",
      "description": "AI데이터센터는 구조적 브릿지 + 인과 매개 + 피드백 루프 노드",
      "leverage_score": 0.92
    }
  ]
}
```

---

## 9. Aggregator: 6개 공간 통합

### 출력 (aggregated.json)

```json
{
  "simulation_summary": {
    "total_rounds": 10,
    "total_events": 5,
    "total_actions": 34,
    "total_meta_edges_fired": 47,
    "community_migrations": 3
  },
  "key_findings": [
    {
      "rank": 1,
      "finding": "WTI 유가 100달러 돌파가 전체 시뮬레이션의 근본 원인 (인과공간)",
      "supporting_spaces": ["causal", "temporal", "hierarchy"],
      "confidence": 0.95
    },
    {
      "rank": 2,
      "finding": "에너지-반도체 간 AI 데이터센터를 통한 구조적 연결이 핵심 (구조×인과)",
      "supporting_spaces": ["structural", "causal", "cross_space"],
      "confidence": 0.88
    },
    {
      "rank": 3,
      "finding": "외국인 매도→주가하락→추가매도 양의 피드백 루프 존재 (재귀공간)",
      "supporting_spaces": ["recursive", "temporal"],
      "confidence": 0.82
    }
  ],
  "spaces": {
    "hierarchy": { "summary": "C2 섹터 수준에서 가장 극적 분화" },
    "temporal": { "summary": "유가→매도→환율 순서의 48시간 인과 체인" },
    "recursive": { "summary": "양·음 피드백 루프 각 2개 탐지" },
    "structural": { "summary": "AI데이터센터가 핵심 브릿지 노드로 부상" },
    "causal": { "summary": "WTI유가가 인과 DAG의 루트 노드" },
    "cross_space": { "summary": "브릿지-인과-피드백 삼중주 패턴 발견" }
  }
}
```

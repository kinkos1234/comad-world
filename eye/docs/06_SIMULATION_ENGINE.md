# 06. 시뮬레이션 엔진 설계 (Layer 2)

## 1. 설계 원칙

**LLM 호출 0회**. 모든 시뮬레이션 판단은 다음 4가지로 수행한다:

1. **메타엣지 규칙** — 관계 생성/소멸/속성 변경 (→ 05_META_EDGE.md)
2. **Action Type 전제조건** — 엔티티 행동 결정 (→ 02_ONTOLOGY_SCHEMA.md)
3. **그래프 연산** — Cypher 쿼리 기반 전파·집계
4. **Active Metadata 버스** — 속성 변경의 자동 전파 및 캐시 무효화 (→ 12_ONTOLOGY_NATIVE_STRUCTURE.md)

---

## 2. 라운드 기반 실행 모델

### 2.1 라운드 구조

```
Round N:
  ┌─ Phase A: 이벤트 주입 ────────────────────────┐
  │  이벤트 큐에서 현재 라운드의 이벤트 추출        │
  │  직접 영향 대상 노드에 충격 적용                │
  └───────────────────────────────────────────────┘
                    │
  ┌─ Phase B: 영향 전파 ────────────────────────────┐
  │  관계 경로를 따라 영향이 전파                     │
  │  감쇠율 적용: effect × decay^distance            │
  └───────────────────────────────────────────────┘
                    │
  ┌─ Phase C: 메타엣지 평가 ──────────────────────┐
  │  on_change: 변경된 속성에 의해 트리거된 규칙    │
  │  evaluate: 전체 활성 규칙 순차 평가             │
  │  충돌 해결 → 효과 일괄 적용                     │
  └───────────────────────────────────────────────┘
                    │
  ┌─ Phase D: Action 해결 ──────────────────────────┐
  │  각 활성 엔티티의 허용 Action 순회               │
  │  전제조건 충족 시 실행 → 그래프 상태 변경        │
  │  쿨다운 체크                                     │
  └───────────────────────────────────────────────┘
                    │
  ┌─ Phase E: 자연 감쇠 ────────────────────────────┐
  │  volatility 자연 감쇠: v *= (1 - decay_rate)    │
  │  임시 속성(price_pressure 등) 리셋              │
  └───────────────────────────────────────────────┘
                    │
  ┌─ Phase F: 커뮤니티 재계산 (조건부) ──────────────┐
  │  매 N 라운드마다 Leiden 재실행                    │
  │  커뮤니티 변경 감지 → 이동 이력 기록             │
  └───────────────────────────────────────────────┘
                    │
  ┌─ Phase G: Active Metadata 전파 ──────────────────┐
  │  속성 변경 이벤트 수집 → 의존 메타데이터 갱신    │
  │  커뮤니티 요약 무효화 플래그 설정                │
  │  분석 캐시 무효화                                │
  └───────────────────────────────────────────────┘
                    │
  ┌─ Phase H: 스냅샷 저장 ──────────────────────────┐
  │  변경된 노드/엣지만 JSONL로 기록                 │
  │  라운드 요약 통계 생성                           │
  └───────────────────────────────────────────────┘
```

### 2.2 라운드 수 결정

기본값: **10 라운드** (설정 가능)

라운드 수는 시드데이터의 이벤트 수에 비례하여 자동 조정:
- 이벤트 N개 → max(N + 3, 10) 라운드 (이벤트 주입 후 여파 관찰용 여유 라운드)

---

## 3. Phase A: 이벤트 주입

### 3.1 이벤트 체인 구축

Layer 0에서 추출된 이벤트를 **시간순 큐**로 구성한다:

```python
class EventChain:
    def __init__(self, events: list[Event]):
        # 시드데이터 내 등장 순서 = 시간 순서로 간주
        self.queue = deque(sorted(events, key=lambda e: e.round))

    def next_events(self, round: int) -> list[Event]:
        """현재 라운드에 주입할 이벤트 반환"""
        result = []
        while self.queue and self.queue[0].round <= round:
            result.append(self.queue.popleft())
        return result
```

### 3.2 이벤트 라운드 배정 전략

시드데이터에 명시적 시간 정보가 있으면 활용, 없으면 균등 분배:

```
이벤트 5개, 라운드 10개:
  Round 1: Event 1
  Round 3: Event 2
  Round 5: Event 3
  Round 6: Event 4
  Round 8: Event 5
  Round 9~10: 여파 관찰
```

### 3.3 직접 영향 계산

```cypher
-- 이벤트가 직접 IMPACTS하는 엔티티 탐색
MATCH (e:Event {uid: $event_uid})-[r:IMPACTS]->(n:Entity)
RETURN n.uid, r.weight, n.susceptibility

-- 영향 적용
-- delta = event.magnitude × edge.weight × node.susceptibility
```

---

## 4. Phase B: 영향 전파

### 4.1 전파 알고리즘

이벤트 직접 영향을 받은 노드에서 시작하여, 관계 경로를 따라 영향이 전파된다.

```python
def propagate(graph, impacted_nodes, decay=0.6, max_hops=3):
    """BFS 기반 영향 전파"""
    visited = set()
    queue = deque()

    # 직접 영향 노드를 큐에 삽입
    for node, effect in impacted_nodes:
        queue.append((node, effect, 0))  # (node, effect, distance)
        visited.add(node.uid)

    propagation_log = []

    while queue:
        node, effect, distance = queue.popleft()

        if distance >= max_hops:
            continue

        # 연결된 노드로 전파
        neighbors = graph.query(
            "MATCH (n:Entity {uid: $uid})-[r]->(m:Entity) "
            "WHERE NOT m.uid IN $visited "
            "RETURN m.uid, r.weight, type(r) AS rel_type, m.susceptibility",
            uid=node.uid, visited=list(visited)
        )

        for neighbor in neighbors:
            propagated_effect = effect * decay * neighbor.weight * neighbor.susceptibility
            if abs(propagated_effect) < 0.01:  # 임계값 이하면 전파 중단
                continue

            # 속성 변경 적용
            apply_effect(neighbor, propagated_effect)
            propagation_log.append({
                "source": node.uid,
                "target": neighbor.uid,
                "effect": propagated_effect,
                "distance": distance + 1
            })

            visited.add(neighbor.uid)
            queue.append((neighbor, propagated_effect, distance + 1))

    return propagation_log
```

### 4.2 전파 규칙

| 관계 유형 | 전파 방향 | 전파 속성 | 특수 규칙 |
|-----------|-----------|-----------|-----------|
| `IMPACTS` | 정방향 | volatility, stance | magnitude에 비례 |
| `DEPENDS_ON` | 역방향 | volatility | 의존 대상 불안 → 의존자 불안 |
| `INFLUENCES` | 정방향 | stance | influence_score 가중 |
| `COMPETES_WITH` | 양방향 | stance (반전) | 한쪽 stance ↑ → 상대 stance ↓ |
| `ALLIED_WITH` | 양방향 | stance (동조) | 한쪽 stance 변화 → 상대 동조 |
| `LEADS_TO` | 정방향 | event activation | 이벤트 체인 트리거 |

---

## 5. Phase C: 메타엣지 평가

→ 05_META_EDGE.md의 "평가 엔진" 절 참조

실행 요약:
1. `on_change` 트리거: Phase A/B에서 변경된 속성을 감지하여 해당 규칙 평가
2. `evaluate` 트리거: priority 순으로 전체 활성 규칙 평가
3. 충돌 해결 후 효과 일괄 적용

---

## 6. Phase D: Action 해결

### 6.1 Action 실행 루프

```python
def resolve_actions(graph, ontology, round_num):
    action_log = []

    # 모든 활성 엔티티 순회 (influence_score 내림차순)
    active_entities = graph.query(
        "MATCH (n:Entity) WHERE n.activity_level > 0.1 "
        "RETURN n ORDER BY n.influence_score DESC"
    )

    for entity in active_entities:
        # 이 엔티티가 수행 가능한 Action 목록
        allowed_actions = ontology.get_actions(entity.object_type)

        for action in sorted(allowed_actions, key=lambda a: -a.priority):
            # 쿨다운 체크
            if not check_cooldown(entity, action, round_num):
                continue

            # 전제조건 평가
            precondition_results = evaluate_preconditions(
                action.preconditions, entity, graph
            )

            if all(r.met for r in precondition_results):
                # Action 실행: 효과 적용
                effects = apply_action_effects(action, entity, graph)

                action_log.append({
                    "round": round_num,
                    "action": action.name,
                    "actor": entity.uid,
                    "target": effects.get("target"),
                    "preconditions_met": precondition_results,
                    "effects_applied": effects
                })

                # 한 엔티티는 라운드당 최대 1개 Action 실행
                break

    return action_log
```

### 6.2 Action 실행 우선순위

같은 엔티티에 여러 Action이 가능할 때:
1. `priority` 높은 것 우선
2. priority 동일 시: 전제조건 충족 강도(margin) 큰 것 우선
3. 라운드당 엔티티별 최대 1 Action (설정 가능)

---

## 7. Phase E: 자연 감쇠

```python
def apply_natural_decay(graph, config):
    graph.query("""
        MATCH (n:Entity)
        WHERE n.volatility > 0
        SET n.volatility = n.volatility * (1 - $decay_rate),
            n.price_pressure = 0
    """, decay_rate=config.volatility_decay)
```

매 라운드 종료 시:
- `volatility` × (1 - decay_rate) — 외부 충격 없으면 자연 안정화
- `price_pressure` 리셋 — 다음 라운드에 새로 계산
- 만료된 엣지(`expired_at <= current_round`) 비활성화

---

## 8. Phase F: 커뮤니티 재계산

### 조건
매 `community_refresh_interval` 라운드마다 실행 (기본: 3라운드)

### 처리

```python
def refresh_communities(graph, previous_communities):
    # 1. Neo4j에서 현재 그래프 추출
    edges = graph.query("MATCH (a)-[r]->(b) WHERE r.expired_at IS NULL "
                        "RETURN a.uid, b.uid, r.weight")

    # 2. Leiden 재실행
    new_communities = detect_communities(edges)

    # 3. 이동 감지
    migrations = []
    for entity in graph.all_entities():
        old_comm = previous_communities.get(entity.uid)
        new_comm = new_communities.get(entity.uid)
        if old_comm != new_comm:
            migrations.append({
                "entity": entity.uid,
                "from": old_comm,
                "to": new_comm,
                "round": current_round
            })

    # 4. Neo4j 커뮤니티 관계 업데이트
    update_community_memberships(graph, new_communities)

    return new_communities, migrations
```

### 커뮤니티 재편의 의미

커뮤니티 재편은 시뮬레이션의 **구조적 변화**를 나타낸다:
- 노드가 다른 커뮤니티로 이동 = 해당 엔티티의 소속/정체성 변화
- 커뮤니티 분열 = 내부 갈등으로 인한 분화
- 커뮤니티 병합 = 공통 이해관계로 인한 통합

이 변화는 Layer 3의 **계층공간 분석**과 **구조공간 분석**에서 핵심 입력이 된다.

---

## 9. Phase G: Active Metadata 전파

Phase A~F에서 발생한 모든 속성 변경을 수집하고, 의존 메타데이터를 자동 갱신한다.

```python
def propagate_active_metadata(graph, changes, metadata_bus):
    """Active Metadata 이벤트 버스를 통한 변경 전파"""

    # 1. 속성 변경 이벤트 수집
    property_changes = collect_property_changes(changes)

    for change in property_changes:
        # 2. 커뮤니티 요약 무효화
        community = graph.get_community(change.entity_uid)
        if community:
            community.summary_stale = True

        # 3. 의존 엔티티 메타데이터 갱신
        if change.property in ("stance", "volatility", "influence_score"):
            dependents = graph.query(
                "MATCH (n {uid: $uid})<-[:DEPENDS_ON]-(d) RETURN d.uid",
                uid=change.entity_uid
            )
            for dep_uid in dependents:
                metadata_bus.emit("upstream_changed", {
                    "entity": dep_uid,
                    "upstream": change.entity_uid,
                    "property": change.property,
                    "delta": change.new_val - change.old_val,
                    "round": change.round
                })

        # 4. 분석 캐시 무효화 플래그
        metadata_bus.invalidate_analysis_cache(
            entity_uid=change.entity_uid,
            spaces=["structural", "causal"]  # 속성 변경에 민감한 분석공간
        )
```

Active Metadata는 시뮬레이션의 "수동 기록"이 아닌 "능동 전파" 메커니즘이다:
- 커뮤니티 요약이 stale 상태면, Layer 4 리포트 생성 시 재계산됨
- 분석 캐시가 무효화되면, Layer 3 재분석 시 해당 부분만 재실행
- 의존 엔티티의 `upstream_changed` 메타데이터는 다음 라운드의 Action 전제조건에서 참조 가능

→ Active Metadata 개념 상세: [02_ONTOLOGY_SCHEMA.md](./02_ONTOLOGY_SCHEMA.md) §9, [12_ONTOLOGY_NATIVE_STRUCTURE.md](./12_ONTOLOGY_NATIVE_STRUCTURE.md) §6

---

## 10. Phase H: 스냅샷 저장

### 스냅샷 전략: 변경분만 기록 (Diff-based)

```python
def save_snapshot(graph, round_num, changes):
    snapshot = {
        "round": round_num,
        "timestamp": datetime.now().isoformat(),
        "node_changes": [],      # 변경된 노드 속성
        "edge_created": [],      # 새로 생성된 엣지
        "edge_expired": [],      # 소멸된 엣지
        "actions_executed": [],   # 실행된 Action
        "meta_edges_fired": [],  # 발동된 메타엣지
        "community_migrations": [],  # 커뮤니티 이동
        "summary": {
            "total_nodes": graph.node_count(),
            "total_active_edges": graph.active_edge_count(),
            "avg_volatility": graph.avg("volatility"),
            "stance_distribution": graph.histogram("stance", bins=10),
            "community_count": {f"C{t}": count for t, count in graph.community_counts()},
        }
    }

    save_jsonl(f"data/snapshots/round_{round_num:03d}.jsonl", snapshot)
```

---

## 11. 전체 실행 흐름

```python
async def run_simulation(config):
    graph = Neo4jClient(config.neo4j)
    ontology = load_ontology("data/extraction/ontology.json")
    meta_edges = load_meta_edges("config/meta_edges.yaml")
    event_chain = EventChain(ontology.initial_events)

    communities = load_json("data/communities/communities.json")
    max_rounds = config.simulation.max_rounds

    # 초기 스냅샷
    save_snapshot(graph, round_num=0, changes={})

    for round_num in range(1, max_rounds + 1):
        changes = {}

        # Phase A: 이벤트 주입
        events = event_chain.next_events(round_num)
        for event in events:
            impacted = inject_event(graph, event)
            changes["events"] = events
            changes["impacted"] = impacted

        # Phase B: 영향 전파
        if impacted:
            propagation = propagate(graph, impacted, config.simulation.propagation_decay)
            changes["propagation"] = propagation

        # Phase C: 메타엣지 평가
        meta_results = evaluate_meta_edges(graph, meta_edges, changes)
        changes["meta_edges"] = meta_results

        # Phase D: Action 해결
        action_log = resolve_actions(graph, ontology, round_num)
        changes["actions"] = action_log

        # Phase E: 자연 감쇠
        apply_natural_decay(graph, config.simulation)

        # Phase F: 커뮤니티 재계산 (조건부)
        if round_num % config.simulation.community_refresh_interval == 0:
            communities, migrations = refresh_communities(graph, communities)
            changes["migrations"] = migrations

        # Phase G: Active Metadata 전파
        propagate_active_metadata(graph, changes, metadata_bus)

        # Phase H: 스냅샷 저장
        save_snapshot(graph, round_num, changes)

    return SimulationResult(
        total_rounds=max_rounds,
        total_events=len(ontology.initial_events),
        total_actions=sum(len(s.get("actions", [])) for s in snapshots),
        llm_calls=0
    )
```

---

## 12. 종료 조건

시뮬레이션은 다음 조건 중 하나가 충족되면 조기 종료할 수 있다:

1. **수렴**: 최근 3라운드 동안 모든 노드의 stance/volatility 변화량 합계 < 0.01
2. **이벤트 소진 + 안정화**: 모든 이벤트가 주입되고, volatility 평균 < 0.1
3. **최대 라운드 도달**: config.simulation.max_rounds

---

## 13. 검증 및 디버깅

### 12.1 불변량 체크 (매 라운드 종료 시)

```python
def check_invariants(graph):
    # stance 범위
    assert all(-1.0 <= n.stance <= 1.0 for n in graph.all_entities())
    # volatility 범위
    assert all(0.0 <= n.volatility <= 1.0 for n in graph.all_entities())
    # 자기 참조 엣지 없음
    assert graph.query("MATCH (n)-[r]->(n) RETURN count(r)")[0] == 0
    # BELONGS_TO 비순환
    assert not graph.has_cycle("BELONGS_TO")
```

### 12.2 라운드 요약 출력

매 라운드 종료 시 CLI에 요약을 출력한다:

```
[Round 3/10] Events: 1 | Actions: 4 | Meta-edges fired: 7
  Volatility: avg=0.42 max=0.89(WTI유가)
  Stance shift: +0.15(원전섹터) -0.22(반도체섹터)
  Community changes: 1 migration (한선엔지니어링: C1_기존→C1_에너지)
  New edges: 3 OPPOSES, 1 ALLIED_WITH | Expired: 2
```

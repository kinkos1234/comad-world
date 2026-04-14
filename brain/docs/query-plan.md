# Query Plan Capture Guide

- **Status:** Proposed observability note
- **Date:** 2026-04-14
- **Owner:** Comad Brain maintainer
- **Related:** `docs/slo.md`, `scripts/comad`

## Context

`brain`의 GraphRAG 질의는 Neo4j planner 품질과 page cache 상태에 민감하다. p95가 흔들릴 때는 "느리다"는 체감만 적지 말고, 어떤 연산자가 실제 병목인지 남겨야 재현 가능한 성능 회귀 분석이 된다. 이 문서는 운영 중인 graph search 쿼리에서 Cypher execution plan을 캡처하는 최소 절차를 정리한다.

## EXPLAIN vs PROFILE

- `EXPLAIN`은 쿼리를 실행하지 않고 계획만 본다. 결과는 비어 있고 데이터 변경도 발생하지 않으므로, 운영 환경에서 먼저 shape를 확인할 때 기본값으로 쓴다.
- `PROFILE`은 쿼리를 실제 실행하면서 각 operator를 통과한 row 수와 storage 접근량을 수집한다. 어느 단계가 가장 많은 DB hit를 발생시키는지 보이지만, 실행 오버헤드가 있으므로 성능 분석 시점에만 제한적으로 사용한다.
- 운영 절차는 `EXPLAIN`으로 인덱스 사용 여부와 전체 plan shape를 본 뒤, 동일 파라미터로 `PROFILE`을 1회 실행해 병목 operator를 고정하는 순서를 권장한다.

## Capture Procedure

1. `cypher-shell -a neo4j://localhost:7688 -u neo4j -p "$NEO4J_PASSWORD"`로 대상 인스턴스에 붙는다.
2. 먼저 `EXPLAIN`을 붙여 planner가 `NodeIndexSeek` 또는 `RelationshipIndexSeek`를 쓰는지 확인한다.
3. 실제 지연이 재현되는 파라미터로 `PROFILE`을 1회만 실행하고, 총 DB hits와 상위 operator 3개를 기록한다.
4. 결과는 날짜, 질의문, 파라미터, 총 latency, 최상위 병목 operator 순으로 남긴다.

## Example Query

```cypher
PROFILE
MATCH (a:Article)-[:MENTIONS]->(e:Entity)
WHERE e.name CONTAINS $query
WITH a, e
ORDER BY a.published_at DESC
LIMIT 20
MATCH (a)-[:FROM_SOURCE]->(s:Source)
RETURN a.title, e.name, s.name, a.published_at
```

예상되는 `PROFILE` 출력 형태는 다음과 같다. 최상단 `ProduceResults` 아래에 `Projection`, `Sort`, `Limit`, `Expand(All)` 또는 `Expand(Into)`, 그리고 핵심 탐색 연산자인 `NodeIndexSeek`가 트리로 보인다. 정상 상태라면 row 수는 `LIMIT 20` 이후 급격히 줄고, DB hit는 `NodeIndexSeek`와 첫 번째 `Expand` 구간에 집중된다. 반대로 `NodeByLabelScan`이 나타나거나 `Sort` 이전 row 수가 과도하게 크면, 인덱스 누락 또는 필터 선택도 저하를 의심해야 한다.

## Cache Hit Ratio Monitoring

CSV metrics가 기본 활성화된 환경이라면 다음 명령으로 page cache hit ratio를 바로 본다.

```bash
tail -f "$NEO4J_HOME/metrics/neo4j.page_cache.hit_ratio.csv"
```

이 값은 0.98 이상을 안정 구간으로 보고, 0.95 아래로 반복 하락하면 메모리 또는 쿼리 패턴 회귀를 의심한다. Prometheus를 켠 환경이라면 동일 지표가 `neo4j_page_cache_hit_ratio` 계열로 노출되므로, SLI 1 분석 시 query latency와 함께 같은 타임윈도우에서 비교한다.

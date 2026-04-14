# Chaos Drill Playbook

- **Status:** Proposed
- **Date:** 2026-04-14
- **Owner:** Comad World maintainer (@kinkos1234)
- **Related:** `docs/slo.md`, `scripts/comad`, `brain/docs/query-plan.md`

## 시나리오 1: brain MCP 다운

- **예상 동작:** `eye`와 `ear`는 즉시 실패하지 않고 캐시 또는 마지막 성공 결과를 사용하며 warning을 남긴다.
- **수동 재현:** `pkill -f brain` 또는 Neo4j `7688` 인스턴스를 중지해 `brain` MCP 의존 경로를 끊는다.
- **복구:** `cd brain && bun run mcp`
- **검증:** 10분 내 graph 질의가 정상 응답으로 복귀하고 warning이 신규 성공 로그로 종료되는지 확인한다.

## 시나리오 2: eye MCP 다운

- **예상 동작:** `brain`과 `voice`는 분석 결과 생성을 건너뛰고 원본 데이터와 경고 메시지로 graceful degrade 한다.
- **수동 재현:** `pkill -f eye` 또는 `eye` API/MCP 프로세스를 중지한 뒤 의존 워크플로우를 호출한다.
- **복구:** `cd eye && bun run mcp` 또는 프로젝트의 표준 `eye` 재기동 명령으로 프로세스를 다시 올린다.
- **검증:** 10분 내 `eye` 기반 분석 요청이 재시도 없이 성공하고 대체 응답 대신 정상 분석 본문이 반환되는지 확인한다.

## 시나리오 3: Neo4j 인스턴스 1개 다운 (7687 또는 7688)

- **예상 동작:** 영향받는 모듈만 부분 성능 저하를 겪고, 나머지 MCP 서버는 살아 있으며 읽기 캐시 또는 축소 응답으로 버틴다.
- **수동 재현:** `7687` 또는 `7688` 중 한 포트를 사용하는 Neo4j 인스턴스 하나만 중지해 단일 데이터 스토어 장애를 만든다.
- **복구:** 중지한 Neo4j 인스턴스를 재시작하고 해당 포트에서 Bolt 연결이 다시 수립되는지 확인한다.
- **검증:** 10분 내 실패하던 Cypher 질의가 성공으로 돌아오고 page cache hit ratio 및 쿼리 지연이 기준선 근처로 회복되는지 확인한다.

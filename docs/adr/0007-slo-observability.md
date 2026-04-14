# ADR 0007 — SLO / SLI Observability

- **Status:** Proposed
- **Date:** 2026-04-14
- **Deciders:** Comad World maintainer (@kinkos1234)
- **Related:** docs/slo.md, docs/chaos-drill.md, brain/docs/query-plan.md

## Context

27-각도 석학 리뷰(Dean·Vogels·Jepsen 축, 2026-04-14)에서 "배포는 쉽지만 장애 시 눈이 없다"는 체계 갭이 드러났다. upgrade/rollback/lock DX는 8점이지만, 운영 관측 지표는 없었다. latency 13.8s가 목표인지 현상인지 구분 불가, MCP 4서버 uptime 집계 부재, Neo4j 2 인스턴스 중 1개 다운 시 graceful degrade 경로가 문서화되지 않음.

## Decision

세 개의 SLI와 한 개의 카오스 드릴 플레이북을 1급 문서로 고정한다.

1. **SLI 1 — brain query p95 latency** (목표 ≤ 15s). 계측: `comad_brain_perf` MCP tool.
2. **SLI 2 — crawl success rate** (목표 ≥ 95%/24h). 계측: ear 크롤 로그.
3. **SLI 3 — MCP server uptime** (목표 ≥ 99%/month). 계측: `comad status` ping.
4. **Chaos drill** — brain/eye/Neo4j 단일 장애 시나리오 3종, 예상 동작·재현·복구·검증 각 4줄.

`comad status`는 `print_sli_summary`로 세 SLI를 출력한다 (현재 stub, 후속 PR에서 실측 배선).

## Consequences

**+** 장애 시 기대값이 명문화돼 회귀 감지가 가능해진다.
**+** 새 기여자가 "이 시스템이 정상인지"를 단일 명령으로 확인한다.
**−** 초기 단계에서는 TODO stub이 출력된다 — 오히려 정직성은 유지되나, 사용자 혼란 가능성. stub 문구에 "TODO: wire ..." 명시로 완화.
**−** SLI 목표 위반 시 알람 채널은 아직 없음 — 다음 ADR 주제.

## Follow-ups

- brain/docs/query-plan.md의 PROFILE 결과를 근거로 p95 목표 재조정.
- `comad_brain_perf`를 `comad status`에 실제 배선.
- Neo4j 7687/7688 분리 이후 복구 RTO 측정.

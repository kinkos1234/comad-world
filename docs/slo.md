# Service Level Objectives

- **Status:** Proposed observability pack baseline
- **Date:** 2026-04-14
- **Owner:** Comad World maintainer (@kinkos1234)
- **Related:** `scripts/comad`, `docs/MCP_TOOLS.md`, `docs/system-intro.md`

## SLI 1 — brain query p95 latency

- **목표:** 15초 이하
- **현재:** 13.8초
- **측정:** `comad_brain_perf` MCP tool
- **주기:** 일단위
- **판정 기준:** 일일 p95가 15초를 초과하면 위반으로 간주한다.

## SLI 2 — crawl success rate

- **목표:** 최근 24시간 윈도우 기준 95% 이상
- **현재:** 기준선 수집 전
- **측정:** `ear` 크롤 성공 로그 수 / 전체 크롤 시도 로그 수
- **주기:** 24시간 롤링 윈도우
- **판정 기준:** 성공률이 95% 미만이면 위반으로 간주한다.

## SLI 3 — MCP server uptime

- **목표:** 월간 99% 이상
- **현재:** 기준선 수집 전
- **측정:** `comad status` ping 로그
- **주기:** 월단위
- **판정 기준:** 월간 가용 시간이 99% 미만이면 위반으로 간주한다.

## 알람·대응

### SLI 1 위반 대응

- 최근 24시간의 `comad_brain_perf` 결과에서 느린 질의 상위 5건과 Neo4j `PROFILE` 결과를 먼저 확인한다.
- 컨텍스트 캡, 인덱스 사용 여부, Neo4j page cache hit ratio를 점검하고 가장 큰 병목 1개만 우선 완화한다.
- 30분 내 p95가 복구되지 않으면 `brain/docs/query-plan.md` 절차로 증적을 남기고 성능 회귀 이슈를 연다.

### SLI 2 위반 대응

- `ear` 크롤 로그에서 실패 소스, HTTP 상태 코드, 타임아웃 비율을 먼저 묶어서 본다.
- 단일 소스 장애면 해당 소스를 격리하고, 공통 장애면 네트워크·인증·파서 변경 여부를 확인한다.
- 1시간 내 95% 이상으로 회복되지 않으면 수집 주기를 낮추고 수동 백필 범위를 결정한다.

### SLI 3 위반 대응

- `comad status` ping 로그에서 어떤 MCP 서버가 얼마나 자주 끊기는지 먼저 식별한다.
- 개별 프로세스 장애면 재기동하고, 반복 장애면 포트 충돌·의존 서비스·메모리 압박 순서로 원인을 좁힌다.
- 월간 예산을 계속 침식하면 `docs/chaos-drill.md` 드릴을 다시 수행해 복구 시간을 재측정한다.

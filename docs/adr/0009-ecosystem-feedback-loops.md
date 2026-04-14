# ADR 0009 — Ecosystem Feedback Loops (Reverse Edges)

- **Status:** Proposed
- **Date:** 2026-04-14
- **Deciders:** Comad World maintainer (@kinkos1234)
- **Related:** docs/feedback-loops.md, brain/scripts/graph-archaeology.ts

## Context

석학 리뷰에서 E.O. Wilson 축(6.5/10)이 가장 구조적인 지적이었다. 현재 파이프라인 `ear → brain → eye`는 **food chain이지 ecosystem이 아니다**. 종(모듈) 다양성은 있으나 상호공생(mutualism) 엣지가 없다. 같은 문제를 Wolfram 축은 "emergent behavior 설명 불가"로 표현했다 — 왜 특정 노드가 hub가 됐는지 추적할 도구 부재.

## Decision

두 개의 생태계 보강을 도입한다.

1. **Reverse Feedback Edges** (docs/feedback-loops.md)
   - `eye → ear` — 예측 정확도 높은 lens가 자주 참조하는 소스를 크롤 우선순위로 역주입.
   - `brain → ear` — graph hub 근방 토픽을 신규 RSS feed 후보로 추천.
   - `sleep → brain` — 세션 패턴이 graph 쿼리 캐시를 warming.
   - `photo → voice` — 이미지 처리 완료 이벤트가 voice workflow 트리거.

2. **Graph Archaeology** (brain/scripts/graph-archaeology.ts)
   - `whyHub(nodeId)` — 해당 노드가 hub가 된 이유 (degree 시계열, 첫 유입 엣지, peak week).
   - `timeline(nodeId, windowDays)` — 엣지 추가 이력의 주단위 bucket.

## Consequences

**+** 단방향 사슬이 양방향 생태계로 전환 — 약한 종(예: eye의 낮은 가중치 lens)도 ear 입력에 영향을 줌.
**+** emergent behavior가 사후 설명 가능해진다 (post-hoc archaeology).
**−** 순환 피드백은 **bias amplification** 위험을 갖는다 (edge case: 잘못된 lens가 잘못된 소스를 더 부른다). 완화책: ADR 0008의 source-diversity 지표가 상한 역할.
**−** 현재 reverse edges는 문서 레벨 설계 — 실제 배선은 모듈별 후속 PR.

## Follow-ups

- eye → ear: eye가 기록하는 `referenced_sources`를 ear의 `sources.yaml` 우선순위 가중치로 주입하는 스크립트.
- `graph-archaeology.ts`에 CLI `bun scripts/graph-archaeology.ts why <id>` 실사용 예제 추가.
- 순환 피드백 경고 로그 — 같은 소스가 연속 3주 가중치 상승 시 경고.

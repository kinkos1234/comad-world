# ADR 0010 — Narrative & Positioning (Hero, Story, Moat)

- **Status:** Proposed
- **Date:** 2026-04-14
- **Deciders:** Comad World maintainer (@kinkos1234)
- **Related:** README.md (hero), STORY.md, docs/moat.md

## Context

석학 리뷰의 메타 인사이트: "엔지니어링 9점인데 이야기 6점." Show HN 런치 이후 11 stars에서 정체된 병목은 코드가 아니라 **README 첫 3문장과 서사 부재**였다 (Harari 6, Moore 6.5, Thiel 6, McLuhan 7.5). 기능 나열은 독자를 사용자로 바꾸지 못한다.

## Decision

세 개의 서사 자산을 1급 문서로 고정한다.

1. **Hero (README 상단 3문장)** — 기능 나열 금지. "arXiv를 매일 읽는 ML 리서처" 페르소나의 Before→After 변환 서사. "reading stops evaporating — it compounds into a system that thinks alongside you." 가 축.

2. **STORY.md (Origin)** — 왜 만들었나, 왜 6 모듈인가, 실패담 2개 (Neo4j 단일 인스턴스 붕괴 / 17K 줄 청소), 지금 배운 것.

3. **docs/moat.md (Competitive Moat)** — 3축 **곱셈** moat: self-evolving loop × Claude Max $0/day × local-first. 모방 가능 부분(스키마, MCP 툴)은 정직하게 분리.

## Consequences

**+** 방문자가 "이게 나한테 왜 필요한가"를 3문장 안에 판정 가능.
**+** 경쟁 포지셔닝이 "또 하나의 KG 툴킷"이 아니라 "궤적 자체가 해자인 시스템"으로 재프레이밍.
**−** 페르소나 narrowing(ML 리서처 중심)은 다른 사용자(finance/biotech preset 사용자)에게 soft-exclusion. 완화: preset 페이지에서 다시 pluralize.
**−** Moat 주장은 **검증 가능한 지표**가 없으면 마케팅 카피에 그친다 — ADR 0007 SLI와 ADR 0008 epistemic 지표가 moat를 뒷받침하는 증거로 작동해야 함.

## Follow-ups

- 페르소나 2차 튜토리얼: finance / biotech / web-dev preset 각각의 "하루" 에세이.
- Show HN 재런치 카피를 이 hero 기반으로 재작성.
- 사용자가 체감할 수 있는 `comad hello` 5분 데모 (Norman 갭, 별도 ADR 후보).

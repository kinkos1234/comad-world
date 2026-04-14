# ADR 0008 — Epistemic Hygiene (Falsification, Source Diversity, Model Cards, Causal Edges)

- **Status:** Proposed
- **Date:** 2026-04-14
- **Deciders:** Comad World maintainer (@kinkos1234)
- **Related:** eye/docs/falsification.md, ear/docs/source-diversity.md, brain/docs/model-cards/, brain/docs/causal-edges.md

## Context

석학 리뷰에서 "자가진화 루프가 자기확증(confirmation)으로 수렴할 위험" 이 반복 지적됐다 (Popper 6.5, O'Neil 6, Gebru 6.5, Pearl 6.5, Korzybski 7). 루프 자체는 강점이지만 **반증 메커니즘, 소스 편향 지표, 모델 한계 기록, 엣지 인과성 구분, 시간적 decay** 다섯 축이 모두 코드/문서로 존재하지 않았다. 측정되지 않는 피드백 루프는 상상일 뿐이다.

## Decision

다섯 개의 인식론적 위생 규약을 문서 레벨에서 고정한다.

1. **Falsification (Popper)** — eye lens 예측이 틀릴 때 `w_new = w_old * 0.9^n` 감쇠. 반증 불가능한 예측은 로그 제외.
2. **Source Diversity (O'Neil)** — 3개 경고 지표 (BigTechRatio, RegionDiversity, PerspectiveSpread). 주간 digest 전 심각 레벨 1개라도 있으면 수동 보정.
3. **Model Cards (Gebru)** — synth-classifier, eye-lens 각 1장. 적용 범위·한계·학습 데이터·윤리 고려.
4. **Causal Edges (Pearl)** — 엣지 타입 분류 `assoc | corr | causal`, 인과 승격은 개입 증거 3건 이상.
5. **Temporal Decay (Korzybski)** — 노드 나이에 따른 weight 감쇠 + 시각화 fade-out.

## Consequences

**+** 자가진화 루프가 "진화" 방향을 측정 가능한 지표로 제약한다.
**+** 모델 한계가 명문화되어 과신 방지.
**−** 지표 계산 로직은 아직 문서 수준 — 실제 배선은 후속 PR.
**−** causal 엣지 승격 기준 "개입 증거 3건"은 실험적 — 실데이터 확보 후 조정 필요.

## Follow-ups

- falsification log 스키마를 eye 실제 prediction 파이프라인에 배선.
- source-diversity 3 지표의 실시간 계산 잡 (weekly CRON 후보).
- causal 엣지 타입 필드를 brain/schema/ JSON Schema에 정식 추가.

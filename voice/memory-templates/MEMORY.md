# [프로젝트명] Memory

## Project Overview

- 프로젝트 설명: [한 줄 요약 — 예: "로컬 LLM 기반 knowledge graph RAG 시스템"]
- 주요 기술: [예: Python, Next.js, ollama, GraphRAG 등]
- 브랜치: [현재 작업 브랜치 — 예: main, autoresearch/mar21]
- 시작일: [YYYY-MM-DD]

## Experiment History

핵심 실험 결과만 요약. 상세는 아래 링크 참조.
-> 상세 기록: [experiments.md](experiments.md)

<!-- 예시:
- Exp 0-5: 기본 추출 파이프라인 구축 (chunking, entity extraction)
- Exp 6-10: 프롬프트 최적화 → 엔티티 정확도 45% → 72%
- Exp 11-15: 관계 추출 개선 → 관계당 평균 깊이 1.2 → 2.8
-->

## Current State

- 최근 작업: [마지막으로 한 것 — 예: "seed 데이터셋 8개 도메인 검증 완료"]
- 다음 할 일: [다음 예정 작업 — 예: "리포트 서사 품질 개선 실험"]
- 현재 성능: [측정 가능한 메트릭 — 예: "엔티티 정확도 72%, 관계 깊이 2.8"]

## Architecture Decisions

주요 설계 결정 요약. 상세는 아래 링크 참조.
-> 상세 기록: [architecture.md](architecture.md)

<!-- 예시:
- 로컬 LLM (llama3.1:8b) 사용 결정 → 비용 0, 프라이버시 보장
- 2-phase extraction (엔티티 → 관계) 선택 → 단일 패스 대비 정확도 +30%
-->

## Known Issues & Improvement Areas

- [ ] [알려진 문제 — 예: "긴 문서(5000자+)에서 엔티티 누락 발생"]
- [ ] [개선 영역 — 예: "리포트 서사가 단조로움, 시뮬레이션 결과 해석 부족"]
-> "검토해봐" 명령으로 자동 진단 가능

## User Preferences

- [예: 비전공자 — 전문 용어 최소화, 카드형 선택지 선호]
- [예: 로컬 모델 사용 — 테스트 시간 길음 → background 실행 필수]
- [예: Claude Max 200 + ChatGPT Plus + Codex CLI 사용]

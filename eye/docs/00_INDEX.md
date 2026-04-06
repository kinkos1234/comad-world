# ComadEye 사전 문서 인덱스

> 온톨로지 네이티브 예측 시뮬레이션 엔진 — 구현을 위한 설계 문서 모음

## 문서 목록

| # | 문서 | 설명 | 의존 |
|---|------|------|------|
| 01 | [ARCHITECTURE](./01_ARCHITECTURE.md) | 4-Layer 시스템 아키텍처 전체 설계 | — |
| 02 | [ONTOLOGY_SCHEMA](./02_ONTOLOGY_SCHEMA.md) | 온톨로지 4요소(Object/Link/Action/Property) 스키마 명세 | 01 |
| 03 | [DATA_MODEL](./03_DATA_MODEL.md) | Neo4j 노드/엣지 스키마, JSONL 로그 포맷, 파일 구조 | 02 |
| 04 | [PIPELINE](./04_PIPELINE.md) | Layer 0~1 입력·온톨로지 구축 파이프라인 상세 | 01, 02, 03 |
| 05 | [META_EDGE](./05_META_EDGE.md) | 메타엣지 규칙 정의 문법, 평가 엔진, 예시 규칙셋 | 02, 03 |
| 06 | [SIMULATION_ENGINE](./06_SIMULATION_ENGINE.md) | Layer 2 상태 전이 엔진 설계 — 라운드, 전파, 커뮤니티 재편 | 02, 03, 05 |
| 07 | [ANALYSIS_SPACES](./07_ANALYSIS_SPACES.md) | Layer 3 — 6개 분석공간(계층/시간/재귀/구조/인과/다중) 명세 | 06 |
| 08 | [REPORT_GENERATION](./08_REPORT_GENERATION.md) | Layer 4 — 구조적 분석 결과를 시뮬레이션리포트.md로 변환 | 07 |
| 09 | [QA_INTERFACE](./09_QA_INTERFACE.md) | 대화형 Q&A — GraphRAG 기반 후속 질문 처리 | 03, 07 |
| 10 | [TECH_STACK](./10_TECH_STACK.md) | 기술 스택, 의존성, Docker 구성, 환경 설정 | — |
| 11 | [PROMPTS](./11_PROMPTS.md) | LLM 호출 지점별 프롬프트 템플릿 전문 | 04, 08 |
| 12 | [ONTOLOGY_NATIVE_STRUCTURE](./12_ONTOLOGY_NATIVE_STRUCTURE.md) | **8-Layer 온톨로지 네이티브 구조** — 시스템 자체의 온톨로지적 관리 프레임 | 01, 02 |

## 읽기 순서

**설계 철학 (먼저 읽기)**: 12 → 01 → 02

**설계 이해**: 03 → 05 → 06 → 07 → 08 → 09

**구현 착수**: 10 → 04 → 11 → (코드 작성)

## 설계 원칙

1. **온톨로지 네이티브**: 시스템이 온톨로지를 "사용"하는 것이 아니라, 시스템 자체가 온톨로지로 구성된다 (8-Layer 구조)
2. **확률적 지능 → 위상학적 지능**: LLM 의존 최소화, 온톨로지 구조가 지능의 본체
3. **LLM 호출 예산 4~5회**: 엔티티 추출(1) + 커뮤니티 요약(1) + 리포트 생성(2~3)
4. **시뮬레이션은 LLM 0회**: 메타엣지 규칙과 그래프 연산만으로 상태 전이
5. **6개 분석공간**: 동일 시뮬레이션 결과를 6개 위상학적 렌즈로 동시 분석
6. **완전 로컬**: Neo4j Community + Ollama(Qwen 3.5) + sentence-transformers
7. **GraphRAG + ReBAC**: 바인딩 프레임으로서 데이터 흐름과 접근 경로를 관계 그래프로 정의
8. **Impact Analysis + Active Metadata**: 변경 영향 시각화 + 메타데이터 자동 전파

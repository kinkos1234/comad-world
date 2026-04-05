# GeekNews 한국어 포스트

**제목:** Comad World — YAML 하나로 도메인이 바뀌는 6개 AI 에이전트 지식 시스템

**URL:** https://github.com/kinkos1234/comad-world

**소개글 (댓글):**

기술 기사를 읽고 까먹고, 한 달 뒤에 같은 기사를 또 발견하는 경험이 반복되어서 만들었습니다.

RSS 피드, arXiv 논문, GitHub 레포를 자동으로 크롤링하고, 엔티티를 추출해서 Neo4j 지식 그래프를 만들고, 자연어로 질의할 수 있는 시스템입니다.

핵심은 **설정 파일 하나(comad.config.yaml)로 도메인이 완전히 바뀐다**는 점입니다. AI/ML 프리셋에서 금융 프리셋으로 바꾸면, 크롤링 대상, 키워드, 분류 기준이 전부 바뀝니다.

6개 에이전트:
- ear: RSS/HN 자동 수집 + 3단계 관련성 분류
- brain: Neo4j 지식 그래프 + GraphRAG (15개 MCP 도구)
- eye: 10개 분석 렌즈로 시뮬레이션 보고서 생성
- photo: Photoshop MCP 사진 보정
- sleep: 메모리 정리
- voice: 워크플로우 자동화

스택: Claude Code, Bun/TypeScript, Python/FastAPI, Next.js, Neo4j
운영 비용: $0.60/day, 테스트 1,422개, MIT 라이선스

README에 데모 GIF 있습니다.

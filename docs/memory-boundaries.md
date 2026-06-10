# 기억 체계 4종 — 경계 명문화 (R6 Phase 2, 2026-06-11)

comad 에는 "기억"이 4계통 병존한다. 외부 벤치마크(2026-06-11)의 처방대로
**통합 대신 경계를 명문화**한다 — 단일 만능 메모리는 안티패턴(실패 패턴)이고,
instruction / knowledge / episodic 은 분리해서 풀어야 한다.

| 계통 | 역할 (한 줄) | 입력 경로 | 소비처 | 다른 계통과의 경계 |
|---|---|---|---|---|
| **T6 feedback memory** (`~/.claude/projects/*/memory/feedback_*.md`) | **instruction** — "다음 세션에서 같은 실수를 반복하지 않게 하는 규칙" | Stop hook 커밋 캡처 → comad-learn(주간) 승격 | 세션 자동 recall, HARD 훅 승격 원천 | 프로젝트 사실·외부 지식 저장 금지. 규칙이 아닌 것은 여기 안 옴 |
| **brain** (Neo4j 지식그래프) | **knowledge(외부)** — 기술 기사·계보·트렌드의 출처 인덱스 | ear/crawl 인제스트 (GeekNews·arXiv·blogs) | comad-recall(Tier1)·foresight | 개인 교훈·세션 사실 저장 금지. claim 은 미검증 — 출처 인덱스로만 신뢰 |
| **kb_facts** (loopy-era SQLite) | **knowledge(내부)** — 메모리 파일에서 추출한 사실의 검색 캐시 | kb-sleep(2h)이 memory/*.md 에서 추출 | comad_kb_* MCP 5종 (Claude+Codex 공용) | **파생 캐시다 — 진실원은 항상 markdown**. 직접 쓰기 금지, 재생성 가능해야 함 |
| **세션 기록** (`.comad/sessions/`, reports) | **episodic** — "무슨 일이 있었나" | T5/handoff, 보고서 작성 | 다음 세션 이어가기, registry 인덱스 | 규칙·지식으로 승격할 것은 각자의 계통으로 보내고 여기는 사건 기록만 |

## 중복 입력 차단 규칙

1. 같은 정보를 두 계통에 쓰지 않는다. 승격이 필요하면 **이동**(원계통에 링크만 남김).
2. kb_facts 는 markdown 의 파생물 — kb 에만 있는 사실이 발견되면 그것은 버그다.
3. brain 에 개인 교훈을 넣지 않는다 (외부 지식 전용). 반대로 feedback memory 에 기사 요약을 넣지 않는다.
4. 4계통 각각의 기여 증거는 분기별 entropy-audit 이 심사한다 (memory-usage.tsv ·
   hook-fires.tsv · kb MCP 호출 · recall 사용). 90일 무기여 계통은 축소/통합 후보.

## 이 문서의 지위

- 분기 entropy-audit 의 심사 기준표.
- 새 "기억" 기능 제안은 이 4계통 중 어디에 속하는지 먼저 답해야 한다.
  4계통 어디에도 안 속하면 — 새 계통이 아니라, 정말 필요한지부터 의심하라 (R6 빼기 원칙).

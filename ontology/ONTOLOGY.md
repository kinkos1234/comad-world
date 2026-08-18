# comad 온톨로지 v0.1 — 운영 도메인 객체 레지스트리

Palantir Foundry 온톨로지 3층(Semantic/Kinetic/Agent) 패턴의 comad 이식, Phase 1.
FastCampus "온톨로지 기반 AI 에이전트 구축" 커리큘럼 P2 상당 (2026-08-18 시작).

## 원칙
1. **파일이 진실원, DB 는 캐시** — 기존 저장소(md/json/plist)는 그대로. 레지스트리는
   전량 재빌드 가능한 인덱스 층이다 (comad-memory 와 동일 원칙).
2. **객체는 `type:slug` id** — 저장소가 달라도 하나의 주소 체계.
3. **링크는 증거를 남긴다** — 모든 edge 에 추출 근거(어느 파일의 어떤 문맥) 첨부.
4. brain(Neo4j, ear 기사·claim 그래프)은 별도 세계 — Phase 3 에서 링크 예정.

## 객체 타입 (v0.1, 7종)
| type | 소스 (SoT) | 비고 |
|---|---|---|
| `memory` | `~/.claude/projects/-Users-jhkim--claude/memory/*.md` | mtype=user/feedback/project/reference |
| `skill` | `~/.claude/skills/*/SKILL.md` | frontmatter |
| `agent` | `~/.claude/agents/*.md` | souls/ 제외 |
| `cron` | `~/Library/LaunchAgents/com.comad.*.plist` | 스케줄·실행 스크립트 파싱 |
| `hook` | `~/.claude/hooks/<event>/*` | stem 단위 (sh+py 래퍼 묶음) |
| `rule` | `~/.claude/rules/*.md` | 승격된 HARD 규칙 |
| `decision` | `~/.claude/.comad/decisions/*.json` + `_resolved/` | HITL 결정큐 |

## 링크 타입 (v0.1, 3종)
- `references` — 메모리 본문의 `[[wikilink]]` (하이픈/언더스코어 정규화)
- `mentions` — 본문에 다른 객체 slug 가 단어 경계로 등장 (구분자 포함 slug 만 —
  `learn` 같은 일반단어 slug 는 오탐이라 제외, feedback_substring_match 규칙 적용)
- `runs` — cron → 실행 스크립트가 속한 skill/hook

## 저장소
- 코드: `comad-world/ontology/bin/onto.py` (python3 stdlib only)
- DB: `~/.claude/.comad/ontology/registry.db` (SQLite + FTS5, 미커밋 상태 파일)

## Kinetic 층 — 액션 카탈로그 (Phase 2, 2026-08-18)
`ontology/actions.json` 이 단일 진실원. 액션 = 8번째 객체 타입(`action:`)으로 레지스트리에 적재된다.

- **effect**: `read`(즉시 실행) / `write` / `destructive`
- **approval**: `none` / `confirm`(`--yes` 필요) / `hitl`(결정큐에 승인요청 생성, 직접 실행 안 함) / `gate`(전용 훅이 강제 — 카탈로그는 문서화, 디스패처는 실행 거부)
- **링크**: `executes`(액션→실행 스크립트가 속한 skill/hook) · `gated_by`(액션→강제 훅)
- **감사로그**: 모든 디스패치 시도(차단 포함)가 `~/.claude/.comad/ontology/audit.jsonl` 에 append
- 에이전트 계약: 상태 변경은 카탈로그 액션 경유가 원칙 — 임의 스크립트 직접 호출은 카탈로그 등재 후

## CLI
```
onto.py build              # 전 소스 스캔 → 레지스트리 재빌드
onto.py stats              # 타입별 객체/링크 수
onto.py search <q>         # FTS 전문 검색 [--type T]
onto.py show <slug>        # 객체 상세 + in/out 링크
onto.py links <slug>       # 링크 그래프 BFS [--depth N]
onto.py actions [domain]   # 액션 카탈로그 목록
onto.py act <id> [args] [--yes]  # 액션 디스패치 (effect/approval 강제 + 감사로그)
```

## 다음 페이즈
- Phase 3 (Agent): 크로스도메인 질의 에이전트 + brain(Neo4j)·OFFCUT(Notion) 소스 연결

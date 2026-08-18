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
| `script` | cron 커맨드가 가리키는 skill/hook 밖 파일 | .sh/.py/.mjs/.js/.ts — 크론 커버리지용 |
| `client` / `deliverable` / `product` | `~/.claude/.comad/ontology/deliverables.json` | **납품 축 (Phase 4)** — 프라이빗 SoT, 레포 미커밋. 링크: `delivered_to`·`bundles`(계보)·`governed_by`·`instance_of`(기능 원형) |

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

## Agent 층 — 질의 에이전트 + 소스 연방 (Phase 3, 2026-08-18)
- **OFFCUT(Notion) 소스 연결**: `scan_shop()` 이 브랜드·거래처·상품·PO 4개 DB 를
  `shop-*` 객체로 적재하고 Notion relation 을 `relates` 링크로 추출한다.
  실패 시 경고 후 스킵 (오프라인 빌드는 `--no-shop`). 행 단위 집계(매출 합계 등)는
  레지스트리가 아니라 카탈로그 read 액션으로 — 레지스트리는 관계 스냅샷만 든다.
- **질의 에이전트 = `/onto` 스킬** (`~/.claude/skills/onto/`, 벤더 사본 `ontology/skill/`):
  LLM 이 에이전트이고 스킬이 그 계약이다 — 신선도 확인 → search/show/links 플로우 →
  연방 라우팅(운영=레지스트리 · 기사/claim=brain MCP · 행 상세=액션) → 변경은 카탈로그 경유.
- **brain(Neo4j) 은 레지스트리에 흡수하지 않는다** — 기사·claim 그래프는 다른 세계.
  에이전트 레벨에서 `mcp__knowledge__comad_brain_*` 로 연방 질의한다.

## 납품 축 (Phase 4, 2026-08-18)
프리랜서 납품 유닛을 1급 객체로: 고객 6·납품물 12 시딩(프로젝트 메모리 기반, 실명 미기록 고객은
역할 라벨만 — 추측 금지). 핵심 질의 3종 검증됨 — "고객 X 에게 나간 것 전부"(delivered_to 역링크) ·
"내부 컴포넌트 수정 시 영향받는 납품물"(bundles 역질의, select-shop-kit↔skill:sales 실사례) ·
"후속 대기 납품물"(state=awaiting-followup). 신규 납품 시 deliverables.json 에 항목 추가 →
재빌드. memory 대상은 -/_ 정규화로 리졸브된다.
**같은 기능을 여러 의뢰인에게 납품하는 패턴**(사용자 교정 2026-08-18): deliverable 에
`product: <원형-slug>` 를 달면 `product:` 객체와 `instance_of` 링크가 자동 생성된다 —
"이 기능 쓰는 의뢰인 전부" = `show product:<slug>`. 실례: slot-machine 원형 ←
sig-slot-machine(슬롯 의뢰인) · sig-hunter(헌터 의뢰인, 데스 단일테마 사본).

## 운영
- 재빌드: 수동 `onto.py build` / `act sys.ontology.build` + **nightly-audit 이 매일 자동 재빌드** (2026-08-18 편입)
- 액션 `forbid_args`: 선언된 금지 인자(예: cafe24.pull 의 `--apply`)는 디스패처가 차단하고 감사에 남긴다
- 감사로그: `~/.claude/.comad/ontology/audit.jsonl`

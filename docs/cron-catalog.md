# Cron Catalog

코마드월드의 모든 스케줄 작업을 한 곳에서 본다. 현재 macOS `launchd`에 **`com.comad.*` 24개**가 등록되어 있다 (brain 파이프라인 12 + 자가발전 루프 12). 마지막 전수 점검: 2026-06-11.

> **크로스플랫폼 진입점**: `brain/scripts/schedule-install.sh` — macOS는 `launchd`, Linux/WSL은 `cron`, Windows는 Task Scheduler로 라우팅. 자세한 설치·보안 주의사항은 [`brain/scripts/launchd/README.md`](../brain/scripts/launchd/README.md) 참고.
> ⚠️ **plist 복구는 반드시 `brain/scripts/launchd/install.sh` 재실행으로** — 2026-04-30 마이그레이션 때 수기 plist 가 JSON 조각으로 손상돼 5종이 6주간 침묵 언로드된 사고가 있었다 (2026-06-11 복구).

## 목차

- [A. 일일 수집 파이프라인](#a-일일-수집-파이프라인-07001000-매일) — 매일 07:00–10:00
- [B. 주간 분석·자동개선 배치](#b-주간-분석자동개선-배치-11001300-월요일) — 매주 월 11:00–13:00
- [C. 실시간 폴링](#c-실시간-폴링) — ear-poll·ci-healer·pr-review
- [D. 자가발전 루프 (loopy-era 계열)](#d-자가발전-루프-loopy-era-계열) — 2026-06-11 R6 기준
- [의존성 그래프](#의존성-그래프)
- [로그 위치](#로그-위치)
- [주의사항](#주의사항)

> 설치·`launchctl` 운영 명령어는 이 문서에 중복하지 않습니다 — 모두 [`brain/scripts/launchd/README.md`](../brain/scripts/launchd/README.md) 참고.

---

## A. 일일 수집 파이프라인 (07:00–10:00 매일)

외부 신호 인제스트 + 디제스트. ear → brain 방향으로 흐른다.

| 시각 | 라벨 | 실행 대상 | 역할 |
|---|---|---|---|
| 07:00 | `com.comad.ear-ingest` | `bun run brain/packages/search/src/ear-ingest.ts --since 1` | 전날 24시간치 ear 아카이브를 Brain으로 인제스트 |
| 08:00 | `com.comad.ear-digest` | `node ear/generate-digest.js` | 인제스트 결과 기반 일일 digest 생성 |
| 09:00 | `com.comad.crawl-arxiv` | `brain/scripts/crawl-arxiv.sh` | arXiv 논문 크롤링 → `/tmp/ko-arxiv-{date}.json` |
| 09:30 | `com.comad.ingest-geeknews` | `brain/scripts/ingest-geeknews.sh` (`bun run packages/ingester/src/geeknews-importer.ts --incremental`) | GeekNews 증분 인제스트 |
| 10:00 | `com.comad.crawl-blogs` | `brain/scripts/crawl-blogs.sh` | HN + RSS 기술 블로그 → `/tmp/ko-blogs-{date}.json` |

**런타임**: bun · node. 러너에 따라 Node 24.13.0 (ear-digest) 또는 Bun (나머지).
**공용 로그**: `brain/crawl.log` (ear-digest만 `ear/digest.log`).

## B. 주간 분석·자동개선 배치 (11:00–13:00 월요일)

데이터 수집 + 성능 측정 + 자가 진화. `Weekday=1` (월요일) 고정.

| 시각 | 라벨 | 실행 대상 | 역할 |
|---|---|---|---|
| 11:00 | `com.comad.crawl-github` | `brain/scripts/crawl-github.sh` | GitHub trending → `/tmp/ko-github-{date}.json` (GITHUB_TOKEN via `gh auth`) |
| 11:30 | `com.comad.monitor-upstream` | `brain/scripts/monitor-upstream.sh` | 채택한 upstream 레포의 release/tag 추적, ReferenceCard 노드로 Brain에 적재 |
| 12:00 | `com.comad.search-weekly` | `brain/scripts/search-weekly.sh` | 주간 레퍼런스 검색. 결과 → `brain/search-weekly.log` |
| 12:30 | `com.comad.evolution-loop` | `brain/scripts/evolution-loop.sh` | 자기 진화 루프. Trigger: Brain +10 nodes / 벤치 -5%+ / upstream major update / fallback weekly |
| 13:00 | `com.comad.run-benchmark` | `brain/scripts/run-benchmark.sh` | GraphRAG 벤치 20문항 → `data/benchmark-{date}.json`, 회귀 감지 시 알림 |

**공용 로그**: 10개 모두 plist-level stdout은 `brain/crawl.log` 또는 `ear/digest.log`로 감. `search-weekly`는 여기에 더해 스크립트 내부에서 `brain/search-weekly.log`에 WARN을 append.

## C. 실시간 폴링

| 주기 | 라벨 | 상태 (2026-06-11 실측) |
|---|---|---|
| 매 15분 (`StartInterval 900s`) | `com.comad.ear-poll` | **활성** (install.sh 가 등록). Discord Mode B 폴링(REST 기반, 0 IDENTIFY quota). 실행: `/bin/bash ear/poll-ear.sh` |
| 매 15분 (`StartInterval 900s`) | `com.comad.ci-healer` | **활성, dry_run=false (실모드)**. GH Actions 실패 감지 → headless claude 수정 → 자동 PR (머지는 사람). config: `~/.claude/skills/comad-ci-healer/config.json` |
| 매 20분 (`StartInterval 1200s`) | `com.comad.pr-review` | **활성, dry_run=false (실모드)**. 신규 PR headSha dedup → 4축 채점 → 인라인+요약 코멘트 |

## D. 자가발전 루프 (loopy-era 계열) — 2026-06-11 R6 기준

수확 → 분석 → 승인요청 → 도달 → 적용 → 계측 → 감사의 닫힌 루프. 전부 비정각 분 오프셋(`feedback_cron_offset_safety` 준수).

| 주기 | 라벨 | 역할 |
|---|---|---|
| 매 30분 | `com.comad.loopy-era` | supervisor **6-phase** tick (R6에서 15→6 슬림화): init → qa-scenario → trigger → verify → verify-final → closeout(results.tsv + outcome 지표 `fix_ratio`·`ci_first_pass`) |
| 매 2시간 | `com.comad.kb-sleep` | memory/*.md → kb_facts 추출·임베딩·rule-only consolidate → memory-log 퍼블리시 |
| 매일 03:15 | `com.comad.auto-dream` | dream_pending 시 comad-sleep 에이전트 headless 실행 (메모리 통합·은퇴 제안) |
| 매일 04:00 | `com.comad.nightly-audit` | 시스템 자가감사 → 사람 판단 필요 항목만 결정 큐 에스컬레이트. codex doctor·HARD 훅 ROI(hook-fires.tsv) 점검 포함 |
| 매주 일 09:17 | `com.comad.learn-weekly` | T6 pending 자동 분석(comad-learn). SOFT 승격 자동, HARD 는 결정 큐 승인 요청만. 교훈마다 재발 감지 검증물 동반 생성 |
| 매주 월 08:13 | `com.comad.decision-digest` | 결정 큐 적체 시 Discord 다이제스트 (LLM 불필요 — 봇 REST 직접 호출) |
| 매주 월 09:00 | `com.comad.foresight` | brain hot클러스터 → 10렌즈 전략 foresight (**dry_run=true** — Discord 미전송 상태) |
| 매 6시간 | `com.comad.evolve` | comad-evolve Phase 1 (trend harvest 만) |
| 매월 2일 10:23 | `com.comad.evolve-monthly` | comad-evolve Phase 2~5 (분석→게이트→A/B→적용). 적용은 A/B 통과분만, 시스템 변경은 결정 큐로 |
| 분기 11일 09:37 (3·6·9·12월) | `com.comad.entropy-audit` | 90일 기여 증거 감사 — 무참조 메모리·무발화 훅·실작동 0 크론을 결정 큐로. 1회차 2026-09-11 (콜드스타트 가드) |

**계측 파일** (감사의 증거 데이터): `~/.claude/.comad/{memory-usage,hook-fires,sdk-usage,tool-durations}.tsv` + `results.tsv`
**주의**: D 계열 신규 크론(learn-weekly·evolve-monthly·decision-digest·entropy-audit)은 cron-catchup 의 미발화 캐치업 카탈로그(`comad-crons.json`)에 미등재.

---

## 의존성 그래프

```
┌── ear-ingest (07:00) ───────────▶ ear-digest (08:00)
│                                            │
│                                            ▼
│  Brain 데이터베이스
│   ▲   ▲   ▲   ▲                            │
│   │   │   │   │                            │
│  arxiv  geeknews  blogs  github            │
│  09:00  09:30     10:00  11:00(월)         │
│                                            │
│  monitor-upstream (11:30 월) ──────────────┤
│                                            │
│  search-weekly (12:00 월) ─────┐           │
│                                ▼           │
│                        evolution-loop ◀────┤
│                           (12:30 월)       │
│                                │           │
│                                ▼           │
│                        run-benchmark ──────┘
│                           (13:00 월)
│                    (회귀 시 다음 주 evolution-loop trigger)
```

### 확인된 명시적 의존
- `evolution-loop.sh` 헤더 주석: "Cron: `30 12 * * 1` (weekly Monday 12:30, **after search-weekly**)"
- `run-benchmark.sh` 헤더 주석: "Cron: `0 13 * * 1` (Monday 13:00, **after evolution loop**)"
- `evolution-loop` trigger 조건 중 하나: "Benchmark score dropped 5%+" → 지난 주 benchmark 결과 의존

### 암시적 의존 (시간 순서로 추정)
- `ear-ingest` (07:00) → `ear-digest` (08:00): 1시간 gap
- 수집(A+B 상단 crawl-*) → 분석(B 하단 search·evolution·benchmark): 같은 월요일 오전에 직렬 진행

---

## `ear-poll` 운영 메모

2026-06-11 부터 활성 (install.sh 가 기본 등록). 비활성화가 필요하면 `launchctl bootout gui/$(id -u)/com.comad.ear-poll`.
일반 설치·제거·상태 조회는 [`brain/scripts/launchd/README.md`](../brain/scripts/launchd/README.md) 참고.

---

## 로그 위치

| 로그 파일 | 생산자 (크론 수) |
|---|---|
| `brain/crawl.log` | 9개 (ear-ingest, crawl-arxiv, ingest-geeknews, crawl-blogs, crawl-github, monitor-upstream, evolution-loop, run-benchmark, 그리고 stderr) |
| `ear/digest.log` | 1개 (ear-digest) |
| `brain/search-weekly.log` | 1개 (search-weekly, 스크립트 내부 appender) |
| `ear/launchd-poll-{out,err}.log` | 1개 (ear-poll) |
| `~/.comad/loopy-era/logs/*` | D 계열 (supervisor·kb-sleep·auto-dream·nightly-audit·learn-weekly·evolve-monthly·decision-digest·entropy-audit) |
| `~/.claude/.comad/{ci-healer,pr-review}/logs/` | ci-healer·pr-review |

**관찰**: `brain/crawl.log`는 9개 크론이 공용으로 쓰는 단일 파일 — 로그가 섞여 실패 진단 시 grep으로 라벨 필터링이 필요. 개선 여지.

---

## 주의사항

1. **월요일 집중**: 07:00–13:00에 10개 작업이 직렬로 발화. 대부분 경량이지만 `run-benchmark`는 GraphRAG 전체 쿼리라 무거울 수 있음. 실패 시 다음 주까지 재시도 없음.

2. **공용 로그 파일 경쟁**: `brain/crawl.log` 한 파일에 9개 크론이 append. 동시 쓰기는 launchd 일정상 거의 발생 안 하지만, 디스크 가득 차면 전체 파이프라인 침묵 실패 가능 → 주기적 logrotate 고려.

3. **GITHUB_TOKEN 의존**: `crawl-github`, `search-weekly`는 `gh auth token`으로 token 수취. `gh` 로그아웃 상태면 rate limit로 부분 실패 → 로그에 `[WARN] GITHUB_TOKEN not available` 출력.

4. **`ear-poll` 재활성화 시**: `RunAtLoad=true`라 `bootstrap` 직후 한 번 실행된다. `.env` 누락 상태로 bootstrap하면 첫 실행에서 fail 로그가 남음.

> Aqua 세션 필요·Keychain OAuth 같은 플랫폼 차원 제약은 [`launchd/README.md`](../brain/scripts/launchd/README.md#caveats) 참고.

---

*Last reviewed: 2026-04-19. 크론 수·시각이 변경되면 이 문서도 함께 업데이트.*

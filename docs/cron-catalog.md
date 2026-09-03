# Cron Catalog

코마드월드의 모든 스케줄 작업을 한 곳에서 본다. 현재 macOS `launchd`에 **`com.comad.*` plist 32개**가 있고 그중 **29개가 로드**되어 있다 (brain 파이프라인 12 + 자가발전 루프 12 + 기타 8 = 기존 31, 여기에 2026-09-03 신설 `transcript-archive` 1). 마지막 전수 점검: **2026-09-03** (headless 비용 감사 후속).

미로드 3개: `threads-watch` (사용자가 2026-09-02 중단 — 플랜 대비 과중), `shop-brief`·`shop-closeout` (plist 만 있고 `launchctl` 에 없음 — 의도인지 확인 필요).

> **크로스플랫폼 진입점**: `brain/scripts/schedule-install.sh` — macOS는 `launchd`, Linux/WSL은 `cron`, Windows는 Task Scheduler로 라우팅. 자세한 설치·보안 주의사항은 [`brain/scripts/launchd/README.md`](../brain/scripts/launchd/README.md) 참고.
> ⚠️ **plist 복구는 반드시 `brain/scripts/launchd/install.sh` 재실행으로** — 2026-04-30 마이그레이션 때 수기 plist 가 JSON 조각으로 손상돼 5종이 6주간 침묵 언로드된 사고가 있었다 (2026-06-11 복구). install.sh 가 관리하는 것은 A·B·C(ear-poll) 계열이고, D·E 계열 plist 는 각 스크립트 옆 문서가 관리한다.

## 목차

- [A. 일일 수집 파이프라인](#a-일일-수집-파이프라인-07001000-매일) — 매일 07:00–10:00
- [B. 주간 분석·자동개선 배치](#b-주간-분석자동개선-배치-11001300-월요일) — 매주 월 11:00–13:00
- [C. 실시간 폴링](#c-실시간-폴링) — ear-poll·ci-healer·pr-review
- [D. 자가발전 루프 (loopy-era 계열)](#d-자가발전-루프-loopy-era-계열) — 2026-09-03 기준
- [E. 기타 잡 (개인 운영·보관)](#e-기타-잡-개인-운영보관)
- [F. 헤드리스 LLM 모델 정책](#f-헤드리스-llm-모델-정책-2026-09-03)
- [의존성 그래프](#의존성-그래프)
- [로그 위치](#로그-위치)
- [주의사항](#주의사항)

> 설치·`launchctl` 운영 명령어는 이 문서에 중복하지 않습니다 — 모두 [`brain/scripts/launchd/README.md`](../brain/scripts/launchd/README.md) 참고.

---

## A. 일일 수집 파이프라인 (07:00–10:00 매일)

외부 신호 인제스트 + 디제스트. ear → brain 방향으로 흐른다.

| 시각 | 라벨 | 실행 대상 | 역할 |
|---|---|---|---|
| 07:00 | `com.comad.ear-ingest` | `bun run brain/packages/search/src/ear-ingest.ts --since 1` | 전날 24시간치 ear 아카이브를 Brain으로 인제스트 (LLM 없음) |
| 08:00 | `com.comad.ear-digest` | `node ear/generate-digest.js` | 인제스트 결과 기반 일일 digest 생성 (LLM 없음. Discord 전송·구독 없음 — 사람이 `ear/digests/*.html` 을 열지 않으면 산출물 없음) |
| 09:00 | `com.comad.crawl-arxiv` | `brain/scripts/crawl-arxiv.sh` | arXiv 논문 크롤링 → `/tmp/ko-arxiv-{date}.json`. 인제스트 추출은 `claude -p --model haiku` (기사 1건 = 1세션) |
| 09:30 | `com.comad.ingest-geeknews` | `brain/scripts/ingest-geeknews.sh` (`bun run packages/ingester/src/geeknews-importer.ts --incremental`) | GeekNews 증분 인제스트 (haiku 추출) |
| 10:00 | `com.comad.crawl-blogs` | `brain/scripts/crawl-blogs.sh` | HN + RSS 기술 블로그 → `/tmp/ko-blogs-{date}.json` (haiku 추출, 일 ~63건) |

**런타임**: bun · node. 러너에 따라 Node 24.13.0 (ear-digest) 또는 Bun (나머지).
**공용 로그**: `brain/crawl.log` (ear-digest만 `ear/digest.log`).
**cwd**: 스크립트가 스스로 `cd $PROJECT_DIR` (brain). 추출 세션은 `~/.claude-headless` 경량 프로필로 나간다 (2026-09-02).

## B. 주간 분석·자동개선 배치 (11:00–13:00 월요일)

데이터 수집 + 성능 측정 + 자가 진화. `Weekday=1` (월요일) 고정.

| 시각 | 라벨 | 실행 대상 | 역할 |
|---|---|---|---|
| 11:00 | `com.comad.crawl-github` | `brain/scripts/crawl-github.sh` | GitHub trending → `/tmp/ko-github-{date}.json` (GITHUB_TOKEN via `gh auth`) |
| 11:30 | `com.comad.monitor-upstream` | `brain/scripts/monitor-upstream.sh` | 채택한 upstream 레포의 release/tag 추적, ReferenceCard 노드로 Brain에 적재 |
| 12:00 | `com.comad.search-weekly` | `brain/scripts/search-weekly.sh` | 주간 레퍼런스 검색. 결과 → `brain/search-weekly.log` |
| 12:30 | `com.comad.evolution-loop` | `brain/scripts/evolution-loop.sh` | 자기 진화 루프. Trigger: Brain +10 nodes / 벤치 -5%+ / upstream major update / fallback weekly |
| 13:00 | `com.comad.run-benchmark` | `brain/scripts/run-benchmark.sh` | GraphRAG 벤치 20문항 → `data/benchmark-{date}.json`, 회귀 감지 시 알림. 답변 합성(`synthesizer.ts`)은 **`claude -p --model haiku` 고정** (2026-09-03 — 이전엔 대화형 `/model` 을 상속해 opus/fable 로 월 50세션). 벤치 지표 `entity_recall` 은 답변 문자열에 기대 엔티티가 포함되는지만 보므로 합성 티어와 무관 |

**공용 로그**: 10개 모두 plist-level stdout은 `brain/crawl.log` 또는 `ear/digest.log`로 감. `search-weekly`는 여기에 더해 스크립트 내부에서 `brain/search-weekly.log`에 WARN을 append.

## C. 실시간 폴링

| 주기 | 라벨 | 상태 (2026-09-03 실측) |
|---|---|---|
| 매 15분 (`StartInterval 900s`) | `com.comad.ear-poll` | **활성** (install.sh 가 등록). Discord Mode B 폴링(REST 기반, 0 IDENTIFY quota). 실행: `/bin/bash ear/poll-ear.sh`. 새 메시지당 `claude -p --model sonnet` (2026-09-03 고정 — 이전엔 fable 상속). 31개 중 유일하게 `WorkingDirectory` 를 둔 plist (ear) |
| 매 15분 (`StartInterval 900s`) | `com.comad.ci-healer` | **활성, dry_run=false (실모드)**. GH Actions 실패 감지 → headless claude(opus) 수정 → 자동 PR (머지는 사람). config: `~/.claude/skills/comad-ci-healer/config.json`. **2026-09-03 가드**: `max_run_age_hours=24` (그보다 오래된 실패 run 무시 — seen.json 리셋 뒤 수주 전 실패 14건을 30분에 힐한 08-19 버스트 방지) · `max_heals_per_poll=2` (상한 밖 run 은 seen 에 안 남겨 다음 폴링에 이어서) |
| **매 60분** (`StartInterval 3600s`) | `com.comad.pr-review` | **활성, dry_run=false**. 신규 PR headSha dedup → 4축 채점 → 인라인+요약 코멘트. 2026-06-04 이후 리뷰 0건(신규 PR 없음)이라 2026-09-03 에 20분 → 60분 (gh 폴링 −2,000회/월, LLM 비용 원래 0) |

## D. 자가발전 루프 (loopy-era 계열) — 2026-09-03 기준

수확 → 분석 → 승인요청 → 도달 → 적용 → 계측 → 감사의 닫힌 루프. 전부 비정각 분 오프셋(`feedback_cron_offset_safety` 준수).
**cwd 주의**: launchd 는 `WorkingDirectory` 가 없으면 `/` 에서 실행한다. 이 계열은 전부 `/` cwd 이고, 그래서 트랜스크립트가 `~/.claude/projects/-/` 에 쌓인다. 프로젝트 CLAUDE.md 는 안 실리지만 전역 CLAUDE.md·rules·MEMORY.md 는 실린다.

| 주기 | 라벨 | 역할 |
|---|---|---|
| **매 60분** (2026-09-03, 30→60분) | `com.comad.loopy-era` | supervisor **7-phase** tick: init → qa-scenario → trigger → **04 self-improve worker**(2026-08-18 재설치, 펜딩 커밋 1건/tick 을 `llm-dispatch.sh` 로 분석) → verify → verify-final → closeout. 펜딩 처리량(일 ~17건) 대비 tick 24회/일이면 손실 없음. **results.tsv 는 하루 1행** (15-closeout 이 마지막 행의 UTC 날짜로 게이트; `COMAD_RESULTS_EVERY_TICK=1` 로 옛 동작). 05-verify 는 `HARNESS_SKIP_COST=1` 로 비용 스캔 생략(점수에 안 들어감) |
| 매 2시간 | `com.comad.kb-sleep` | memory/*.md → kb_facts 추출·임베딩·rule-only consolidate → memory-log 퍼블리시 (로컬 ollama, LLM API 없음). 로그 55MB×2 누적 — 로테이션 필요 |
| 매일 03:15 | `com.comad.auto-dream` | dream_pending 시 comad-sleep 에이전트 headless 실행 (`--model sonnet`, 서브에이전트 `CLAUDE_CODE_SUBAGENT_MODEL=sonnet`). 08-31 실행 «병합/삭제 0건» — dream 임계 재검토 후보 |
| 매일 04:00 | `com.comad.nightly-audit` | 시스템 자가감사(`--model opus`, 평균 17.6턴) → 사람 판단 필요 항목만 결정 큐 에스컬레이트. codex doctor·HARD 훅 ROI(hook-fires.tsv)·threads 게이트 캘리브레이션 점검 포함. `--add-dir comad-world ~/.comad ~/.claude` 로 감사 범위 명시 (2026-09-03) |
| 매주 일 09:17 | `com.comad.learn-weekly` | T6 pending 자동 분석(comad-learn, `--model opus`, 68턴). SOFT 승격 자동, HARD 는 결정 큐 승인 요청만. `--add-dir ~/.claude ~/.comad` (2026-09-03) |
| 매주 월 08:13 | `com.comad.decision-digest` | 결정 큐 적체 시 Discord 다이제스트 (LLM 불필요 — 봇 REST 직접 호출) |
| 매주 월 09:00 | `com.comad.foresight` | brain hot클러스터 → 10렌즈 전략 foresight (`--model opus` 단발). **dry_run=false — Discord 전송 중** (카탈로그의 옛 `dry_run=true` 표기는 stale 이었음, 2026-09-03 정정) |
| 매 6시간 | `com.comad.evolve` | comad-evolve Phase 1 (trend harvest 만, LLM 없음) |
| 매월 2일 10:23 | `com.comad.evolve-monthly` | comad-evolve Phase 2~ (`--model opus`, 65턴). 서브에이전트 sonnet 고정 |
| 분기 11일 09:37 (3·6·9·12월) | `com.comad.entropy-audit` | 90일 기여 증거 감사 — 무참조 메모리·무발화 훅·실작동 0 크론을 결정 큐로. 1회차 2026-09-11 (콜드스타트 가드). 서브에이전트 sonnet 고정 |
| 매주 화 09:41 | `com.comad.job-scan` | 구직 공고 주간 모니터링 (`loopy-era/bin/job-scan-weekly.sh`, `--model sonnet` + 서브에이전트 sonnet 고정 — 이전엔 서브에이전트가 opus-5 126턴). 기준 `~/.claude/.comad/job-scan/criteria.md`, 중복 방지 `seen.txt`. 신규 0건이면 침묵 |

**계측 파일** (감사의 증거 데이터): `~/.claude/.comad/{memory-usage,hook-fires,sdk-usage,tool-durations}.tsv` + `results.tsv` (2026-09-03 부터 맨 끝 4열 `headless_tokens_24h`·`headless_usd_24h`·`interactive_tokens_24h`·`interactive_usd_24h` 추가 — 크론 효율은 headless_* 만 본다. `usd_24h` 는 대화형 cache_read 에 묻혀 지표로 못 쓴다).
**cron-catchup 카탈로그** (`chrome-starting-page/data/comad-crons.json`): 2026-09-03 에 loopy-era·kb-sleep·auto-dream·nightly-audit·decision-digest·learn-weekly·job-scan·ak-weekly 8종 등재. 단 `plugins/comad.js` 의 scheduled 판정은 weekday `daily`·`monday` 만 인식하므로 일·화요일 잡은 그 줄을 확장하기 전까지 `not_scheduled` 로 보인다.

## E. 기타 잡 (개인 운영·보관)

| 주기 | 라벨 | 실행 대상 | 역할 · 상태 |
|---|---|---|---|
| 매주 일 10:17 | `com.comad.ak-weekly` | `~/.claude/.comad/bin/ak-weekly.sh` | AK 암묵지 위클리 생성 (`claude -p --model sonnet`, 36턴) → Discord 검수. 산출 `~/kakao-archive/agentkorea/review/weekly/` |
| 매일 04:17 | `com.comad.kakao-archive` | `~/kakao-archive/agentkorea/tools/archive.sh` (homebrew bash) | 카톡 운영진방 복호 아카이브 (LLM 없음) |
| 매일 04:23 | `com.comad.codex-session-retention` | `~/.claude/.comad/bin/codex-session-retention.sh` | codex 세션 파일 보존기간 정리 (LLM 없음) |
| 부팅 시 (RunAtLoad) | `com.comad.cron-catchup` | `brain/scripts/cron-catchup.sh` | 대시보드 API(`localhost:1111/api/comad/cron/status`)로 오늘 미발화 크론을 `launchctl kickstart`. 카탈로그 = `comad-crons.json` |
| 07:23 · 19:23 | `com.comad.threads-watch` | `~/Programmer/01-comad/threads-watch/bin/watch.sh` | AI 계정 Threads 모니터링 → 판정(포스트 1건 = 1세션) → brain. **2026-09-02 사용자 중단(언로드)** — 월 2,584세션에 채택 high 0.1%, 수집 6시간/런이 한도 소진 사망 2건의 원인. plist 는 남아 있고 `launchctl list` 에 없음 |
| 매일 08:47 | `com.comad.shop-brief` | `~/.claude/skills/shop-report/bin/shop-cron.sh` | 편집샵 아침 브리핑. **plist 만 있고 미로드** |
| 매일 21:37 | `com.comad.shop-closeout` | `~/.claude/skills/shop-report/bin/shop-cron.sh` | 편집샵 마감. **plist 만 있고 미로드** |
| **매월 1일 03:41** (2026-09-03 신설) | `com.comad.transcript-archive` | `~/.claude/.comad/bin/transcript-archive.sh` | `~/.claude/projects` · `~/.claude-headless/projects` 의 세션·서브에이전트 트랜스크립트 중 7일보다 오래되고 지난 컷오프보다 새로운 것을 `~/.claude/.comad/transcript-archive/YYYY-MM.tgz` 로 보관 (원본 삭제 안 함 — Claude Code 자체 정리가 담당). 로그 `archive.log`. 첫 실행 2026-09-03: 4,021파일 613MB → 305MB |

## F. 헤드리스 LLM 모델 정책 (2026-09-03)

헤드리스 감사(`scratchpad/audit/headless.md`) 결론: 헤드리스 전체는 notional 비용의 ~1.6% 지만 «한도 잔여분» 을 갉아먹는다. 원칙:

1. **모든 `claude -p` 는 `--model` 을 명시한다.** 미지정 시 대화형 `/model`(opus/fable) 을 상속한다 (2026-09-02 커밋 47a5316 + 2026-09-03 synthesizer·ear-poll).
2. **에이전트를 스폰하는 스크립트는 `CLAUDE_CODE_SUBAGENT_MODEL=sonnet` 을 export 한다.** `--model` 은 메인 세션만 고정하고 서브에이전트는 상위 모델로 나갔다 (job-scan: sonnet 지정인데 opus-5 126턴). 2026-09-03 실측: `CLAUDE_CODE_SUBAGENT_MODEL=haiku claude -p --model sonnet` → 메인 `claude-sonnet-5`, 서브에이전트 `claude-haiku-4-5` (frontmatter 에 `model:` 이 없는 에이전트 기준. frontmatter 가 있는 에이전트는 `CLAUDE_CODE_SUBAGENT_MODEL_FORCE` 가 별도로 존재 — 미검증). 적용: job-scan·auto-dream·nightly-audit·learn-weekly·evolve-monthly·entropy-audit.
3. **판단 작업(nightly-audit·learn-weekly·foresight·evolve-monthly·entropy-audit)은 opus 유지**, 추출·채점·합성은 haiku/sonnet.
4. **순수 텍스트 호출은 `~/.claude-headless` 경량 프로필** + `--disable-slash-commands --strict-mcp-config` (2026-09-02).

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
- `loopy-era` 15-closeout → `results.tsv` 하루 1행 → nightly-audit 가 읽는다 (`score`/`score_v1` 혼동 금지)

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
| `brain/catchup.log` | 1개 (cron-catchup) |
| `~/.comad/loopy-era/logs/*` | D 계열 + ak-weekly + codex-session-retention + threads-watch(중단) |
| `~/.claude/.comad/{ci-healer,pr-review}/logs/` | ci-healer·pr-review |
| `~/.claude/.comad/transcript-archive/archive.log` | transcript-archive |
| `~/kakao-archive/agentkorea/cron.{log,err}` | kakao-archive |
| `~/.comad/shop/logs/` | shop-brief·shop-closeout (미로드) |

**관찰**: `brain/crawl.log`는 9개 크론이 공용으로 쓰는 단일 파일 — 로그가 섞여 실패 진단 시 grep으로 라벨 필터링이 필요. 개선 여지. `kb-sleep-tick.log`·`kb-sleep.stderr.log` 는 각 55MB — 로테이션 필요.

---

## 주의사항

1. **월요일 집중**: 07:00–13:00에 10개 작업이 직렬로 발화. 대부분 경량이지만 `run-benchmark`는 GraphRAG 전체 쿼리라 무거울 수 있음. 실패 시 다음 주까지 재시도 없음.

2. **공용 로그 파일 경쟁**: `brain/crawl.log` 한 파일에 9개 크론이 append. 동시 쓰기는 launchd 일정상 거의 발생 안 하지만, 디스크 가득 차면 전체 파이프라인 침묵 실패 가능 → 주기적 logrotate 고려.

3. **GITHUB_TOKEN 의존**: `crawl-github`, `search-weekly`는 `gh auth token`으로 token 수취. `gh` 로그아웃 상태면 rate limit로 부분 실패 → 로그에 `[WARN] GITHUB_TOKEN not available` 출력.

4. **`ear-poll` 재활성화 시**: `RunAtLoad=true`라 `bootstrap` 직후 한 번 실행된다. `.env` 누락 상태로 bootstrap하면 첫 실행에서 fail 로그가 남음.

5. **한도(quota) 소진 시각**: 2026-09-01·09-02 두 번 01:20 KST 에 «out of extra usage» 로 헤드리스 판정이 죽었다. 원인은 저녁 대화형 세션(턴당 컨텍스트 중앙값 420k)이 한도를 비운 직후 19:23 발화분 threads 판정이 도는 구조. threads-watch 는 중단됐지만 같은 시간대의 다른 헤드리스 잡(auto-dream 03:15·nightly-audit 04:00)도 동일 위험 — 실패 로그에 `usage` 문구가 있으면 모델이 아니라 한도 문제다.

6. **`--add-dir` 는 프롬프트 «뒤»에**: variadic 옵션이라 `--add-dir a b "$PROMPT"` 로 쓰면 프롬프트가 디렉터리로 삼켜진다.

> Aqua 세션 필요·Keychain OAuth 같은 플랫폼 차원 제약은 [`launchd/README.md`](../brain/scripts/launchd/README.md#caveats) 참고.

---

*Last reviewed: 2026-09-03. 크론 수·시각이 변경되면 이 문서와 `chrome-starting-page/data/comad-crons.json` 을 함께 업데이트.*

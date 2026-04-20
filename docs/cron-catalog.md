# Cron Catalog

코마드월드의 모든 스케줄 작업을 한 곳에서 본다. 현재 macOS `launchd`에 **10개 활성 + 1개 비활성** = 총 11개가 등록되어 있다.

> **크로스플랫폼 진입점**: `brain/scripts/schedule-install.sh` — macOS는 `launchd`, Linux/WSL은 `cron`, Windows는 Task Scheduler로 라우팅. 자세한 설치·보안 주의사항은 [`brain/scripts/launchd/README.md`](../brain/scripts/launchd/README.md) 참고.

## 목차

- [A. 일일 수집 파이프라인](#a-일일-수집-파이프라인-07001000-매일) — 매일 07:00–10:00
- [B. 주간 분석·자동개선 배치](#b-주간-분석자동개선-배치-11001300-월요일) — 매주 월 11:00–13:00
- [C. 실시간 폴링](#c-실시간-폴링-비활성) — 비활성
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

## C. 실시간 폴링 (비활성)

| 주기 | 라벨 | 상태 |
|---|---|---|
| 매 15분 (`StartInterval 900s`) | `com.comad.ear-poll` | **`.plist.disabled`**. Discord Mode B 폴링(REST 기반, 0 IDENTIFY quota). 활성화 조건: `~/.claude/channels/discord2/.env` 존재 |

실행 경로: `/bin/bash ear/poll-ear.sh` · 로그: `ear/launchd-poll-{out,err}.log`
활성 시 `RunAtLoad=true`라 로드 직후 1회 실행됨에 주의.

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

## `ear-poll` 활성화 (비활성 → 활성 전환 시)

```sh
ls ~/.claude/channels/discord2/.env || echo "env 파일 먼저 준비 필요"
mv ~/Library/LaunchAgents/com.comad.ear-poll.plist.disabled \
   ~/Library/LaunchAgents/com.comad.ear-poll.plist
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.comad.ear-poll.plist
```

일반 설치·제거·상태 조회는 [`brain/scripts/launchd/README.md`](../brain/scripts/launchd/README.md) 참고.

---

## 로그 위치

| 로그 파일 | 생산자 (크론 수) |
|---|---|
| `brain/crawl.log` | 9개 (ear-ingest, crawl-arxiv, ingest-geeknews, crawl-blogs, crawl-github, monitor-upstream, evolution-loop, run-benchmark, 그리고 stderr) |
| `ear/digest.log` | 1개 (ear-digest) |
| `brain/search-weekly.log` | 1개 (search-weekly, 스크립트 내부 appender) |
| `ear/launchd-poll-{out,err}.log` | 1개 (ear-poll, 비활성) |

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

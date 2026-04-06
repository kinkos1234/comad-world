# ComadSleep

**Claude Code 메모리를 위한 수면 주기.**

ComadSleep은 Claude Code의 자동 메모리 파일을 정리하고, 중복을 제거하고, 오래된 항목을 가지치기하는 서브에이전트입니다. 사람의 수면이 기억을 정리하듯이요.

Claude Code의 [Auto Memory](https://docs.anthropic.com/en/docs/claude-code/memory)는 세션마다 계속 쌓입니다. 시간이 지나면 중복, 죽은 참조, 임시 메모가 쌓이죠. ComadSleep은 한마디로 정리합니다.

```
나: dream
claude: ComadSleep — 2026-03-24: 3개 프로젝트, 5개 파일 스캔.
        중복 4개 병합, 죽은 참조 2개 제거, 백업 완료.
```

## Auto-dream이 있는데 왜 이게 필요해?

Claude Code에는 `autoDreamEnabled`라는 미공개 자동 메모리 정리 기능이 있습니다. 그런데 왜 ComadSleep?

| | Auto-dream | ComadSleep |
|---|---|---|
| **제어** | Claude가 알아서 실행 | **내가** 원할 때 실행 |
| **백업** | 검증된 백업 없음 | 타임스탬프 백업 + 검증 후 진행 |
| **리포트** | 조용히 실행 | 뭘 바꿨는지 전체 리포트 |
| **범위** | 현재 프로젝트만 | 모든 프로젝트 한 번에 |
| **미리보기** | 불가 | dry-run으로 미리 확인 |
| **크로스 프로젝트** | 불가 | 프로젝트 간 중복 감지 |
| **잠금 안전** | 기본 | 이중 잠금 (자체 + OMC) |

**둘은 보완 관계입니다.** Auto-dream은 매일 가벼운 정비, ComadSleep은 주간 대청소 — 영수증 포함.

## 작동 방식

2단계 파이프라인:

```
Phase 1: Scan          Phase 2: Act
┌─────────────┐       ┌─────────────────┐
│ 현황 파악    │       │ 백업 (검증 포함) │
│ + 분석      │──────▶│ 병합 & 정리      │
│ + 분류      │       │ 가지치기 & 인덱싱 │
└─────────────┘       └─────────────────┘
        │                       │
   "CLEAN" ──▶ 끝        리포트 ──▶ 끝
```

**빠른 경로**: 지난 실행 이후 변경 없으면 한 줄로 끝. 토큰 낭비 없음.

### 하는 일

| 동작 | 예시 |
|------|------|
| **중복 병합** | MEMORY.md와 experiments.md에 같은 내용 → 하나로 |
| **죽은 참조 제거** | 만든 적 없는 `architecture.md` 링크 → 삭제 |
| **임시 메모 정리** | 2주 전 "현재 작업 중..." → 삭제 |
| **REVIEW 태그 해소** | 지난번에 태그한 항목이 해결됐으면 → 태그 제거 |
| **크로스 프로젝트 스캔** | 프로젝트에 저장된 범용 도구 메모 → 플래그 |
| **아티팩트 정리** | 오래된 `.consolidate-lock`, 임시 파일 → 삭제 |

### 절대 안 하는 일

- `CLAUDE.md` 수정 (사용자 지침은 신성불가침)
- 확실하지 않은 항목 삭제 (`[REVIEW NEEDED]` 태그 대신)
- 백업 검증 없이 진행
- `.omc/` 디렉토리나 프로젝트 소스코드 건드리기

## 설치

**한 줄 설치:**

```bash
curl -fsSL https://raw.githubusercontent.com/kinkos1234/comad-sleep/main/install.sh | bash
```

**수동 설치:**

```bash
cp comad-sleep.md ~/.claude/agents/
```

Claude Code 세션 재시작하면 바로 사용 가능.

### 선택: 세션 종료 시 자동 실행

```bash
cp hooks/comad-sleep-hook.json ~/.claude/hooks/
```

메모리가 150줄 이상이면 세션 종료 시 자동으로 ComadSleep 실행.

## 사용법

### 수동 실행

Claude Code에서 아무거나 입력:

```
dream
메모리 정리
정리해줘
꿈꿔
```

### 미리보기 (변경 없이 확인만)

```
dream dry-run
미리보기
```

### Discord 봇

Claude Code Discord 봇(ccc/ccd)에서도 동작. 채널에 `dream` 전송.

## 안전장치

ComadSleep은 데이터 손실에 편집증적입니다:

1. **백업 먼저** — 변경 전 타임스탬프 포함 백업 생성
2. **백업 검증** — 파일 수와 용량 비교. 불일치 시 중단.
3. **이중 잠금** — 자체 lock + OMC `.consolidate-lock` 모두 확인
4. **추측 금지** — 불확실한 항목은 삭제 대신 `[REVIEW NEEDED]` 태그
5. **상태 추적** — 마지막 실행 상태 기억, 변경 없는 프로젝트 스킵

## 예시: 정리 전 vs 후

**정리 전** (60줄, 문제 7개):
```
MEMORY.md:
  - Working on user authentication        ← 3주 전 메모 (stale)
  - 이번 세션에서 API 라우트 수정 중       ← 임시 메모
  - → See [architecture.md]               ← 죽은 링크
  - JWT token expiration not handled
  - JWT token expiry causes logout         ← 중복
```

**정리 후** (34줄, 문제 0개, -43%):
```
MEMORY.md:
  - Auth: Lucia with Prisma adapter (see experiments.md)
  - JWT token expiration not handled
  - Rate limiting needed (upstash/ratelimit in progress)
```

전체 예시는 [examples/](examples/) 참고.

## 요구사항

- Claude Code (커스텀 에이전트 지원 버전)
- 끝. 의존성 없음, 빌드 없음, 런타임 없음.

## 라이선스

MIT

---

*수면이 기억을 정리하듯 — Anthropic의 미공개 Auto-dream 기능에서 영감을 받았습니다.*

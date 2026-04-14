# ADR 0011 — Mono-repo Reversal (Supersedes 0001)

- **Status:** Accepted
- **Date:** 2026-04-14
- **Deciders:** Comad World maintainer (@kinkos1234)
- **Supersedes:** [ADR 0001 — Repository Strategy](0001-repository-strategy.md)

## Context

ADR 0001은 "umbrella + 6 nested `.git`" 분리 전략을 선언했다. 하지만 2026-04-14 감사에서 다음이 드러났다.

1. **사용자 관점에서 이미 mono-repo.** umbrella는 이미 모든 모듈 소스 (brain/packages/core/src, eye/src/comad_eye 등)를 트래킹하고 있었다. `git clone comad-world` 한 번으로 완전한 시스템이 재현된다.

2. **Nested `.git` 원격은 존재하지 않는다.** `brain/.git`의 origin은 `github.com/kinkos1234/comad-brain.git` — 404. ear·eye·photo·sleep·voice 모두 동일. `scripts/upgrade.sh`의 per-module pull 로직은 실제로 작동한 적이 없다.

3. **채택률 관점에서 분리 구조는 역효과.** 15 stars, 1 maintainer, 독립 포크 요청 0건. "한 번에 clone, 한 번에 작동"이 초기 OSS의 유일한 레버(Norman/Linus/DHH/Collison/Moore/Evan You 6인 만장일치).

4. **Dual-tracking 혼란.** 같은 파일이 umbrella git과 nested git 양쪽에서 추적됐다. 오늘 세션에서 동일 파일이 양쪽 git에 각각 커밋되는 사고가 발생했다.

## Decision

ADR 0001을 폐기하고 단일 레포 구조로 정정한다.

1. **6개 nested `.git` 아카이브 후 제거** — `/tmp/comad-nested-git-archive/`로 이동 (복구 필요 시 7일 내 복귀 가능).
2. **Umbrella가 유일한 git.** 모든 모듈 파일은 umbrella의 일급 트래킹 대상.
3. **`scripts/upgrade.sh`의 per-module pull 로직 단순화** — 단일 `git pull`로 축소 (후속 PR).
4. **`comad.lock`은 과도기 유물로 보존** — 향후 릴리스 태그로 대체 예정.

## Consequences

**+** `git clone comad-world` → `./install.sh` → 즉시 작동. Onboarding 마찰 최소.
**+** Dependabot, changesets, release-please, GitHub Actions 등 모든 표준 OSS 도구와 궁합 회복.
**+** 사고 재발 방지 — "어느 git에 commit했지?" 질문이 사라짐.
**−** 모듈별 독립 릴리스 가능성 상실. 필요해지는 시점(외부 포크 등장)이 오면 ADR 0012로 재분리 가능. **YAGNI.**
**−** Nested git의 히스토리(brain 77M 포함)가 공개 원격에 게시되지 않음. 내부 archive로만 보존.
**−** ADR 0001의 Structure Guard CI는 여전히 유효 (루트 중복 파일 방지) — 유지.

## Rollback Plan

문제 발생 시 7일 내:
```bash
for m in brain ear eye photo sleep voice; do
  mv /tmp/comad-nested-git-archive/$m.git $m/.git
done
```

## Related

- 부모 결정: ADR 0001 (Superseded)
- 연쇄 결정: ADR 0007-0010 (luminary review gap packs — 이 리뷰의 후속)

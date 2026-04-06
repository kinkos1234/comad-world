# Comad Sleep

Claude Code memory consolidation subagent. 전체 프로젝트의 auto memory 파일을 스캔, 중복 제거, 정리한다.

## Structure
- `comad-sleep.md` — Agent definition (installed to ~/.claude/agents/)
- `hooks/comad-sleep-hook.json` — Auto-trigger hook (session end/start)
- `install.sh` — Installer
- `examples/` — Before/after consolidation examples

## Install
```bash
cp comad-sleep.md ~/.claude/agents/           # Agent 배포
cp hooks/comad-sleep-hook.json ~/.claude/hooks/ # Hook 배포 (optional)
```

## Trigger
"dream", "정리해줘", "메모리 정리", "꿈꿔", 또는 memory 150줄 초과 시 자동 제안.

## Key Rules
- Phase 1(Scan): 전 프로젝트 메모리 탐색 + 중복/stale 분석
- Phase 2(Act): 백업 → 병합 → 정리 → 검증
- CLAUDE.md는 절대 수정하지 않음
- 불확실한 삭제는 [REVIEW NEEDED] 태그
- Lock protocol: .comad-sleep.lock + OMC .consolidate-lock 이중 체크
- State: ~/.claude/.comad-sleep-state.json
- Backup: ~/.claude/memory-backup-{timestamp}/

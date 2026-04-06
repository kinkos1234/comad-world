# Comad Voice

Claude Code workflow harness for non-developers. 6개 자동 트리거(T0-T5)로 AI 개발 워크플로우를 자동화한다.

## Structure
- `core/comad-voice.md` — Main config (installed to ~/.claude/CLAUDE.md)
- `core/triggers/` — T0(onboarding) T1(review) T2(fullcycle) T3(parallel) T4(polish) T5(session-save)
- `memory-templates/` — MEMORY.md, experiments.md, architecture.md templates
- `install.sh` — One-line installer (v2.0.0)
- `tests/test_install.bats` — BATS test suite

## Commands
```bash
./install.sh                        # Install to ~/.claude/CLAUDE.md
bats tests/test_install.bats       # Run tests
```

## CI
GitHub Actions: markdownlint + install.sh syntax check + bats tests. Triggers on push/PR to main.

## Key Rules
- CLAUDE.md 삽입 시 COMAD-VOICE:START/END 마커 사용
- install.sh는 기존 CLAUDE.md 백업 후 append
- Standalone 동작 (Claude Code만으로 완전 독립 동작, 외부 의존성 없음)
- Trigger 파일 수정 시 core/comad-voice.md도 동기화 필요

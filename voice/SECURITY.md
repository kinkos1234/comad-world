# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.0.x   | :white_check_mark: |

## Reporting a Vulnerability

Comad Voice는 `~/.claude/CLAUDE.md`에 설정을 추가하는 도구입니다.
보안 취약점을 발견하셨다면 아래 절차를 따라주세요:

1. **공개 Issue로 올리지 마세요** — 취약점 정보가 공개될 수 있습니다
2. GitHub의 [Private vulnerability reporting](https://github.com/kinkos1234/comad-voice/security/advisories/new)을 사용해주세요
3. 또는 GitHub 프로필을 통해 직접 연락해주세요

### 응답 시간

- 확인: 48시간 이내
- 초기 평가: 1주 이내
- 수정 배포: 심각도에 따라 결정

## Scope

보안 검토 대상:
- `install.sh` — 시스템 파일 수정
- `core/comad-voice.md` — CLAUDE.md에 주입되는 설정

보안 검토 대상이 아닌 것:
- Claude Code 자체의 취약점 (Anthropic에 별도 신고)

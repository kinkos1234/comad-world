#!/bin/zsh
# DEPRECATED: 다이제스트 생성은 ear 봇 세션 시작 시 자동 수행됨 (CLAUDE.md 참조)
# launchd cron에서 claude -p는 OAuth 인증 불가로 동작하지 않음.
# 이 스크립트는 더 이상 실행하지 않음. launchd에서 제거할 것.
echo "$(date '+%Y-%m-%d %H:%M:%S') [SKIP] Digest generation moved to ear bot session (CLAUDE.md)" >> "$HOME/Programmer/01-comad/comad-world/ear/digest.log"

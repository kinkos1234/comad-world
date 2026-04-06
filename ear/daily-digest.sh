#!/bin/zsh
# DEPRECATED: 다이제스트 생성은 ear 봇 재시작 시 자동 수행됨 (CLAUDE.md 참조)
# claude -p 는 크론 환경에서 OAuth 인증 불가로 동작하지 않음.
# 이 크론 항목을 제거하려면: crontab -e 에서 daily-digest.sh 줄 삭제
echo "$(date '+%Y-%m-%d %H:%M:%S') [SKIP] Digest generation moved to ear bot startup (CLAUDE.md)"

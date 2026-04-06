#!/bin/zsh
export PATH="$HOME/.local/bin:$HOME/.bun/bin:/opt/homebrew/bin:$PATH"
export SHELL="/bin/zsh"
export USER="jhkim"
export TERM="xterm-256color"

EAR="$HOME/Programmer/01-comad/comad-world/ear"
YESTERDAY=$(date -v-1d +%Y-%m-%d)
DIGEST_FILE="$EAR/digests/${YESTERDAY}-digest.html"
TEMPLATE="$EAR/digest-template.html"
LOG="$EAR/digest.log"

# Skip if already generated
if [[ -f "$DIGEST_FILE" ]]; then
  echo "$(date '+%Y-%m-%d %H:%M:%S') Digest for $YESTERDAY already exists, skipping" >> "$LOG"
  exit 0
fi

# Check if there are archive files for yesterday
ARTICLES=$(ls "$EAR/archive/${YESTERDAY}-"* 2>/dev/null)
if [[ -z "$ARTICLES" ]]; then
  echo "$(date '+%Y-%m-%d %H:%M:%S') No articles for $YESTERDAY, skipping digest" >> "$LOG"
  exit 0
fi

COUNT=$(echo "$ARTICLES" | wc -l | tr -d ' ')
echo "$(date '+%Y-%m-%d %H:%M:%S') Generating digest for $YESTERDAY ($COUNT articles)..." >> "$LOG"

# Generate digest using claude -p
PROMPT="다음은 ${YESTERDAY}의 아카이브 기사들이다. digest-template.html을 참조하여 HTML 다이제스트를 생성하라. 순수 HTML만 출력하라.

템플릿:
$(cat "$TEMPLATE")

기사들:
$(for f in $EAR/archive/${YESTERDAY}-*; do echo "---"; cat "$f"; done)

날짜: $YESTERDAY
기사 수: $COUNT"

echo "$PROMPT" | claude -p --model haiku > "$DIGEST_FILE" 2>> "$LOG"

if [[ -s "$DIGEST_FILE" ]]; then
  echo "$(date '+%Y-%m-%d %H:%M:%S') ✓ Digest generated: $DIGEST_FILE" >> "$LOG"
else
  rm -f "$DIGEST_FILE"
  echo "$(date '+%Y-%m-%d %H:%M:%S') ✗ Digest generation failed" >> "$LOG"
fi

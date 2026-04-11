#!/bin/zsh
# monitor-upstream.sh — Track adopted upstream repos for updates
# Cron: 0 11 * * 1 (weekly Monday 11:30)
#
# Checks GitHub releases/tags for repos that Comad has adopted patterns from.
# New releases are logged and stored in Brain as ReferenceCard nodes.

export PATH="$HOME/.local/bin:$HOME/.bun/bin:/opt/homebrew/bin:$PATH"
export SHELL="/bin/zsh"
export USER="jhkim"
export TERM="xterm-256color"

PROJECT_DIR="$HOME/Programmer/01-comad/comad-world/brain"
STATE_FILE="$PROJECT_DIR/data/.upstream-state.json"
LOG="$PROJECT_DIR/upstream-monitor.log"
TODAY=$(date +%Y-%m-%d)

# Repos to monitor (adopted patterns from these)
REPOS=(
  "anthropics/claude-code"
  "anthropics/anthropic-sdk-python"
  "modelcontextprotocol/servers"
  "zombieFox/nightTab"
  "nicepkg/gpt-runner"
  "langchain-ai/langchain"
  "neo4j/neo4j"
  "oven-sh/bun"
  "microsoft/playwright"
)

# Get GitHub token for API rate limits
GITHUB_TOKEN=$(gh auth token 2>/dev/null)
if [[ -z "$GITHUB_TOKEN" ]]; then
  echo "[$TODAY] [WARN] No GITHUB_TOKEN — rate limits may apply" >> "$LOG"
fi

AUTH_HEADER=""
if [[ -n "$GITHUB_TOKEN" ]]; then
  AUTH_HEADER="Authorization: Bearer $GITHUB_TOKEN"
fi

# Initialize state file if missing
if [[ ! -f "$STATE_FILE" ]]; then
  echo '{}' > "$STATE_FILE"
fi

echo "[$TODAY] Upstream monitor — checking ${#REPOS[@]} repos" >> "$LOG"

UPDATES_FOUND=0

for repo in "${REPOS[@]}"; do
  # Fetch latest release
  if [[ -n "$AUTH_HEADER" ]]; then
    RESPONSE=$(curl -sS -H "$AUTH_HEADER" "https://api.github.com/repos/$repo/releases/latest" 2>/dev/null)
  else
    RESPONSE=$(curl -sS "https://api.github.com/repos/$repo/releases/latest" 2>/dev/null)
  fi

  TAG=$(echo "$RESPONSE" | grep '"tag_name"' | head -1 | sed 's/.*: "//;s/".*//')
  PUBLISHED=$(echo "$RESPONSE" | grep '"published_at"' | head -1 | sed 's/.*: "//;s/".*//')

  if [[ -z "$TAG" ]]; then
    # No releases — try latest tag instead
    if [[ -n "$AUTH_HEADER" ]]; then
      TAG_RESPONSE=$(curl -sS -H "$AUTH_HEADER" "https://api.github.com/repos/$repo/tags?per_page=1" 2>/dev/null)
    else
      TAG_RESPONSE=$(curl -sS "https://api.github.com/repos/$repo/tags?per_page=1" 2>/dev/null)
    fi
    TAG=$(echo "$TAG_RESPONSE" | grep '"name"' | head -1 | sed 's/.*: "//;s/".*//')
    PUBLISHED="$TODAY"
  fi

  if [[ -z "$TAG" ]]; then
    echo "  ⚠ $repo — no releases or tags found" >> "$LOG"
    continue
  fi

  # Compare with saved state
  LAST_TAG=$(cat "$STATE_FILE" | grep "\"$repo\"" | sed 's/.*: "//;s/".*//')

  if [[ "$TAG" != "$LAST_TAG" && -n "$TAG" ]]; then
    echo "  ★ $repo: $LAST_TAG → $TAG (published: $PUBLISHED)" >> "$LOG"
    UPDATES_FOUND=$((UPDATES_FOUND + 1))

    # Archive update info for Brain ingest
    UPDATE_FILE="$PROJECT_DIR/data/upstream-updates/$TODAY-$(echo $repo | tr '/' '-').md"
    mkdir -p "$(dirname "$UPDATE_FILE")"
    cat > "$UPDATE_FILE" << MDEOF
---
date: $TODAY
relevance: 추천
categories: [Tool, OpenSource]
source: https://github.com/$repo/releases/tag/$TAG
---

# $repo $TAG 릴리즈

## 핵심 요약
- $repo가 $TAG 버전을 릴리즈함
- 이전 추적 버전: ${LAST_TAG:-"(최초 추적)"}
- Comad가 이 프로젝트의 패턴을 채택하고 있어 변경사항 검토 필요

## 왜 알아야 하는가
Comad 시스템이 이 프로젝트에서 패턴을 내재화했으므로, 주요 변경사항이 우리 구현에 영향을 줄 수 있다. CHANGELOG를 확인하고 필요시 내재화 업데이트 검토.
MDEOF

  else
    echo "  · $repo: $TAG (unchanged)" >> "$LOG"
  fi
done

# Update state file with all current tags
echo '{' > "${STATE_FILE}.tmp"
FIRST=true
for repo in "${REPOS[@]}"; do
  if [[ -n "$AUTH_HEADER" ]]; then
    TAG=$(curl -sS -H "$AUTH_HEADER" "https://api.github.com/repos/$repo/releases/latest" 2>/dev/null | grep '"tag_name"' | head -1 | sed 's/.*: "//;s/".*//')
  else
    TAG=$(curl -sS "https://api.github.com/repos/$repo/releases/latest" 2>/dev/null | grep '"tag_name"' | head -1 | sed 's/.*: "//;s/".*//')
  fi
  [[ -z "$TAG" ]] && continue
  if [[ "$FIRST" == "true" ]]; then
    FIRST=false
  else
    echo ',' >> "${STATE_FILE}.tmp"
  fi
  printf '  "%s": "%s"' "$repo" "$TAG" >> "${STATE_FILE}.tmp"
done
echo '' >> "${STATE_FILE}.tmp"
echo '}' >> "${STATE_FILE}.tmp"
mv "${STATE_FILE}.tmp" "$STATE_FILE"

echo "[$TODAY] ✓ Monitor complete: $UPDATES_FOUND updates found" >> "$LOG"

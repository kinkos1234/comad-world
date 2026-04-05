#!/bin/bash
# apply-config.sh — Generate module configs from comad.config.yaml
#
# Reads comad.config.yaml and generates:
#   - ear/interests.md
#   - ear/CLAUDE.md
#
# Brain crawlers read comad.config.yaml directly at runtime.
# Eye, photo, sleep, voice are domain-agnostic (no generation needed).

set -euo pipefail

CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info()  { echo -e "  ${GREEN}✓${NC} $1"; }
warn()  { echo -e "  ${YELLOW}!${NC} $1"; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
CONFIG="$ROOT_DIR/comad.config.yaml"

if [ ! -f "$CONFIG" ]; then
    echo "Error: comad.config.yaml not found."
    echo "Run: cp presets/ai-ml.yaml comad.config.yaml"
    exit 1
fi

echo ""
echo -e "${CYAN}Applying comad.config.yaml...${NC}"
echo ""

# ─── Check for yq (YAML processor) ───
if ! command -v yq &> /dev/null; then
    echo "Installing yq (YAML processor)..."
    if [[ "$OSTYPE" == "darwin"* ]]; then
        brew install yq 2>/dev/null || {
            echo "Please install yq: brew install yq"
            exit 1
        }
    else
        echo "Please install yq: https://github.com/mikefarah/yq"
        exit 1
    fi
fi

# ─── Generate ear/interests.md ───
echo "Generating ear/interests.md..."

INTERESTS_FILE="$ROOT_DIR/ear/interests.md"
cat > "$INTERESTS_FILE" << 'HEADER'
# User Interest Profile
# Auto-generated from comad.config.yaml
# Regenerate with: ./scripts/apply-config.sh

HEADER

echo "## High Priority (Core Focus)" >> "$INTERESTS_FILE"
yq '.interests.high[].name' "$CONFIG" | while read -r name; do
    examples=$(yq ".interests.high[] | select(.name == \"$name\") | .examples // [] | join(\", \")" "$CONFIG")
    if [ -n "$examples" ] && [ "$examples" != "" ]; then
        echo "- $name ($examples)" >> "$INTERESTS_FILE"
    else
        echo "- $name" >> "$INTERESTS_FILE"
    fi
done

echo "" >> "$INTERESTS_FILE"
echo "## Medium Priority (Worth Tracking)" >> "$INTERESTS_FILE"
yq '.interests.medium[].name' "$CONFIG" | while read -r name; do
    echo "- $name" >> "$INTERESTS_FILE"
done

echo "" >> "$INTERESTS_FILE"
echo "## Low Priority (Filter)" >> "$INTERESTS_FILE"
yq '.interests.low[].name' "$CONFIG" | while read -r name; do
    echo "- $name" >> "$INTERESTS_FILE"
done

info "ear/interests.md"

# ��── Generate ear/CLAUDE.md ───
echo "Generating ear/CLAUDE.md..."

LANGUAGE=$(yq '.profile.language' "$CONFIG")
CATEGORIES=$(yq '.categories | join(", ")' "$CONFIG")
MUST_READ_STACK=$(yq '.must_read_stack | join(", ")' "$CONFIG")
MUST_READ_RATIO=$(yq '.ear.must_read_ratio' "$CONFIG")
RECOMMENDED_RATIO=$(yq '.ear.recommended_ratio' "$CONFIG")
REFERENCE_RATIO=$(yq '.ear.reference_ratio' "$CONFIG")
MUST_READ_PCT=$(printf "%.0f" "$(echo "$MUST_READ_RATIO * 100" | bc)")
RECOMMENDED_PCT=$(printf "%.0f" "$(echo "$RECOMMENDED_RATIO * 100" | bc)")
REFERENCE_PCT=$(printf "%.0f" "$(echo "$REFERENCE_RATIO * 100" | bc)")
ARCHIVE_DIR=$(yq '.ear.archive_dir // "ear/archive"' "$CONFIG")
DIGEST_DIR=$(yq '.ear.digest_dir // "ear/digests"' "$CONFIG")

EAR_CLAUDE="$ROOT_DIR/ear/CLAUDE.md"
cat > "$EAR_CLAUDE" << EOF
# Comad Ear — Content Curator Rules
# Auto-generated from comad.config.yaml. Regenerate with: ./scripts/apply-config.sh

## Role

Discord content curator bot. Detects article links, fetches content,
classifies relevance, and archives to \`${ARCHIVE_DIR}/YYYY-MM-DD-[slug].md\`.

## Relevance Tiers

- **Must-Read (${MUST_READ_PCT}%):** Directly impacts current stack (${MUST_READ_STACK}). Security threats, paradigm shifts.
- **Recommended (${RECOMMENDED_PCT}%):** Core interest areas without immediate impact.
- **Reference (${REFERENCE_PCT}%):** Low relevance but tracks trends.

## Must-Read Stack

${MUST_READ_STACK}

## Categories

${CATEGORIES}

## Archive Format

File: \`${ARCHIVE_DIR}/YYYY-MM-DD-[kebab-case-slug].md\`

\`\`\`yaml
---
date: YYYY-MM-DD
relevance: Must-Read|Recommended|Reference
categories: [${CATEGORIES}]
source: original-article-url
---
\`\`\`

## Rules

- Content language: ${LANGUAGE}
- One article per file, no duplicates
- Generate daily digest in \`${DIGEST_DIR}/\`
EOF

# Append interest profile
echo "" >> "$EAR_CLAUDE"
echo "## Interest Profile" >> "$EAR_CLAUDE"
echo "" >> "$EAR_CLAUDE"
cat "$INTERESTS_FILE" >> "$EAR_CLAUDE"

info "ear/CLAUDE.md"

# ─── Summary ───
echo ""
echo -e "${GREEN}Done!${NC} Generated:"
echo "  - ear/interests.md"
echo "  - ear/CLAUDE.md"
echo ""
echo "Brain crawlers read comad.config.yaml directly at runtime."
echo "Eye, photo, sleep, voice are domain-agnostic (no config needed)."
echo ""

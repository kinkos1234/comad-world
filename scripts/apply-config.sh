#!/usr/bin/env bash
# apply-config.sh — Generate module configs from comad.config.yaml.
#
# Contract (see docs/adr/0002-config-contract.md):
#   Every top-level section in comad.config.yaml has an owner module and a
#   list of regeneration targets. This script walks the ownership matrix and
#   regenerates only what each present section requires.
#
# Today only the `interests` / `categories` / `must_read_stack` / `ear`
# sections drive generation (ear/interests.md + ear/CLAUDE.md). Brain reads
# `sources` / `brain.*` directly at runtime. Eye reads `eye.*` directly. The
# skeleton below makes it easy to add new generators without another
# structural refactor.
#
# Usage:
#   scripts/apply-config.sh             # regenerate
#   scripts/apply-config.sh --dry-run   # show targets, do not write
#   scripts/apply-config.sh --validate  # also run the schema validator
#
set -euo pipefail

# shellcheck source=scripts/lib/common.sh
. "$(dirname "${BASH_SOURCE[0]}")/lib/common.sh"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
CONFIG="$ROOT_DIR/comad.config.yaml"

DRY_RUN=0
RUN_VALIDATE=0
for arg in "$@"; do
  case "$arg" in
    --dry-run)  DRY_RUN=1 ;;
    --validate) RUN_VALIDATE=1 ;;
    -h|--help)  sed -n '2,19p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *)          die "Unknown arg: $arg" ;;
  esac
done

[ -f "$CONFIG" ] || die "comad.config.yaml not found. Run: cp presets/ai-ml.yaml comad.config.yaml"
comad_need yq "brew install yq (macOS) or https://github.com/mikefarah/yq" || exit 1

if [ "$RUN_VALIDATE" = "1" ]; then
  step "Validating comad.config.yaml"
  bash "$SCRIPT_DIR/validate-config.sh"
fi

step "Applying comad.config.yaml"
[ "$DRY_RUN" = "1" ] && warn "DRY-RUN — no files will be written"

# ─── Section: interests + ear → ear/interests.md, ear/CLAUDE.md ──────────────
generate_ear_configs() {
  local INTERESTS_FILE="$ROOT_DIR/ear/interests.md"
  local EAR_CLAUDE="$ROOT_DIR/ear/CLAUDE.md"

  if [ "$DRY_RUN" = "1" ]; then
    dim "    would regenerate: $INTERESTS_FILE"
    dim "    would regenerate: $EAR_CLAUDE"
    return 0
  fi

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

  local LANGUAGE CATEGORIES MUST_READ_STACK MUST_READ_RATIO RECOMMENDED_RATIO REFERENCE_RATIO
  local MUST_READ_PCT RECOMMENDED_PCT REFERENCE_PCT ARCHIVE_DIR DIGEST_DIR
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

  echo "" >> "$EAR_CLAUDE"
  echo "## Interest Profile" >> "$EAR_CLAUDE"
  echo "" >> "$EAR_CLAUDE"
  cat "$INTERESTS_FILE" >> "$EAR_CLAUDE"

  info "ear/CLAUDE.md"
}

# ─── Skeleton: future generators (no-op today, kept for discoverability) ─────
# Add a function here + call it below when the module needs generated config.
generate_brain_configs() {
  # Placeholder for ADR 0002 PR 3. Brain reads comad.config.yaml directly
  # today; when per-module typed loaders land, this function will emit
  # brain/config/runtime.yaml.
  :
}

generate_eye_configs() {
  # Placeholder for ADR 0002 PR 3. Eye overrides (.eye.*) will emit
  # eye/config/overrides.yaml once the eye loader accepts them.
  :
}

# ─── Dispatch ────────────────────────────────────────────────────────────────
generate_ear_configs
generate_brain_configs
generate_eye_configs

echo ""
info "apply-config complete"
dim "  Brain crawlers read comad.config.yaml directly at runtime."
dim "  Eye, photo, sleep, voice are domain-agnostic (no generation needed today)."

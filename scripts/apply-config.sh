#!/usr/bin/env bash
# apply-config.sh — Generate module configs from comad.config.yaml.
#
# Contract (see docs/adr/0002-config-contract.md):
#   Every top-level section in comad.config.yaml has an owner module and a
#   list of regeneration targets. This script walks the ownership matrix and
#   regenerates only what each present section requires.
#
# Current generators (ADR 0002 PR 2):
#   ear:   interests + ear.* → ear/interests.md, ear/CLAUDE.md
#   brain: sources, interests, brain.* → brain/config/{sources.yaml,
#          keywords.json, runtime.yaml}
#   eye:   eye.* → eye/config/overrides.yaml (merged over settings.yaml by
#          the pydantic loader in PR 3)
#
# Add a function here + call it below when a new module needs generated
# config. photo/sleep/voice are domain-agnostic and ingest nothing.
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

# ─── Section: sources + interests + brain → brain/config/*.{yaml,json} ───────
#
# Per ADR 0002 ownership matrix:
#   sources.*   → brain/config/sources.yaml
#   interests.* → brain/config/keywords.json
#   brain.*     → brain/config/runtime.yaml
#
# These artifacts are forward-compatible with the typed loaders landing in
# ADR 0002 PR 3 (zod/pydantic). Today brain's crawlers still read
# comad.config.yaml directly; the generated files are additive and safe.
generate_brain_configs() {
  local BRAIN_DIR="$ROOT_DIR/brain/config"
  local SOURCES_FILE="$BRAIN_DIR/sources.yaml"
  local KEYWORDS_FILE="$BRAIN_DIR/keywords.json"
  local RUNTIME_FILE="$BRAIN_DIR/runtime.yaml"

  if [ "$DRY_RUN" = "1" ]; then
    dim "    would regenerate: $SOURCES_FILE"
    dim "    would regenerate: $KEYWORDS_FILE"
    dim "    would regenerate: $RUNTIME_FILE"
    return 0
  fi

  mkdir -p "$BRAIN_DIR"

  {
    echo "# brain/config/sources.yaml"
    echo "# Auto-generated from comad.config.yaml (section: sources)."
    echo "# Regenerate with: ./scripts/apply-config.sh"
    echo "# Owner (ADR 0002): brain"
    echo ""
    yq '{"sources": .sources}' "$CONFIG"
  } > "$SOURCES_FILE"
  info "brain/config/sources.yaml"

  # keywords.json — flat deduped list across high/medium/low for crawler scoring.
  yq -o=json '
    [
      (.interests.high   // [])[] | .keywords[]?,
      (.interests.medium // [])[] | .keywords[]?,
      (.interests.low    // [])[] | .keywords[]?
    ] | unique
  ' "$CONFIG" > "$KEYWORDS_FILE"
  info "brain/config/keywords.json"

  {
    echo "# brain/config/runtime.yaml"
    echo "# Auto-generated from comad.config.yaml (section: brain)."
    echo "# Regenerate with: ./scripts/apply-config.sh"
    echo "# Owner (ADR 0002): brain"
    echo ""
    if [ "$(yq '.brain // "" | length' "$CONFIG")" != "0" ]; then
      yq '.brain' "$CONFIG"
    else
      echo "{}"
    fi
  } > "$RUNTIME_FILE"
  info "brain/config/runtime.yaml"
}

# ─── Section: eye → eye/config/overrides.yaml ────────────────────────────────
#
# Per ADR 0002 the `eye.*` section carries overrides that layer on top of the
# module-owned defaults in eye/config/settings.yaml. PR 3 will wire the
# pydantic loader to merge these; for now we emit the file so humans and CI
# can diff the effective override set.
generate_eye_configs() {
  local EYE_DIR="$ROOT_DIR/eye/config"
  local OVERRIDES_FILE="$EYE_DIR/overrides.yaml"

  if [ "$DRY_RUN" = "1" ]; then
    dim "    would regenerate: $OVERRIDES_FILE"
    return 0
  fi

  mkdir -p "$EYE_DIR"

  {
    echo "# eye/config/overrides.yaml"
    echo "# Auto-generated from comad.config.yaml (section: eye)."
    echo "# Regenerate with: ./scripts/apply-config.sh"
    echo "# Owner (ADR 0002): eye. Merged over eye/config/settings.yaml by the"
    echo "# pydantic loader (ADR 0002 PR 3)."
    echo ""
    if [ "$(yq '.eye // "" | length' "$CONFIG")" != "0" ]; then
      yq '.eye' "$CONFIG"
    else
      echo "{}"
    fi
  } > "$OVERRIDES_FILE"
  info "eye/config/overrides.yaml"
}

# ─── Dispatch ────────────────────────────────────────────────────────────────
generate_ear_configs
generate_brain_configs
generate_eye_configs

echo ""
info "apply-config complete"
dim "  Brain: sources.yaml, keywords.json, runtime.yaml regenerated."
dim "  Eye: overrides.yaml regenerated (merged over eye/config/settings.yaml)."
dim "  photo, sleep, voice are domain-agnostic (no generation needed)."

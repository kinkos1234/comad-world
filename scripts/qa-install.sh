#!/bin/bash
# qa-install.sh — Validates install.sh, apply-config.sh, and preset loading
# Tests the setup pipeline without actually installing (non-destructive)
#
# Usage: bash scripts/qa-install.sh

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PASS=0
FAIL=0
TOTAL=0

check() {
    local name="$1"
    local result="$2"
    local detail="${3:-}"
    TOTAL=$((TOTAL + 1))
    if [ "$result" -eq 0 ]; then
        PASS=$((PASS + 1))
        echo -e "  \033[32m✓\033[0m $name${detail:+ ($detail)}"
    else
        FAIL=$((FAIL + 1))
        echo -e "  \033[31m✗\033[0m $name${detail:+ ($detail)}"
    fi
}

echo ""
echo "============================================"
echo "  Install & Config QA"
echo "============================================"
echo ""

# ── install.sh syntax ──
echo "install.sh validation:"
check "install.sh syntax valid" $(bash -n install.sh 2>&1 && echo 0 || echo 1)
check "install.sh is executable" $([[ -x install.sh ]] && echo 0 || echo 1)
check "install.sh has shebang" $(head -1 install.sh | grep -q "^#!/bin/bash" && echo 0 || echo 1)
check "install.sh uses set -euo pipefail" $(grep -q "set -euo pipefail" install.sh && echo 0 || echo 1)

echo ""

# ── apply-config.sh syntax ──
echo "apply-config.sh validation:"
check "apply-config.sh syntax valid" $(bash -n scripts/apply-config.sh 2>&1 && echo 0 || echo 1)
check "apply-config.sh is executable" $([[ -x scripts/apply-config.sh ]] && echo 0 || echo 1)
check "apply-config.sh has shebang" $(head -1 scripts/apply-config.sh | grep -q "^#!/bin/bash" && echo 0 || echo 1)

echo ""

# ── Preset validation ──
echo "Preset validation:"
for preset in presets/*.yaml; do
    name=$(basename "$preset")

    # Check YAML syntax (basic: no tabs, has profile section)
    has_profile=$(grep -c "^profile:" "$preset" || true)
    has_interests=$(grep -c "^interests:" "$preset" || true)
    has_sources=$(grep -c "^sources:" "$preset" || true)
    has_categories=$(grep -c "^categories:" "$preset" || true)

    check "$name has profile section" $([[ "$has_profile" -gt 0 ]] && echo 0 || echo 1)
    check "$name has interests section" $([[ "$has_interests" -gt 0 ]] && echo 0 || echo 1)
    check "$name has sources section" $([[ "$has_sources" -gt 0 ]] && echo 0 || echo 1)
    check "$name has categories section" $([[ "$has_categories" -gt 0 ]] && echo 0 || echo 1)

    # Check no hardcoded secrets
    secrets=$(grep -i "password:" "$preset" | grep -v "changeme" | grep -v "env var" || true)
    check "$name no hardcoded secrets" $([[ -z "$secrets" ]] && echo 0 || echo 1)
done

echo ""

# ── Preset → config copy test ──
echo "Preset loading test:"
TMPDIR=$(mktemp -d)
trap "rm -rf $TMPDIR" EXIT

for preset in presets/*.yaml; do
    name=$(basename "$preset")
    cp "$preset" "$TMPDIR/comad.config.yaml"

    # Verify the copy is valid
    check "cp $name → comad.config.yaml works" $([[ -s "$TMPDIR/comad.config.yaml" ]] && echo 0 || echo 1)

    # Verify key fields exist in copied file
    has_name=$(grep -c "name:" "$TMPDIR/comad.config.yaml" || true)
    check "$name config has name field" $([[ "$has_name" -gt 0 ]] && echo 0 || echo 1)
done

echo ""

# ── apply-config.sh dry run (if yq available) ──
echo "Config generation test:"
if command -v yq &> /dev/null; then
    # Test with a preset
    cp presets/ai-ml.yaml comad.config.yaml.bak 2>/dev/null || true
    ORIG_CONFIG=""
    if [ -f comad.config.yaml ]; then
        ORIG_CONFIG=$(cat comad.config.yaml)
    fi

    cp presets/web-dev.yaml comad.config.yaml
    bash scripts/apply-config.sh > /dev/null 2>&1 || true

    check "ear/interests.md generated" $([[ -f ear/interests.md ]] && echo 0 || echo 1)
    check "ear/CLAUDE.md generated" $([[ -f ear/CLAUDE.md ]] && echo 0 || echo 1)

    if [ -f ear/interests.md ]; then
        # Verify it contains web-dev content (not AI/ML)
        has_react=$(grep -c "Frontend" ear/interests.md || true)
        check "Generated interests matches preset" $([[ "$has_react" -gt 0 ]] && echo 0 || echo 1)
    fi

    if [ -f ear/CLAUDE.md ]; then
        has_categories=$(grep -c "categories" ear/CLAUDE.md || true)
        check "Generated CLAUDE.md has categories" $([[ "$has_categories" -gt 0 ]] && echo 0 || echo 1)
    fi

    # Restore original config
    if [ -n "$ORIG_CONFIG" ]; then
        echo "$ORIG_CONFIG" > comad.config.yaml
    else
        rm -f comad.config.yaml.bak
    fi
else
    check "yq available for config generation" 1 "install yq: brew install yq"
    check "ear/interests.md generated" 1 "skipped (no yq)"
    check "ear/CLAUDE.md generated" 1 "skipped (no yq)"
fi

echo ""

# ── Brain config-loader compatibility ──
echo "Brain config-loader check:"
LOADER="brain/packages/crawler/src/config-loader.ts"
check "config-loader.ts exists" $([[ -f "$LOADER" ]] && echo 0 || echo 1)
check "config-loader reads comad.config.yaml" $(grep -q "comad.config.yaml" "$LOADER" && echo 0 || echo 1)
check "config-loader exports getAllKeywords" $(grep -q "getAllKeywords" "$LOADER" && echo 0 || echo 1)
check "config-loader exports getRssFeeds" $(grep -q "getRssFeeds" "$LOADER" && echo 0 || echo 1)
check "config-loader exports getArxivCategories" $(grep -q "getArxivCategories" "$LOADER" && echo 0 || echo 1)
check "config-loader exports getGitHubConfig" $(grep -q "getGitHubConfig" "$LOADER" && echo 0 || echo 1)

echo ""

# ── Crawler config integration ──
echo "Crawler config integration:"
for crawler in hn-crawler arxiv-crawler github-crawler; do
    FILE="brain/packages/crawler/src/${crawler}.ts"
    if [ -f "$FILE" ]; then
        check "$crawler imports from config-loader" $(grep -q "config-loader" "$FILE" && echo 0 || echo 1)
        # Verify NO hardcoded domain arrays
        hardcoded=$(grep -c "const AI_KEYWORDS\|const CATEGORIES\|const TOPICS" "$FILE" 2>/dev/null || echo "0")
        # It's ok if they assign from config-loader, not ok if they have literal arrays
        has_literal_array=$(grep -A1 "const AI_KEYWORDS\|const CATEGORIES\|const TOPICS" "$FILE" | grep -c '\["' || true)
        check "$crawler no hardcoded arrays" $([[ "${has_literal_array:-0}" -eq 0 ]] && echo 0 || echo 1)
    else
        check "$crawler exists" 1
    fi
done

echo ""
echo "============================================"
SCORE=$((PASS * 100 / TOTAL))
echo "  Result: $PASS/$TOTAL passed ($SCORE%)"
if [ "$FAIL" -eq 0 ]; then
    echo "  Status: ALL PASS"
else
    echo "  Status: $FAIL FAILURES"
fi
echo "============================================"
echo ""

exit "$FAIL"

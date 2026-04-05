#!/bin/bash
# qa-repo.sh — Repo polish QA checker
# Verifies GitHub Community Standards and star-readiness infrastructure.
# Target: ALL checks pass (0 failures)
#
# Usage: bash scripts/qa-repo.sh

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PASS=0
FAIL=0
TOTAL=0

check() {
    local name="$1"
    local result="$2"  # 0=pass, 1=fail
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
echo "  Repo Polish QA"
echo "============================================"
echo ""

# ── Essential Files ──
echo "Essential files:"
check "README.md exists" $([[ -f README.md ]] && echo 0 || echo 1)
check "LICENSE exists" $([[ -f LICENSE ]] && echo 0 || echo 1)
check "CONTRIBUTING.md exists" $([[ -f CONTRIBUTING.md ]] && echo 0 || echo 1)
check ".gitignore exists" $([[ -f .gitignore ]] && echo 0 || echo 1)
check "install.sh exists + executable" $([[ -x install.sh ]] && echo 0 || echo 1)

echo ""
echo "Community standards:"
check "CODE_OF_CONDUCT.md exists" $([[ -f CODE_OF_CONDUCT.md ]] && echo 0 || echo 1)
check "SECURITY.md exists" $([[ -f SECURITY.md ]] && echo 0 || echo 1)

echo ""
echo "GitHub templates:"
check "Issue template exists" $([[ -f .github/ISSUE_TEMPLATE/bug_report.md || -f .github/ISSUE_TEMPLATE/bug_report.yml ]] && echo 0 || echo 1)
check "Feature request template exists" $([[ -f .github/ISSUE_TEMPLATE/feature_request.md || -f .github/ISSUE_TEMPLATE/feature_request.yml ]] && echo 0 || echo 1)
check "PR template exists" $([[ -f .github/PULL_REQUEST_TEMPLATE.md || -f .github/pull_request_template.md ]] && echo 0 || echo 1)

echo ""
echo "CI/CD:"
check "GitHub Actions workflow exists" $([[ -d .github/workflows && $(ls .github/workflows/*.yml 2>/dev/null | wc -l) -gt 0 ]] && echo 0 || echo 1)

echo ""
echo "Module READMEs:"
for mod in brain ear eye photo sleep voice; do
    check "$mod/README.md exists" $([[ -f "$mod/README.md" ]] && echo 0 || echo 1)
done

echo ""
echo "Configuration:"
check "comad.config.yaml exists" $([[ -f comad.config.yaml ]] && echo 0 || echo 1)
check "At least 2 presets" $([[ $(ls presets/*.yaml 2>/dev/null | wc -l) -ge 2 ]] && echo 0 || echo 1) "$(ls presets/*.yaml 2>/dev/null | wc -l | tr -d ' ') presets"
check "apply-config.sh exists + executable" $([[ -x scripts/apply-config.sh ]] && echo 0 || echo 1)

echo ""
echo "Security:"
# Check for hardcoded secrets
SECRETS=$(grep -rn "password.*=.*[a-zA-Z0-9]" --include="*.ts" --include="*.py" --include="*.yaml" --include="*.yml" --include="*.json" . 2>/dev/null | grep -v "changeme" | grep -v ".example" | grep -v "NEO4J_PASSWORD" | grep -v "env var" | grep -v "qa-repo" | grep -v "node_modules" || true)
check "No hardcoded secrets" $([[ -z "$SECRETS" ]] && echo 0 || echo 1)

# Check for .env files (should be gitignored)
check ".env in .gitignore" $(grep -q "^\.env$" .gitignore 2>/dev/null && echo 0 || echo 1)

# Check no .env files committed
ENV_FILES=$(find . -name ".env" -not -path "*/node_modules/*" -not -name "*.example" 2>/dev/null || true)
check "No .env files present" $([[ -z "$ENV_FILES" ]] && echo 0 || echo 1)

echo ""
echo "Cleanliness:"
# No empty directories (except archive/digests which are intentional)
EMPTY_DIRS=$(find . -type d -empty -not -path "*/.git/*" -not -path "*/node_modules/*" 2>/dev/null || true)
check "No empty directories" $([[ -z "$EMPTY_DIRS" ]] && echo 0 || echo 1) "${EMPTY_DIRS:+found: $EMPTY_DIRS}"

# No node_modules committed
check "No node_modules" $([[ ! -d node_modules && ! -d brain/node_modules ]] && echo 0 || echo 1)

# No .DS_Store
DS_STORE=$(find . -name ".DS_Store" 2>/dev/null || true)
check "No .DS_Store files" $([[ -z "$DS_STORE" ]] && echo 0 || echo 1)

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

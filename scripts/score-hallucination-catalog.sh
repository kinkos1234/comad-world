#!/usr/bin/env bash
# score-hallucination-catalog.sh — House precondition gate (Issue #2).
#
# Reads docs/planning/hallucination-catalog.md and scores the rows based
# on the "Would T+C catch?" column. Gate: score >= 0.80 before Issue #2
# PR 1 can land.
set -euo pipefail

. "$(dirname "${BASH_SOURCE[0]}")/lib/common.sh"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CATALOG="$ROOT_DIR/docs/planning/hallucination-catalog.md"
[ -f "$CATALOG" ] || die "catalog not found: $CATALOG"

step "Scoring $CATALOG"

PY=""
for c in python3 /opt/anaconda3/bin/python3 /usr/bin/python3; do
  command -v "$c" >/dev/null 2>&1 && PY="$c" && break
done
[ -n "$PY" ] || die "no python3"

CATALOG="$CATALOG" "$PY" - <<'PY'
import os, re, sys

path = os.environ["CATALOG"]
with open(path) as f:
    text = f.read()

# Table rows look like:  | 1 | 2026-04-01 | ... | Yes | ... |
# Skip header/separator and the schema description rows.
row_re = re.compile(r"^\|\s*(\d+)\s*\|(.+?)\|\s*$", re.MULTILINE)
caught_re = re.compile(r"^\s*(yes|y|partial|p|no|n)?\s*$", re.IGNORECASE)

rows = []
for m in row_re.finditer(text):
    cells = [c.strip() for c in m.group(2).split("|")]
    # Expect at least: date, node, source, symptom, root_cause, caught, notes
    if len(cells) < 7:
        continue
    caught = cells[5]
    rows.append((int(m.group(1)), caught))

filled = [r for r in rows if r[1]]
if not filled:
    print("  no rows filled yet — template ready, catalog empty")
    print("  status: PENDING (need >=20 filled rows before scoring)")
    sys.exit(0)

score = 0.0
caught_n = partial_n = missed_n = 0
for _, c in filled:
    cl = c.lower().strip()
    if cl in ("yes", "y"):
        score += 1.0
        caught_n += 1
    elif cl in ("partial", "p"):
        score += 0.5
        partial_n += 1
    elif cl in ("no", "n"):
        missed_n += 1

print(f"  filled rows:   {len(filled)}")
print(f"  caught:        {caught_n}")
print(f"  partial:       {partial_n}")
print(f"  missed:        {missed_n}")
denom = max(len(filled), 20)
print(f"  score:         {score:.2f} / {denom}  = {score/denom:.2%}")
if len(filled) < 20:
    print(f"  status: PENDING ({20 - len(filled)} more rows needed)")
elif score / denom >= 0.80:
    print("  status: PASS — Issue #2 PR 1 gate open")
else:
    print("  status: FAIL — score below 80% threshold, design needs revision")
PY

info "done"

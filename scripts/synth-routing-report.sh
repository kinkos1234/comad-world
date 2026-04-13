#!/usr/bin/env bash
# synth-routing-report.sh — summarize brain/data/logs/synth-routing.jsonl
# produced by ADR 0003 routing. Used to tune the classifier from real
# data before flipping SYNTH_ROUTING=on.
#
# Usage:
#   scripts/synth-routing-report.sh                    # last 7 days
#   scripts/synth-routing-report.sh --since 2026-04-07
#   scripts/synth-routing-report.sh --log /path/to/synth-routing.jsonl
set -euo pipefail

. "$(dirname "${BASH_SOURCE[0]}")/lib/common.sh"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_PATH="$ROOT_DIR/brain/data/logs/synth-routing.jsonl"
SINCE=""

while [ $# -gt 0 ]; do
  case "$1" in
    --log)   LOG_PATH="$2"; shift 2 ;;
    --since) SINCE="$2"; shift 2 ;;
    -h|--help) sed -n '2,8p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) die "unknown arg: $1" ;;
  esac
done

[ -f "$LOG_PATH" ] || die "log not found: $LOG_PATH (is SYNTH_ROUTING enabled?)"

PY=""
for candidate in python3 /opt/anaconda3/bin/python3 /usr/bin/python3; do
  command -v "$candidate" >/dev/null 2>&1 && PY="$candidate" && break
done
[ -n "$PY" ] || die "no python3 found"

step "Synth routing report — $LOG_PATH"
LOG_PATH="$LOG_PATH" SINCE="$SINCE" "$PY" - <<'PY'
import json, os, sys
from datetime import datetime, timedelta, timezone
from statistics import median

path = os.environ["LOG_PATH"]
since_arg = os.environ.get("SINCE", "").strip()
if since_arg:
    since_ts = int(datetime.fromisoformat(since_arg).replace(tzinfo=timezone.utc).timestamp() * 1000)
else:
    since_ts = int((datetime.now(timezone.utc) - timedelta(days=7)).timestamp() * 1000)

rows = []
with open(path) as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        if r.get("ts", 0) >= since_ts:
            rows.append(r)

if not rows:
    print("  no records in window")
    sys.exit(0)

by_tier = {"easy": [], "hard": []}
reason_counts = {}
for r in rows:
    by_tier.setdefault(r.get("tier", "unknown"), []).append(r)
    for rsn in r.get("reasons", []):
        reason_counts[rsn] = reason_counts.get(rsn, 0) + 1

def pct(n, d): return f"{(100*n/d):.1f}%" if d else "0%"
def p(xs, q):
    if not xs: return 0
    xs = sorted(xs)
    idx = min(int(len(xs) * q), len(xs) - 1)
    return xs[idx]

total = len(rows)
print(f"  window:        {total} requests")
for tier in ("easy", "hard"):
    tr = by_tier.get(tier, [])
    if not tr:
        print(f"  {tier:6}        0 ({pct(0,total)})")
        continue
    lats = [r["latency_ms"] for r in tr if "latency_ms" in r]
    print(f"  {tier:6}        {len(tr):>5}  ({pct(len(tr), total)})  "
          f"p50={p(lats, 0.5)}ms  p95={p(lats, 0.95)}ms  median_ans={int(median([r['answer_len'] for r in tr])) if tr else 0}ch")

print("\n  top classifier reasons:")
for rsn, n in sorted(reason_counts.items(), key=lambda x: -x[1])[:8]:
    print(f"    {n:>5}  {rsn}")
PY

info "done"

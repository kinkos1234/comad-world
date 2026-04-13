#!/usr/bin/env bash
# validate-config.sh — validate comad.config.yaml (and presets) against the
# canonical JSON Schema. Used by `make validate-config` and by CI.
#
# Dependencies:
#   - python3 with PyYAML (for yaml→json conversion)
#   - npx (for ajv-cli, auto-fetched on first run)
#
set -euo pipefail

# shellcheck source=scripts/lib/common.sh
. "$(dirname "${BASH_SOURCE[0]}")/lib/common.sh"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

SCHEMA="schema/comad.config.schema.json"
[ -f "$SCHEMA" ] || die "schema missing: $SCHEMA"

# Determine which python has PyYAML.
PY=""
for candidate in python3 /opt/anaconda3/bin/python3 /usr/bin/python3; do
  if command -v "$candidate" >/dev/null 2>&1; then
    if "$candidate" -c "import yaml" 2>/dev/null; then
      PY="$candidate"
      break
    fi
  fi
done
if [ -z "$PY" ]; then
  die "no python3 with PyYAML found. Install: pip install pyyaml"
fi

TARGETS=("comad.config.yaml")
if [ "${VALIDATE_PRESETS:-1}" = "1" ]; then
  shopt -s nullglob
  TARGETS+=(presets/*.yaml)
fi

fail=0
tmp="$(mktemp).json"
trap 'rm -f "$tmp"' EXIT

for t in "${TARGETS[@]}"; do
  if [ ! -f "$t" ]; then
    warn "missing: $t (skipped)"
    continue
  fi
  if ! COMAD_IN="$t" COMAD_OUT="$tmp" "$PY" -c '
import os, yaml, json
inp = os.environ["COMAD_IN"]
out = os.environ["COMAD_OUT"]
json.dump(yaml.safe_load(open(inp)), open(out, "w"))
' 2>/dev/null; then
    fail "$t: YAML parse error"
    fail=1
    continue
  fi
  out=$(npx --yes ajv-cli@5 validate -s "$SCHEMA" -d "$tmp" --spec=draft2020 --errors=line 2>&1 || true)
  if echo "$out" | tail -1 | grep -q 'valid$'; then
    info "$t"
  else
    fail "$t"
    echo "$out" | tail -5 | sed 's/^/    /'
    fail=1
  fi
done

exit "$fail"

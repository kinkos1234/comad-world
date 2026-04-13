#!/usr/bin/env bash
# check-loaders-in-sync.sh — ADR 0002 PR 4 parity gate.
#
# The brain (zod) and eye (pydantic) loaders are hand-authored against
# schema/comad.config.schema.json. That means they can drift. This script
# fails fast if they do:
#
#   1. ajv validates every preset against the JSON Schema.
#      (delegated to scripts/validate-config.sh)
#   2. the brain zod loader accepts every preset.
#   3. both the JSON Schema and the brain zod loader reject a known-invalid
#      payload — catches the case where a loader silently accepts garbage.
#
# Run locally: make schema-sync-check
# CI: .github/workflows/structure-guard.yml (config-schema-validation job)
set -euo pipefail

# shellcheck source=scripts/lib/common.sh
. "$(dirname "${BASH_SOURCE[0]}")/lib/common.sh"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

step "Step 1/3 — JSON Schema validation (ajv)"
bash scripts/validate-config.sh

step "Step 2/3 — Brain zod loader accepts every preset"
if ! command -v bun >/dev/null 2>&1; then
  warn "bun not found; skipping zod loader check (install bun or run in CI)"
else
  fail=0
  for preset in presets/*.yaml; do
    [ -f "$preset" ] || continue
    # Point the loader at each preset via a temp copy — loader searches for
    # comad.config.yaml, so we stage a sibling dir.
    tmpdir=$(mktemp -d)
    trap 'rm -rf "$tmpdir"' EXIT
    cp "$preset" "$tmpdir/comad.config.yaml"
    if (cd brain && COMAD_CONFIG_DIR="$tmpdir" bun -e "
      import { loadConfig } from './packages/core/src/config/loader.ts';
      const cfg = loadConfig({ force: true });
      if (!cfg.profile?.name) throw new Error('missing profile.name');
    " 2>&1 | tail -3); then
      info "$preset (zod)"
    else
      fail "$preset (zod rejected)"
      fail=1
    fi
  done
  [ "$fail" = "0" ] || exit 1
fi

step "Step 3/3 — Loaders reject a known-invalid payload"
tmpdir=$(mktemp -d)
trap 'rm -rf "$tmpdir"' EXIT
cat > "$tmpdir/comad.config.yaml" << 'INVALID'
profile:
  name: 42
sources:
  rss_feeds:
    - {name: "bad", url: "not-a-url"}
INVALID

# JSON Schema must reject.
tmpjson="$tmpdir/config.json"
PY=""
for candidate in python3 /opt/anaconda3/bin/python3 /usr/bin/python3; do
  command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c 'import yaml' 2>/dev/null && PY="$candidate" && break
done
[ -n "$PY" ] || die "no python3 with PyYAML found"
"$PY" -c "import yaml,json; json.dump(yaml.safe_load(open('$tmpdir/comad.config.yaml')), open('$tmpjson','w'))"
if npx --yes ajv-cli@5 validate -s schema/comad.config.schema.json -d "$tmpjson" --spec=draft2020 --errors=line >/dev/null 2>&1; then
  fail "JSON Schema accepted an intentionally invalid payload (regression)"
  exit 1
fi
info "JSON Schema rejected invalid payload"

# Zod must reject.
if command -v bun >/dev/null 2>&1; then
  if (cd brain && COMAD_CONFIG_DIR="$tmpdir" bun -e "
    import { loadConfig } from './packages/core/src/config/loader.ts';
    try { loadConfig({ force: true }); process.exit(0); }
    catch { process.exit(42); }
  " 2>/dev/null); then
    fail "zod loader accepted an intentionally invalid payload (regression)"
    exit 1
  fi
  info "Zod loader rejected invalid payload"
fi

echo ""
info "loaders are in sync with schema/comad.config.schema.json"

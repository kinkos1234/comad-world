# Comad World — one-line entry points for the most common workflows.
# Keep this file small: everything non-trivial lives in scripts/.

SHELL := /bin/bash
.DEFAULT_GOAL := help

COMAD ?= ./scripts/comad

# ─── Help ───
.PHONY: help
help:
	@echo ""
	@echo "Comad World — common tasks"
	@echo ""
	@echo "  make status           show VERSION + module SHAs"
	@echo "  make upgrade          upgrade main + modules + deps + agents"
	@echo "  make upgrade-check    dry-run upgrade (no writes)"
	@echo "  make backups          list upgrade snapshots"
	@echo "  make rollback TS=...  restore a snapshot"
	@echo "  make lock             regenerate comad.lock"
	@echo ""
	@echo "  make test             run the full test suite (brain + eye)"
	@echo "  make test-brain       brain TypeScript tests only"
	@echo "  make test-eye         eye Python tests only"
	@echo ""
	@echo "  make clean            dry-run: what runtime artifacts would be removed"
	@echo "  make clean-apply      actually remove caches, logs, build artifacts"
	@echo "  make clean-deep       also nuke node_modules / .venv (slow)"
	@echo ""
	@echo "  make render           regenerate path-aware templates (e.g. sleep/.mcp.json)"
	@echo ""
	@echo "  make validate-config  JSON Schema validation"
	@echo "  make schema-sync-check verify zod/pydantic loaders stay in sync"
	@echo ""

# ─── comad wrapper passthroughs ───
.PHONY: status upgrade upgrade-check backups rollback lock
status:
	@$(COMAD) status
upgrade:
	@$(COMAD) upgrade
upgrade-check:
	@$(COMAD) upgrade --dry-run
backups:
	@$(COMAD) backups
rollback:
	@test -n "$(TS)" || { echo "Usage: make rollback TS=<timestamp>  (see: make backups)"; exit 1; }
	@$(COMAD) rollback $(TS)
lock:
	@$(COMAD) lock

# ─── Test ───
.PHONY: test test-brain test-eye
test: test-brain test-eye

test-brain:
	@if [ -d brain ]; then \
		echo ">> brain: bun test"; \
		cd brain && bun test; \
	else echo "brain/ missing — skipped"; fi

test-eye:
	@if [ -d eye ]; then \
		echo ">> eye: pytest"; \
		cd eye && python3 -m pytest tests/ -q; \
	else echo "eye/ missing — skipped"; fi

# ─── Clean ───
.PHONY: clean clean-apply clean-deep
clean:
	@bash scripts/clean-runtime.sh
clean-apply:
	@bash scripts/clean-runtime.sh --apply
clean-deep:
	@bash scripts/clean-runtime.sh --deep --apply

# ─── Render templates ───
.PHONY: render
render:
	@bash scripts/render-templates.sh

# ─── Config validation ───
.PHONY: validate-config schema-sync-check
validate-config:
	@bash scripts/validate-config.sh
schema-sync-check:
	@bash scripts/check-loaders-in-sync.sh

# ─── Phase C — synth routing (ADR 0003) ───
.PHONY: synth-routing-report
synth-routing-report:
	@bash scripts/synth-routing-report.sh

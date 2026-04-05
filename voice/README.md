# Voice — Workflow Automation Harness

"Just say what you want. AI does the rest."

Claude Code harness with auto-triggered workflows. **Domain-agnostic** — works with any project.

## What It Does

| Trigger | What Happens |
|---------|-------------|
| First session in a project | Auto-explores, shows welcome + available commands |
| "검토해봐" / "review this" | Full codebase diagnosis → 3-5 improvement cards → pick and go |
| "풀사이클" / "full cycle" | Research → Decompose → Experiment → Integrate → Polish → Deliver |
| Multi-subtask detected | Auto-classifies dependencies, parallelizes independent work |
| "광택" / "repo polish" | README, badges, LICENSE, CI, templates — GitHub-ready |
| "저장해줘" / "save session" | Session summary + handoff notes for next time |
| "QA해줘" / "qa" / "테스트해봐" | Browser-based QA: navigation, forms, responsive, console errors |

## Before vs After

**Before:** "improve this" → Claude fixes one thing, done.

**After:** "검토해봐" → Claude diagnoses everything, shows rated cards, you pick, it runs autonomous experiments.

## Install

```bash
cd voice && ./install.sh
```

This appends workflow triggers to `~/.claude/CLAUDE.md`.

## Review Army

Multi-specialist code review with adaptive gating. See [review-army.md](review-army.md) for details.

5 parallel reviewers (security, performance, correctness, maintainability, compatibility) with auto-skip for quiet specialists and cross-review dedup.

## Requirements

- Claude Code (Claude Max recommended)
- Optional: Codex CLI + tmux (for parallel work)

## Uninstall

The installer uses `<!-- COMAD-VOICE:START -->` / `<!-- COMAD-VOICE:END -->` markers. Remove that block from `~/.claude/CLAUDE.md`.

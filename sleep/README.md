# Sleep — Memory Consolidation Agent

A sleep cycle for your Claude Code memory. Consolidates, deduplicates, and prunes auto-memory files across all projects.

**Domain-agnostic** — works with any Claude Code project.

## Why?

Claude Code's auto-memory grows every session. Duplicates pile up, stale references linger, session-specific debris accumulates. Sleep cleans it all with a single word.

```
you: dream
claude: ComadSleep — Scanned 3 projects, 5 files.
        Merged 4 duplicates, pruned 2 stale refs.
```

## How It Works

```
Phase 1: Scan              Phase 2: Act
┌─────────────────┐       ┌───────────────────┐
│ Orient + Gather │──────▶│ Backup (verified)  │
│ + Classify      │       │ Consolidate + Prune│
└─────────────────┘       └───────────────────┘
```

**Fast path**: if nothing changed since last run, returns immediately.

## What It Does

| Action | Example |
|--------|---------|
| Merge duplicates | Same fact in two files → keep one |
| Prune stale refs | Dead link to deleted file → remove |
| Clean transient notes | "Currently working on..." from 2 weeks ago → remove |
| Cross-project scan | Generic notes in project-specific memory → flag |

## What It Never Does

- Modify CLAUDE.md files
- Delete anything uncertain (tags `[REVIEW NEEDED]` instead)
- Proceed without verified backup

## Install

```bash
cp sleep/comad-sleep.md ~/.claude/agents/
```

## Trigger Words

- `dream`
- `메모리 정리` / `정리해줘`
- Dry-run: `dream dry-run` / `미리보기`

## Safety

1. Timestamped backup before changes
2. Backup verification (file count + bytes)
3. Dual-lock protocol (own + OMC)
4. Uncertain items tagged, not deleted

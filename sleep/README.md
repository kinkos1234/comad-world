# ComadSleep

**A sleep cycle for your Claude Code memory.**

ComadSleep is a Claude Code subagent that consolidates, deduplicates, and prunes your auto memory files — like how sleep consolidates human memory.

Claude Code's [Auto Memory](https://docs.anthropic.com/en/docs/claude-code/memory) grows with every session. Over time, notes pile up: duplicates, stale references, session-specific debris. ComadSleep cleans it all up with a single word.

```
you: dream
claude: ComadSleep — 2026-03-24: Scanned 3 projects, 5 files.
        Merged 4 duplicates, pruned 2 stale refs, backed up to ~/.claude/memory-backup-...
```

## Why not just Auto-dream?

Claude Code has an unreleased built-in feature called Auto-dream (`autoDreamEnabled`) that also consolidates memory. So why ComadSleep?

| | Auto-dream | ComadSleep |
|---|---|---|
| **Control** | Runs when Claude decides | Runs when YOU decide |
| **Backup** | No verified backup | Timestamped backup, verified before changes |
| **Report** | Silent | Full report of what changed and why |
| **Scope** | Current project only | All projects at once |
| **Dry-run** | No preview | Preview changes before applying |
| **Cross-project** | No | Detects generic knowledge in project-specific memory |
| **Lock safety** | Basic | Dual-lock (own + OMC) with stale lock cleanup |

**They complement each other.** Auto-dream handles light daily maintenance. ComadSleep is your weekly deep clean — with receipts.

## How It Works

ComadSleep runs a 2-phase pipeline:

```
Phase 1: Scan          Phase 2: Act
┌─────────────┐       ┌─────────────────┐
│ Orient      │       │ Backup (verified)│
│ + Gather    │──────▶│ Consolidate      │
│ + Classify  │       │ Prune & Index    │
└─────────────┘       └─────────────────┘
        │                       │
   "CLEAN" ──▶ done      Report ──▶ done
```

**Fast path**: If nothing changed since the last run, it returns in one line. No wasted tokens.

### What It Does

| Action | Example |
|--------|---------|
| **Merge duplicates** | Same fact in MEMORY.md AND experiments.md → keep one |
| **Prune stale refs** | Link to `architecture.md` that was never created → remove |
| **Clean transient notes** | "Currently working on..." from 2 weeks ago → remove |
| **Resolve [REVIEW NEEDED]** | Tagged item from last run, now resolved → untag |
| **Cross-project scan** | Generic tool notes in project-specific memory → flag |
| **Remove artifacts** | Stale `.consolidate-lock` files, temp files → clean |

### What It Never Does

- Modify your `CLAUDE.md` files (instructions are sacred)
- Delete anything it's unsure about (tags `[REVIEW NEEDED]` instead)
- Proceed without a verified backup
- Touch `.omc/` directories or project source code

## Install

**One-line install:**

```bash
curl -fsSL https://raw.githubusercontent.com/kinkos1234/comad-sleep/main/install.sh | bash
```

**Manual install:**

```bash
cp comad-sleep.md ~/.claude/agents/
```

That's it. Restart your Claude Code session and it's ready.

### Optional: Auto-trigger on session end

```bash
cp hooks/comad-sleep-hook.json ~/.claude/hooks/
```

This runs ComadSleep automatically when a session ends with 150+ lines of memory.

## Usage

### Manual trigger

Just say any of these in Claude Code:

```
dream
메모리 정리
정리해줘
```

### Dry-run (preview without changes)

```
dream dry-run
미리보기
```

### Discord bot

Works with Claude Code Discord bots (ccc/ccd). Send `dream` in any connected channel.

## Safety

ComadSleep is paranoid about data loss:

1. **Backup first** — Creates timestamped backup before any changes (`~/.claude/memory-backup-{timestamp}/`)
2. **Verify backup** — Compares file count and bytes. Aborts if mismatch.
3. **Lock protocol** — Checks both its own lock AND OMC's `.consolidate-lock` to prevent concurrent writes
4. **Never guesses** — Uncertain items get `[REVIEW NEEDED]` tags, not deleted
5. **State tracking** — Remembers last run state to skip unchanged projects

## Configuration

ComadSleep stores its state at:

```
~/.claude/.comad-sleep-state.json    # Run history, project hashes
~/.claude/.comad-sleep.lock          # Concurrency lock (auto-managed)
```

### Coexistence with Auto-dream

If you have `autoDreamEnabled: true` in your Claude Code settings, ComadSleep complements it:

- **Auto-dream** = lightweight, automatic, background
- **ComadSleep** = thorough, on-demand, with backup + report

They don't conflict. ComadSleep never touches `autoDreamEnabled`.

## Example: Before & After

**Before** (60 lines across 2 files — 7 issues):
```
MEMORY.md:
  - Working on user authentication        ← stale (3 weeks old)
  - 이번 세션에서 API 라우트 수정 중       ← transient
  - → See [architecture.md]               ← dead link
  - JWT token expiration not handled
  - JWT token expiry causes logout         ← duplicate
```

**After** (34 lines — 0 issues, -43%):
```
MEMORY.md:
  - Auth: Lucia with Prisma adapter (see experiments.md)
  - JWT token expiration not handled
  - Rate limiting needed (upstash/ratelimit in progress)
```

Full before/after examples in [examples/](examples/).

## Requirements

- Claude Code (any version with custom agents support)
- That's it. No dependencies, no build step, no runtime.

## License

MIT

---

*Inspired by how sleep consolidates human memory — and by Anthropic's unreleased Auto-dream feature.*

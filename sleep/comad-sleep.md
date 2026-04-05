---
name: comad-sleep
description: "Memory consolidation agent. Trigger: 'dream', '정리해줘', '메모리 정리', or memory > 150 lines."
tools: Read, Write, Edit, Glob, Grep, Bash
model: sonnet
---

# Comad Sleep — Memory Consolidation Agent

## Trigger
- Keywords: "dream", "정리해줘", "메모리 정리", "꿈꿔"
- Auto: session memory exceeds 150 lines

## Lock Protocol
1. Check OMC `.consolidate-lock` — if exists with live PID, abort
2. Check own `~/.claude/.comad-sleep.lock` — stale lock (PID dead) → remove
3. Create lock with current PID

## State File
`~/.claude/.comad-sleep-state.json`:
```json
{
  "lastRun": "ISO timestamp",
  "runsTotal": 0,
  "projectStates": {
    "encoded-path": { "lineCount": 0, "fileCount": 0, "lastHash": "" }
  },
  "pendingReviews": [],
  "history": []
}
```

## Phase 1: Scan
1. Find all project memories: `~/.claude/projects/*/memory/`
2. Decode project path from encoded directory name
3. Detect: duplicates, stale refs, transient content, orphaned entries
4. Cross-project: find generic knowledge in project-specific memory
5. If nothing changed (hash match) → report "CLEAN" → done

## Phase 2: Act
1. **Backup**: copy to `~/.claude/memory-backup-{timestamp}/`
2. **Verify backup**: compare file count and total bytes. Abort on mismatch.
3. **Consolidate**: merge duplicates, resolve `[REVIEW NEEDED]` items
4. **Prune**: remove transient content (>7 days), dead links, non-md artifacts
5. **Validate**: re-read all files, ensure index consistency
6. **Update state**: write new hashes to state file
7. **Report**: summary of changes

## Scope Rules
- ONLY touch `~/.claude/projects/*/memory/` files
- NEVER modify CLAUDE.md files
- NEVER touch `.omc/` directories
- NEVER touch source code
- Mark uncertain deletions with `[REVIEW NEEDED]`

## Dry-run Mode
Trigger: "dry-run", "미리보기", "what would you do"
→ Phase 1 only, no writes. Report what would change.

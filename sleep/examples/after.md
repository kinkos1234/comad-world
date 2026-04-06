# Example: After ComadSleep

Same project after running `dream`.

## ~/.claude/projects/my-app/memory/MEMORY.md (19 lines, was 38)

```markdown
# My App Memory

## Project Overview
- Next.js 14 app with Prisma ORM + PostgreSQL
- Deployed on Vercel
- Auth: Lucia with Prisma adapter (see experiments.md)

## Known Issues
- JWT token expiration not handled
- Rate limiting needed for API (upstash/ratelimit in progress)

## Topics
- [experiments.md](experiments.md) — auth approach testing, rate limiting

## User Preferences
- TypeScript strict mode
- pnpm
```

## ~/.claude/projects/my-app/memory/experiments.md (15 lines, was 22)

```markdown
# Experiments

## Experiment 1: Auth with NextAuth
- Tried NextAuth v5 beta, too unstable — reverted

## Experiment 2: Auth with Lucia
- Lucia auth library + Prisma adapter — adopted
- Open issue: JWT token expiration handling

## Experiment 3: Rate Limiting
- Using upstash/ratelimit — in progress
```

## ComadSleep Report

```
ComadSleep Report — 2026-03-24

Scanned: 1 project, 2 files
Backup: ~/.claude/memory-backup-2026-03-24T231500/

Changes:
- [my-app/MEMORY.md]: merged 3 duplicates, removed 3 transient notes,
  removed dead link to architecture.md, updated cross-references
- [my-app/experiments.md]: removed 1 duplicate, removed 1 transient note

Pending Review: none

Next: Consider creating architecture.md when making architectural decisions.
```

## What Changed

| Metric | Before | After | Reduction |
|--------|--------|-------|-----------|
| Total lines | 60 | 34 | -43% |
| Duplicates | 3 | 0 | -100% |
| Dead references | 1 | 0 | -100% |
| Transient notes | 3 | 0 | -100% |
| Orphaned [REVIEW NEEDED] | 1 | 0 | resolved |

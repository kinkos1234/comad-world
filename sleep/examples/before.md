# Example: Before ComadSleep

This is a realistic example of what auto memory looks like after weeks of use.

## ~/.claude/projects/my-app/memory/MEMORY.md (38 lines)

```markdown
# My App Memory

## Project Overview
- Next.js 14 app with Prisma ORM
- PostgreSQL database
- Deployed on Vercel

## Current State
- Working on user authentication
- Currently debugging login flow  ← stale (3 weeks old)
- 이번 세션에서 API 라우트 수정 중  ← transient

## Architecture Decisions
→ See [architecture.md](architecture.md) for details  ← dead link (file never created)

## Known Issues
- JWT token expiration not handled
- JWT token expiry causes logout  ← duplicate of above
- Rate limiting needed for API
- TODO: add rate limiting  ← duplicate of above

## Experiment History
→ See [experiments.md](experiments.md)

## User Preferences
- Prefers TypeScript strict mode
- Uses pnpm

## Notes
- Prisma schema updated to add User model
- User model added with email, name, role fields  ← duplicate
- Remember to run prisma migrate  ← transient/completed task
- [REVIEW NEEDED] Check if middleware.ts handles auth correctly
```

## ~/.claude/projects/my-app/memory/experiments.md (22 lines)

```markdown
# Experiments

## Experiment 1: Auth with NextAuth
- Tried NextAuth v5 beta
- Too unstable, reverted

## Experiment 2: Auth with Lucia
- Lucia auth library works well
- Integrated with Prisma adapter
- JWT token expiration not handled  ← duplicate from MEMORY.md

## Experiment 3: Rate Limiting
- Using upstash/ratelimit
- 이번 세션에서 테스트 중  ← transient
```

## Issues Found (7 total)

1. **2 dead references**: `architecture.md` link points to non-existent file
2. **3 duplicates**: JWT expiration (2x), rate limiting (2x), User model (2x)
3. **3 transient notes**: "Currently debugging...", "이번 세션에서...", "Remember to run..."
4. **1 orphaned review tag**: `[REVIEW NEEDED]` with no resolution date

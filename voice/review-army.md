# Review Army — Multi-Specialist Code Review

Triggered by voice's "검토해봐" workflow or manually via `/review-army`.
Inspired by gstack's adaptive gating pattern, built for comad.

## How It Works

### Specialists (5 reviewers run in parallel)

| Specialist | Focus | Auto-skip threshold |
|-----------|-------|-------------------|
| **security** | Auth, tokens, injection, permissions, trust boundaries | 3 consecutive empty reviews |
| **performance** | N+1 queries, unbounded loops, memory leaks, missing indexes | 3 consecutive empty reviews |
| **correctness** | Logic bugs, race conditions, forgotten enum cases, stale reads | Never skip |
| **maintainability** | Dead code, naming, abstraction level, test coverage gaps | 5 consecutive empty reviews |
| **compatibility** | Breaking API changes, schema migrations, backward compat | 3 consecutive empty reviews |

### Adaptive Gating

Each specialist tracks its hit rate (findings per review). After N consecutive empty reviews, that specialist is temporarily skipped to save time. Reactivated when:
- Files matching its domain are changed (e.g., `auth.*` reactivates security)
- Manual override via `--all-specialists`

Stats stored in `.comad/review-stats.json`:
```json
{
  "security": { "total": 12, "hits": 8, "consecutive_empty": 0 },
  "performance": { "total": 12, "hits": 3, "consecutive_empty": 2 }
}
```

### Cross-Review Dedup

If a finding was previously dismissed by the user and the relevant code hasn't changed, suppress it in future reviews. Tracked in `.comad/review-dismissed.json`.

### Output Format

Each specialist produces findings:
```json
{
  "specialist": "security",
  "severity": "high|medium|low",
  "file": "src/auth.ts",
  "line": 42,
  "finding": "JWT secret loaded from env without fallback — crashes on missing var",
  "suggestion": "Add default or fail-fast with clear error message",
  "test_stub": "expect(() => loadConfig({})).toThrow('JWT_SECRET required')"
}
```

### Integration with voice

When voice detects "검토해봘" or "review", it:
1. Runs `git diff main...HEAD` to get changed files
2. Dispatches specialists in parallel (Agent tool with haiku/sonnet)
3. Collects findings, dedup, sort by severity
4. Presents as improvement cards (existing voice pattern)
5. Updates review stats

### CLI Usage (standalone)

```bash
# Review current branch changes
claude -p "Read voice/review-army.md, then review the diff from $(git merge-base main HEAD) to HEAD"

# Review specific files
claude -p "Read voice/review-army.md, then review src/auth.ts src/api.ts"
```

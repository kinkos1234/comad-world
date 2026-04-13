# ADR 0004 — Search → Brain Feedback Loop

- **Status:** Accepted (scaffold landed 2026-04-14)
- **Date:** 2026-04-14
- **Deciders:** Comad World maintainer (@kinkos1234)
- **Related:** Phase C of the self-evolution plan; ADR 0003 (routing)

## Context

`/search` discovers reference repos, evaluates them, generates adoption
plans, and — on `--apply` — stands them up in a git worktree and runs
the project's tests against the proposed changes. When verification
passes, the plan is ready for merge.

None of that learning flows back into brain. Next week, when someone
asks "what did we adopt for MCP servers and why?", brain has no
knowledge of the adoption. The graph is a read-only snapshot of the
crawled world, not of our own decisions.

## Goals

1. **Close the loop.** A successful `--apply` + verify writes a
   markdown record to `brain/data/adopted/` that the existing ingester
   can pick up on its next run.
2. **Capture intent, not just code.** The record includes the plan's
   motivation, the matched core-comad keywords, verification status,
   and the sandbox branch — so future answers can cite "we adopted X
   for Y, verified on branch Z."
3. **Zero coupling.** Search doesn't call the ingester directly.
   Writing a markdown file is an append to a directory; the ingester
   catches up on its schedule (daily cron).

## Non-goals

- Ingesting the adopted repo's full source AST. That's a much bigger
  project (AST chunking, code-aware embeddings). Start with README +
  plan record.
- Mutating the graph on apply. No neo4j writes in the search hot path.

## Decision

### File shape

On successful `--apply` verification, write
`brain/data/adopted/<YYYY-MM-DD>-<repo-slug>.md`:

```markdown
---
date: 2026-04-14
relevance: adopted
categories: [MCP, TypeScript]
source: https://github.com/owner/repo
verification_branch: adopt/mcp-server-001
verification_status: pass
core_matches: [mcp, typescript]
---

# Adopted: owner/repo

## Why we adopted it
<plan.rationale>

## What it offers
<plan.value_proposition>

## Verified on
branch: <branch> (typecheck pass, tests pass)

## README excerpt
<first 4KB of the repo's README>
```

The front-matter matches the ear-archive schema, so the existing
ingester (`geeknews-importer.ts`) can pick the files up by pointing
`ARCHIVE_DIR` at the adopted dir, or by a follow-up change that scans
both locations.

### Call site

`brain/packages/search/src/cli.ts` already knows when verification
passed. A single new call after the PASS branch:

```ts
if (verification.typecheck_passed && verification.tests_passed) {
  await recordAdoptedRepo(plan, verification);
}
```

Env-gated by `BRAIN_ADOPT_FEEDBACK`. Default off, so today's behavior
is unchanged byte-for-byte until the operator opts in.

### Failure semantics

The record is best-effort. If writing fails (disk full, race), the
search flow reports the failure but does not fail the user's `--apply`.
Adoption succeeded; logging it is a nicety.

## Rollout

1. **This PR:** `record-adopted.ts` + `recordAdoptedRepo()` +
   `recordAdoptedRepo.test.ts` using a tmp dir. Wired into cli.ts
   behind the env flag. No ingester change.
2. **Follow-up PR:** teach `geeknews-importer.ts` to scan
   `brain/data/adopted/` in addition to `ear/archive/`, or split the
   importer into a shared core + two thin wrappers.
3. **Enable:** flip `BRAIN_ADOPT_FEEDBACK=on` once we have 3–5
   adoptions to watch the loop work end-to-end.

## Alternatives considered

- **Direct neo4j write in the apply path.** Tightly couples search to
  brain's schema. Any schema migration becomes a cross-module break.
  File + existing ingester keeps the seam.
- **Emit a JSONL line instead of markdown.** The ingester is
  markdown-shaped today. Adopting JSONL would double the ingestion
  surface for marginal gain.
- **Push-trigger the ingester on every apply.** The ingester takes
  minutes; putting it in the user-facing apply flow is a regression.

## Open questions

- Should we also snapshot the `plan.diff` into the record so the
  adopted knowledge includes what we actually changed in our tree?
  Likely yes, but file size could grow — maybe compress or cap.
- Do we want an explicit "un-adopted" event (if we revert the merge)?
  Defer until we have a real revert to handle.

# ADR 0003 — Hybrid Synthesis Routing

- **Status:** Accepted (scaffold landed 2026-04-14)
- **Date:** 2026-04-14
- **Deciders:** Comad World maintainer (@kinkos1234)
- **Related:** Phase C of the self-evolution plan

## Context

`brain/packages/graphrag/src/synthesizer.ts` answers user questions from
graph context via one of two backends:

- **Ollama** (local, `qwen3.5:9b` by default) — only used when
  `USE_OLLAMA=1`. In the 2026-04-13 benchmark it doubled p50 latency at
  the 9B size; the 3B variant collapsed recall. So the flag defaults off
  and the hook sits unused.
- **`claude -p`** — the actual production path. Every question, whether
  "what is LLaMA?" or "compare the three most influential papers of the
  last year and explain their citations," pays Claude-Opus-class latency.

The Phase C proposal is that easy questions should not pay that price.
If a fast local model can answer a lookup correctly, we take the win;
otherwise we escalate to Claude. This is the same adaptive-routing idea
that Andrej's skill collection centers on: use the cheapest tool that
can do the job, don't default to the biggest one.

## Goals

1. **Cheap wins for easy questions.** Lookup-shaped questions run on
   `qwen3.5:9b` (or smaller) when the local model is running, with a
   short prompt and a short output budget.
2. **No regressions for hard questions.** Anything the classifier is
   uncertain about goes to `claude -p` as today. The classifier errs
   toward Claude.
3. **Observability, not hope.** Every routing decision logs which path
   it took, the classifier's signal, and end-to-end latency. We want to
   be able to read `brain/data/logs/synth-routing.jsonl` and know the
   easy/hard ratio and per-class p50/p95 over the last week.
4. **Reversibility.** A single env flag (`SYNTH_ROUTING=off`) pins every
   question to `claude -p`, matching today's behavior byte-for-byte.

## Non-goals

- Training or fine-tuning a dedicated classifier. Start with a heuristic.
- Replacing the existing LRU answer cache. Caching is orthogonal — the
  routing decision happens before the cache hits.
- Supporting arbitrary third-party models. If someone wants Groq or
  Together, they can extend `classifyQuestionComplexity` and plug in a
  backend; the routing layer is pluggable.

## Decision

### Classification — heuristic, not model

A pure function of the question string and the retrieved context length:

```
classify(question, contextLen) -> { tier: "easy" | "hard", reasons: [...] }
```

Easy when **all** of:
- question length ≤ 80 characters after trim
- no multi-hop / comparative keywords: `compare`, `비교`, `왜`, `어떻게`,
  `why`, `how`, `trade-?off`, `explain`, `설명`, `analyze`, `분석`
- no multi-clause structure (≤1 `,` / `?` / `.`)
- context length ≤ 1200 chars (otherwise synthesis IS the hard work)

Hard otherwise. Reasons are logged so we can tune the heuristic from
real data rather than guessing.

### Routing table

| Tier | Backend order                                 | Ctx cap | Timeout |
|------|-----------------------------------------------|---------|---------|
| easy | Ollama (if `USE_OLLAMA=1`) → fallback `claude -p` | 1200   | 15s     |
| hard | `claude -p` (Ollama skipped)                  | 3000   | 60s     |

When `SYNTH_ROUTING=off`, both tiers collapse to the hard route.

### Backend implementation

Reuses the existing `synthesizeOllama` / `synthesizeClaudeCLI` functions.
The new `routeAndSynthesize(question, context)` wraps them and writes a
one-line JSON log per request.

### Logging

`brain/data/logs/synth-routing.jsonl` — append-only, one JSON object per
request:

```json
{
  "ts": 1713148800123,
  "tier": "easy",
  "reasons": ["short", "no-hop-words"],
  "backend": "ollama",
  "fallback": false,
  "question_len": 42,
  "context_len": 890,
  "latency_ms": 1340,
  "answer_len": 228
}
```

A follow-up `scripts/synth-routing-report.sh` summarizes the log into
easy/hard ratio, p50/p95 latency, and Ollama fallback rate.

## Rollout

1. **PR (this one):** ship `classifier.ts` + `synth-router.ts` scaffold
   with unit tests. `synthesize()` gains an internal branch guarded by
   `SYNTH_ROUTING=on` (defaults off) so production behavior is
   unchanged.
2. **Shadow mode:** flip to `SYNTH_ROUTING=shadow` for a week. Both
   tiers run for every question; we log the would-be routing decision
   and the actual answer from `claude -p`. Compare answers by length
   and user-reported quality.
3. **Enable:** flip default to `on` after shadow-mode data supports it.

## Alternatives considered

- **Classify via Claude itself.** Too expensive — the classifier is in
  the hot path and adds Claude latency to every question.
- **Route by Cypher vs. vector retrieval.** Proxy signal at best.
  Vector-retrieval questions can still be factual one-liners.
- **Skip routing, just shrink the context cap globally.** Loses recall
  on hard questions to save p50 on easy ones. Doesn't get us the right
  shape of tradeoff.

## Open questions

- Should the easy-tier fallback to `claude -p` also shrink the context
  (to keep the "easy" budget)? Current stance: **yes**, keep the 1200
  cap. If Ollama failed on 1200 chars, the signal says the question
  wasn't actually easy, and we should take one more shot at that budget
  before escalating.
- Do we want a third "trivial" tier (hand-rolled templates for "what is
  X?") to bypass the LLM entirely? Defer; not enough data yet.

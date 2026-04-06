# Show HN 포스트 초안

> 게시처: https://news.ycombinator.com/submit
> 타이밍: 화-목 오전 8-10시 EST (한국시간 밤 10시-자정)

---

## Title

Show HN: Comad Voice – Natural language triggers for autonomous Claude Code pipelines

## URL

https://github.com/kinkos1234/comad-voice

## Text (optional, HN 스타일로 간결하게)

Comad Voice is a CLAUDE.md configuration harness that adds natural language triggers to Claude Code. It targets non-developers who have AI subscriptions but don't know what to ask.

Say "검토해봐" (review this) → Claude diagnoses the codebase, shows improvement cards, you pick a number, and it runs an autoresearch experiment loop.

Say "풀사이클" (full-cycle) → 6-stage pipeline: RESEARCH → DECOMPOSE → EXPERIMENT → INTEGRATE → POLISH → DELIVER, with automatic Codex parallel delegation.

It's configuration-only: markdown files + a bash installer. No runtime code, no external dependencies. Requires Claude Code (Claude Max recommended).

The core idea comes from Karpathy's "Software in the era of AI" talk — Generation + Verification loops with partial autonomy. Comad Voice automates the loop while keeping the human in control through card-based choices.

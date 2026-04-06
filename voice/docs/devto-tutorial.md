# How I Built an AI Workflow System That Lets Non-Developers Run Autonomous Pipelines

> 게시처: https://dev.to/
> 태그: claudecode, ai, productivity, opensource

---

## The Problem: AI Subscription Waste

I'm not a developer. But I subscribe to Claude Max, ChatGPT Plus, and Google Pro simultaneously.

The embarrassing truth? I was using less than 10% of my tokens every month.

Not because the tools weren't powerful. Because **I didn't know what to ask**.

"Fix this bug" → Claude fixes one thing → done.
"Improve this" → What should I improve? → silence.

There was no framework for systematic improvement. No way to say "just make everything better" and have it actually work.

## The Inspiration: Karpathy's Insight

Then I watched [Andrej Karpathy's "Software in the era of AI"](https://www.youtube.com/watch?v=kwSVtQ7dziU) talk. Two ideas stuck:

1. **Generation + Verification loops**: AI generates, tests, keeps or discards. Repeat.
2. **Autonomy Slider**: Not fully autonomous, not fully manual — somewhere in between.

What if I could build a system where:
- AI runs the loop automatically
- But I still make the key decisions
- Through simple card-based choices, not code

## What I Built: Comad Voice

**Comad Voice** is a workflow harness for Claude Code. The tagline: *"Just say it. AI does the rest."*

It's not a new CLI tool. It's not a framework. It's **configuration** — markdown files that inject into Claude Code's `CLAUDE.md`, adding natural language triggers.

### Trigger 1: "Review this" (검토해봐)

Open any project in Claude Code and just type:

```
검토해봐
```

What happens:
1. Claude analyzes your entire codebase
2. Presents 3-5 improvement cards with difficulty and impact ratings
3. You pick a number
4. An autonomous experiment loop runs (autoresearch)

No technical knowledge needed. Just pick a card.

### Trigger 2: "Full-cycle" (풀사이클)

For big topics, the 6-stage pipeline auto-executes:

```
RESEARCH → DECOMPOSE → EXPERIMENT → INTEGRATE → POLISH → DELIVER
```

The system even auto-detects which subtasks are independent (→ delegated to Codex in parallel) vs dependent (→ Claude runs sequentially). Non-developers don't need to understand dependency analysis.

### Trigger 3: Multi-AI Orchestration

Comad Voice doesn't just use Claude. It orchestrates:
- **Claude (Opus)**: Decisions, architecture, complex code
- **Codex**: Independent parallel tasks
- **Gemini**: Large-scale research

### Trigger 4: Repo Polish

Say "광택" (polish) and your GitHub repo gets auto-packaged to open source standards: badges, CHANGELOG, social preview, CI templates.

## How to Install

```bash
curl -fsSL https://raw.githubusercontent.com/kinkos1234/comad-voice/main/install.sh | bash
```

Prerequisites:
- Claude Code (Claude Max recommended)
- Optional: Codex CLI + tmux for parallel delegation

## What I Learned

1. **Non-developers need different UX**: Not "what command should I type?" but "which card looks interesting?"
2. **Configuration > Code for accessibility**: A markdown file is less scary than a new CLI tool
3. **Partial autonomy > Full autonomy**: Let AI run the loop, but keep humans at decision points
4. **Session memory matters**: Long AI conversations degrade. Comad Voice auto-manages session breaks.

## Links

- **GitHub**: https://github.com/kinkos1234/comad-voice
- **Inspiration**: [Karpathy — "Software in the era of AI"](https://www.youtube.com/watch?v=kwSVtQ7dziU)

MIT licensed. Feedback and stars welcome!

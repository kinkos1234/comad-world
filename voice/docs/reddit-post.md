# r/ClaudeCode 포스트 초안

> 게시처: https://www.reddit.com/r/ClaudeCode/
> 타이밍: US 오전 9-11시 EST (한국시간 밤 11시-새벽 1시)

---

## Title

I built a workflow harness that lets non-developers run autonomous AI pipelines with just natural language

## Body

I'm a non-developer who subscribes to Claude Max + ChatGPT Plus + Google Pro — and was using less than 10% of my tokens every month.

The problem? I didn't know **what to ask**.

"Improve this" → Claude fixes one thing → done. No framework for systematic improvement.

So I built **Comad Voice** — a CLAUDE.md configuration harness that adds natural language triggers to Claude Code.

### How it works

Say **"검토해봐"** (or "review this") and Claude will:
1. Auto-analyze your entire codebase
2. Present 3-5 improvement cards with difficulty/impact ratings
3. You pick a number → autonomous experiment loop runs

Say **"풀사이클"** (or "full-cycle") for big topics → 6-stage pipeline:
```
RESEARCH → DECOMPOSE → EXPERIMENT → INTEGRATE → POLISH → DELIVER
```

### Key features
- 4 natural language triggers (review, full-cycle, parallel, repo polish)
- Automatic dependency analysis — decides what to run in parallel vs sequential
- Session memory management — prevents context pollution in long sessions
- Multi-AI orchestration: Claude (decisions) + Codex (parallel tasks) + Gemini (research)
- One-line install: `curl -fsSL https://raw.githubusercontent.com/kinkos1234/comad-voice/main/install.sh | bash`

### What it is NOT
- Not a new CLI tool — it's configuration (markdown + bash)
- Not magic — you still need Claude Code installed
- No external dependencies — fully standalone

### Requirements
- Claude Code (Claude Max recommended)
- Optional: Codex CLI + tmux for parallel delegation

### Links
- GitHub: https://github.com/kinkos1234/comad-voice
- Inspired by: [Andrej Karpathy — "Software in the era of AI"](https://www.youtube.com/watch?v=kwSVtQ7dziU)

MIT licensed. Feedback and contributions welcome!

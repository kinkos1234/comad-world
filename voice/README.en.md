<p align="center">
  <img src="docs/images/slide-1-cover.png" alt="Comad Voice" width="480" style="max-width: 100%;">
</p>

<h1 align="center">Comad Voice</h1>

<p align="center">
  <strong>"Just say it. AI does the rest."</strong>
</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="License: MIT"></a>
  <a href="https://github.com/kinkos1234/comad-voice/releases"><img src="https://img.shields.io/github/v/release/kinkos1234/comad-voice?include_prereleases" alt="Release"></a>
  <img src="https://img.shields.io/badge/Made%20with-AI-22D3EE" alt="Made with AI">
  <img src="https://img.shields.io/badge/Claude%20Code-compatible-blueviolet" alt="Claude Code">
  <a href="https://github.com/kinkos1234/comad-voice/stargazers"><img src="https://img.shields.io/github/stars/kinkos1234/comad-voice?style=social" alt="GitHub Stars"></a>
</p>

<p align="center">
  AI workflow harness for non-developer vibe coders.<br>
  Just Claude Code — throw one big topic and it auto-runs:<br>
  research → experiment → refactor → ship.
</p>

<p align="center">
  <a href="README.md">한국어</a> · English
</p>

---

## Table of Contents

- [Comad Series](#comad-series)
- [Who Is This For?](#who-is-this-for)
- [What Changes?](#what-changes)
- [Why Comad Voice?](#why-comad-voice)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Usage](#usage)
- [Command Cheatsheet](#command-cheatsheet)
- [How It Works](#how-it-works)
- [Troubleshooting](#troubleshooting)
- [Credits](#credits)
- [Contributing](#contributing)
- [License](#license)

---

## Comad Series

| Name            | Role                              |
| --------------- | --------------------------------- |
| **ComadEye**    | Future Simulator (see)            |
| **Comad Ear**   | Discord Bot Server (listen)       |
| **Comad Brain** | Knowledge Ontology (think)        |
| **Comad Voice** | AI Workflow Harness (speak)       |

---

## Who Is This For?

- People who don't code but want to build projects with AI
- Subscribers of Claude Max / ChatGPT Plus / Google Pro who underutilize them
- Vibe coders who don't know what to ask

## What Changes?

**Before:** "Improve this" → Claude fixes one thing and stops

**After:** "Review this" → Claude auto-diagnoses, shows improvement cards, you pick a number, and it runs an autonomous experiment loop

<p align="center">
  <img src="docs/images/slide-2-before-after.png" alt="Before vs After" width="600" style="max-width: 100%;">
</p>

### Feature Comparison

| Feature | Raw Claude Code | With Comad Voice |
| --- | :---: | :---: |
| One-word diagnosis ("review this") | - | Yes |
| Autonomous experiment loop (autoresearch) | - | Yes |
| Multi-AI dependency auto-detection | - | Yes |
| Session memory management | - | Yes |
| Local model wait-time utilization | - | Yes |
| Non-developer card UI | - | Yes |
| Installation complexity | - | 1-line curl |

### Why Comad Voice?

Claude Code is powerful, but it's designed for people who **know what to ask**.

Comad Voice is for the other side:
- Say "review this" and AI diagnoses and experiments on its own
- Dependency analysis, parallel delegation, and session management happen automatically
- It's **configuration**, not code — install and speak

> Not "using tools well" but "tools working well on their own."

---

## Prerequisites

| Tool                       | Required | Description                                    |
| -------------------------- | -------- | ---------------------------------------------- |
| **Claude Code**            | Yes      | Claude Max subscription recommended (Opus)     |
| **Codex CLI**              | Optional | Parallel task delegation (works without it)    |
| **tmux**                   | Optional | Required for Codex CLI parallel execution      |

> All features work with just Claude Code — no external tool dependencies.

### Pre-installation

```bash
# Codex CLI (optional)
npm install -g @openai/codex

# tmux (optional, macOS)
brew install tmux
```

---

## Installation

```bash
curl -fsSL https://raw.githubusercontent.com/kinkos1234/comad-voice/main/install.sh | bash
```

Or manual install:

```bash
git clone https://github.com/kinkos1234/comad-voice.git
cd comad-voice
./install.sh
```

What the installer does:

1. Appends Comad Voice config to `~/.claude/CLAUDE.md`
2. Optionally copies memory templates to your current project

---

## Usage

### 1. "Review this" — Easiest Start

Open Claude Code in your project folder and just say:

```
검토해봐
```

(or in English: "review this", "health check", "diagnose")

Claude will:

1. Analyze your codebase
2. Show improvement areas as cards
3. Just pick a number — the experiment loop runs automatically

### 2. "Full-cycle" — Throw a Big Topic

```
Improve the report quality of ComadEye overall
```

The 6-stage pipeline auto-executes:

```
RESEARCH → DECOMPOSE → EXPERIMENT → INTEGRATE → POLISH → DELIVER
```

### 3. Local Model Wait Time Utilization

While local LLM tests are running:

```
Prepare the next experiment code while waiting
```

Claude auto-manages background execution + parallel work.

### 4. Session Management

For long tasks, split sessions:

```
Save results to memory and start a new session
```

---

## Command Cheatsheet

| What you want            | Just say this                              |
| ------------------------ | ------------------------------------------ |
| Diagnose current state   | "검토해봐", "review this"                  |
| Auto-run big topic       | "풀사이클", "full-cycle"                   |
| Iterative experiments    | "experiment", "autoresearch"               |
| Save session             | "save session", "여기까지"                 |
| Resume work              | "continue", "이어서 해줘"                  |
| Use wait time            | "prepare next experiment"                  |
| Parallel tasks           | Auto-detected (delegates if independent)   |
| Polish your repo         | "repo polish", "광택"                      |

---

## How It Works

### Full-Cycle Pipeline

<p align="center">
  <img src="docs/images/slide-3-pipeline.png" alt="Full-Cycle Pipeline" width="600" style="max-width: 100%;">
</p>

```
User: "Improve report quality"
         ↓
[RESEARCH] Analyze current code + research related techniques
         ↓
[DECOMPOSE] Break into subtasks + auto-judge dependencies
   🟢 Independent → Delegate to Codex in parallel
   🔴 Dependent → Claude runs sequentially
   🟡 Needs context → Claude handles directly
         ↓
[EXPERIMENT] autoresearch loop per subtask
         ↓
[INTEGRATE] Merge best results + refactor
         ↓
[POLISH] QA + performance + documentation
         ↓
[DELIVER] Create PR + retrospective
```

### Automatic Dependency Analysis

Non-developers don't need to judge "is this independent or dependent?"
Claude auto-analyzes using 5 criteria:

1. File overlap between tasks?
2. Uses functions created by other tasks?
3. Takes output from other tasks as input?
4. Must run in a specific order?
5. Modifies shared state?

### Session Memory

Prevents context pollution in long sessions:

- Session swap recommended every 5-7 experiments
- Important results auto-saved to memory files
- Auto-restored in new sessions

### Project Structure

```
comad-voice/
├── core/
│   ├── comad-voice.md          # Core config (appended to CLAUDE.md)
│   └── triggers/
│       ├── t0-onboarding.md    # First session onboarding
│       ├── t1-review.md        # "Review this" trigger
│       ├── t2-fullcycle.md     # "Full-cycle" trigger
│       ├── t3-parallel.md      # Parallel auto-detection
│       ├── t4-polish.md        # Repo polish trigger
│       └── t5-session-save.md  # Session save & handoff
├── memory-templates/           # Session memory templates
├── examples/
│   └── first-session.md        # First session guide
├── install.sh                  # One-click installer
└── tests/                      # bats test suite
```

---

## Troubleshooting

### "Review this" doesn't work

- Check that `COMAD-VOICE:START` marker exists in `~/.claude/CLAUDE.md`
- Run `cat ~/.claude/CLAUDE.md | grep COMAD-VOICE` to verify installation

### Install script fails

- Verify Claude CLI is installed: `which claude`
- Existing backup available at: `~/.claude/CLAUDE.md.bak.*`

### Codex parallel delegation doesn't work

- Check Codex CLI: `which codex`
- Check tmux: `which tmux`
- This feature is optional — everything works without Codex

---

## Credits

Comad Voice was independently developed, inspired by:

- **autoresearch** pattern — Autonomous experiment loop (Andrej Karpathy inspired)
- **Multi-agent orchestration** — Role-based agent delegation patterns
- **Safety protocols** — Dangerous command warnings, debugging principles

> Comad Voice runs fully standalone with just Claude Code. No external tool dependencies.

### Inspiration

- [Andrej Karpathy — "Software in the era of AI"](https://www.youtube.com/watch?v=kwSVtQ7dziU)
  - Generation + Verification loop
  - Autonomy Slider concept
  - "Partial autonomy" for AI collaboration

---

## Contributing

Contributions are welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for details.

---

## License

[MIT](LICENSE) — Free to use, modify, and distribute.

---

## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=kinkos1234/comad-voice&type=Date)](https://star-history.com/#kinkos1234/comad-voice&Date)

---

<p align="center">
  <strong>Made with AI by Comad J</strong>
</p>

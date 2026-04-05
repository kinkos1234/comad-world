# Photo — AI Photo Correction Agent

Claude Code agent for AI-powered photo correction via Photoshop MCP.

**Domain-agnostic** — works with any photo subject.

## Principles

- **Naturalness first** — if it looks corrected, it's a failure
- **Non-destructive** — backup mandatory
- **Conservative on portraits** — extremely light touch
- **Respect intent** — moody/artistic photos get minimal correction

## Engine Priority

1. **PIL** — Basic corrections (exposure, white balance, color). Over-correction guard: MAE > 20 triggers reduction.
2. **Camera Raw** (via Computer Use) — Texture, clarity, dehaze, vignette. Used when PIL can't achieve the desired effect.
3. **Advanced** (Generative Fill, Neural Filters) — Only when explicitly requested by user.

## Requirements

- Adobe Photoshop (running instance)
- Claude Code with Computer Use + Photoshop MCP

## Install

```bash
cp photo/core/comad-photo.md ~/.claude/agents/
```

## Usage

Open a photo directory in Claude Code, then say:
- "이 사진 보정해줘" / "correct this photo"
- "사진 보정" / "photo correction"

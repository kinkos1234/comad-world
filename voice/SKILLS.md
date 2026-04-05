# Comad Voice Skills — Portable Format

Voice skills are standalone markdown files that any Claude Code user can install.
No runtime dependency on comad-world — each skill is self-contained.

## Skill Format

Each `.md` file in `voice/` is a skill:

```
voice/
├── review-army.md    — Multi-specialist code review
├── qa.md             — Browser-based QA testing
├── repo-polish.md    — GitHub repo professionalization (planned)
├── session-save.md   — Session checkpoint & handoff (planned)
└── SKILLS.md         — This file
```

## Install a Single Skill

```bash
# Copy one skill to your Claude Code config
cp voice/qa.md ~/.claude/skills/comad-qa.md

# Or append to CLAUDE.md
echo "## QA Skill" >> ~/.claude/CLAUDE.md
cat voice/qa.md >> ~/.claude/CLAUDE.md
```

## Install All Skills

```bash
cd voice && ./install.sh
```

## Creating a New Skill

1. Create `voice/my-skill.md`
2. Define trigger keywords at the top
3. Write the procedure as Claude-readable instructions
4. Add to the trigger table in `voice/README.md`
5. Test: `claude -p "Read voice/my-skill.md, then execute it"`

## Skill Authoring Rules

- **Self-contained**: No imports, no external scripts, no runtime dependencies
- **Trigger-first**: First line defines when the skill activates
- **Procedure**: Step-by-step instructions Claude can follow
- **Output format**: Define expected output structure
- **Idempotent**: Running twice produces the same result

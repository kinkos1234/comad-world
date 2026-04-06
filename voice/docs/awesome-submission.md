# awesome-claude-code 제출 양식

> 제출처: https://github.com/hesreallyhim/awesome-claude-code/issues/new?template=recommend-resource.yml
> **반드시 GitHub 웹 UI에서 Issue로 제출** (PR이 아님!)

---

## 양식 작성 내용

### Display Name
Comad Voice

### Category
Workflows & Knowledge Guides

### Sub-Category
General

### Primary Link
https://github.com/kinkos1234/comad-voice

### Author Name
Comad J (kinkos1234)

### Author Link
https://github.com/kinkos1234

### License
MIT

### Description
AI workflow harness that turns natural language commands into autonomous multi-stage pipelines for non-developers. Injects trigger-based workflows into CLAUDE.md so that saying "검토해봐" (review this) auto-diagnoses a codebase and presents improvement cards, while "full-cycle" runs a 6-stage pipeline from research through delivery with automatic Codex parallel delegation.

### Validate Claims
Install with `curl -fsSL https://raw.githubusercontent.com/kinkos1234/comad-voice/main/install.sh | bash` (requires Claude Code). Open any project in Claude Code and say "검토해봐". Claude will analyze the codebase and present 3-5 improvement cards with difficulty ratings and expected impact.

### Specific Task(s)
Install Comad Voice, open a project, and type "검토해봐" to see the diagnostic card system. Then pick a card number to watch the autoresearch loop execute.

### Specific Prompt(s)
- "검토해봐" (or "review this" / "health check" in English)
- "풀사이클" (or "full-cycle" in English)

### Additional Comments
Comad Voice is a configuration-only harness (no runtime code, no external dependencies) that bridges the gap between Claude Code's power and non-technical users by providing natural language triggers. Fully standalone — just Claude Code. Bilingual Korean/English documentation. Inspired by Andrej Karpathy's "Software in the era of AI" talk. MIT licensed, tested with bats, CI/CD with GitHub Actions.

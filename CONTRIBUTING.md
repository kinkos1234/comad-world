# Contributing to Comad World

## Adding a Preset

1. Copy an existing preset: `cp presets/ai-ml.yaml presets/your-domain.yaml`
2. Edit all sections:
   - `profile` — name and description
   - `interests` — high/medium/low with keywords
   - `categories` — domain-specific tags
   - `sources` — RSS feeds, arXiv categories, GitHub topics
   - `must_read_stack` — daily-use tools
   - `brain.entity_extraction` — domain hint and relationship types
3. Test: `cp presets/your-domain.yaml comad.config.yaml && ./scripts/apply-config.sh`
4. Submit a PR

## Module Development

Each module lives in its own directory and should work independently.

- **Config-driven modules** (brain, ear) read from `comad.config.yaml`
- **Domain-agnostic modules** (eye, photo, sleep, voice) need no config changes

## Code Style

- TypeScript (brain): Bun runtime, no external test framework
- Python (eye): Python 3.13+, pytest, type hints
- Shell scripts: `set -euo pipefail`, shellcheck clean
- Markdown: markdownlint compliant

## License

By contributing, you agree your contributions are licensed under MIT.

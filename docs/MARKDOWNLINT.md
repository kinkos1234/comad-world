# Markdownlint Rules Reference

Comad uses a standardized markdownlint config across all modules.
Config file: `.markdownlint-cli2.jsonc` (same in every repo).

## Enabled Rules (catch real issues)

| Rule | Name | Why |
|------|------|-----|
| MD001 | heading-increment | h1 → h3 skip breaks document outline |
| MD003 | heading-style | Mixed `#` and `===` is confusing |
| MD005 | list-indent | Broken indentation changes meaning |
| MD009 | no-trailing-spaces | Git diff noise |
| MD010 | no-hard-tabs | Inconsistent rendering |
| MD011 | no-reversed-links | `(text)[url]` is a bug |
| MD018 | no-missing-space-atx | `#heading` renders wrong |
| MD023 | heading-start-left | Indented headings don't render |
| MD025 | single-h1 | Multiple h1 breaks SEO and structure |
| MD037 | no-space-in-emphasis | `** bold **` doesn't render |
| MD038 | no-space-in-code | `` ` code ` `` doesn't render |
| MD042 | no-empty-links | `[text]()` is broken |
| MD045 | no-alt-text | Accessibility |
| MD051 | link-fragments | `#broken-anchor` links |

## Disabled Rules (stylistic, not quality)

| Rule | Name | Why disabled |
|------|------|-------------|
| MD007 | ul-indent | Conflicts with nested lists in technical docs |
| MD012 | no-multiple-blanks | Harmless formatting preference |
| MD013 | line-length | Impractical for tables, URLs, badges |
| MD022 | blanks-around-headings | Breaks compact doc style |
| MD024 | no-duplicate-heading | Valid: "Usage" under different modules |
| MD026 | no-trailing-punctuation | Korean headings use colons naturally |
| MD029 | ol-prefix | `1. 1. 1.` vs `1. 2. 3.` is preference |
| MD031 | blanks-around-fences | Breaks compact code examples |
| MD032 | blanks-around-lists | Breaks compact layout |
| MD033 | no-inline-html | Needed for badges, alignment, images |
| MD034 | no-bare-urls | Bare URLs fine in technical docs |
| MD036 | no-emphasis-as-heading | Common in changelogs |
| MD040 | fenced-code-language | Not all code blocks need language tags |
| MD041 | first-line-heading | READMEs start with HTML badges |
| MD047 | single-trailing-newline | Auto-fixed by editors |
| MD050 | strong-style | Asterisks vs underscores — preference |
| MD058 | blanks-around-tables | Conflicts with compact tables |
| MD060 | table-column-count | False positives on complex tables |

## Ignored Paths

- `node_modules/`, `.venv/` — dependencies
- `*-report-*.md` — generated reports
- `CHANGELOG.md` — auto-generated
- `data/`, `archive/` — runtime data
- `.omc/`, `.comad/` — session state

## Applying to a new repo

Copy `.markdownlint-cli2.jsonc` from comad-world root.

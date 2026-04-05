#!/usr/bin/env python3
"""
README QA Scorer — measures GitHub star-readiness of README.md

Scoring criteria based on analysis of top-starred GitHub repos:
  - awesome-readme, Best-README-Template, GitHub Community Standards
  - Patterns from repos with 1k-50k stars

Target: 90/100 to be considered "star-ready"

Usage:
    python3 scripts/qa-readme.py                  # Score README.md
    python3 scripts/qa-readme.py --verbose         # Show details per check
    python3 scripts/qa-readme.py --fix-hints       # Show how to fix failures
"""

import re
import sys
import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
README_PATH = REPO_ROOT / "README.md"


class Check:
    def __init__(self, name: str, points: int, description: str, fix_hint: str = ""):
        self.name = name
        self.points = points
        self.description = description
        self.fix_hint = fix_hint
        self.passed = False
        self.detail = ""


def load_readme() -> str:
    if not README_PATH.exists():
        print("ERROR: README.md not found")
        sys.exit(1)
    return README_PATH.read_text(encoding="utf-8")


def run_checks(content: str) -> list[Check]:
    checks = []
    lines = content.split("\n")
    lower = content.lower()

    # ── 1. Hero Section (15 points) ──────────────────────────────
    c = Check("hero_title", 3, "H1 title exists",
              "Add a top-level # Title or <h1> tag")
    c.passed = bool(re.search(r"<h1[^>]*>|^# ", content, re.MULTILINE))
    checks.append(c)

    c = Check("hero_tagline", 4, "One-line tagline/description under title",
              "Add a <p align='center'><strong>tagline</strong></p> or bold line after title")
    c.passed = bool(re.search(r"<strong>.*?</strong>|^\*\*[^*]+\*\*$", content, re.MULTILINE))
    checks.append(c)

    c = Check("hero_badges", 3, "At least 2 badges (shields.io or similar)",
              "Add badges: license, version, CI status, etc.")
    badge_count = len(re.findall(r"img\.shields\.io|badge/|!\[.*?\]\(https?://", content))
    c.passed = badge_count >= 2
    c.detail = f"{badge_count} badges found"
    checks.append(c)

    c = Check("hero_visual", 5, "Visual element: image, GIF, ASCII diagram, or screenshot",
              "Add a hero image, architecture diagram, or demo GIF")
    has_image = bool(re.search(r"<img |!\[.*?\]\(.*?\.(png|jpg|gif|svg|webp)", content, re.I))
    has_ascii_diagram = bool(re.search(r"[─│┌┐└┘├┤┬┴┼╔╗╚╝║═▶→←↑↓].*[─│┌┐└┘├┤┬┴┼╔╗╚╝║═▶→←↑↓]", content))
    has_mermaid = "```mermaid" in lower
    c.passed = has_image or has_ascii_diagram or has_mermaid
    checks.append(c)

    # ── 2. Value Proposition (12 points) ─────────────────────────
    c = Check("what_is", 4, "'What is' or 'Overview' section explaining the project",
              "Add a ## What is X? section with 2-3 sentences")
    c.passed = bool(re.search(r"##.*What is|## Overview|## About", content, re.I))
    checks.append(c)

    c = Check("key_differentiator", 4, "Clear differentiator: why THIS over alternatives",
              "Add 'The key idea:' or comparison table or 'Unlike X, this...'")
    c.passed = bool(re.search(r"key idea|unlike|differenti|compared to|vs\.|the magic|what makes", lower))
    checks.append(c)

    c = Check("use_cases", 4, "Concrete use cases or 'Who is this for'",
              "Add ## Who is this for? or bullet list of use cases")
    c.passed = bool(re.search(r"who is this for|use case|designed for|built for|for .*who|perfect for", lower))
    checks.append(c)

    # ── 3. Quick Start (15 points) ───────────────────────────────
    c = Check("install_section", 5, "Clear install/quickstart section",
              "Add ## Quickstart or ## Install with step-by-step commands")
    c.passed = bool(re.search(r"## (Quick ?start|Install|Getting Started|Setup)", content, re.I))
    checks.append(c)

    c = Check("install_commands", 5, "Copy-pasteable install commands (```bash blocks)",
              "Add bash code blocks with actual commands")
    bash_blocks = re.findall(r"```(?:bash|sh)\n(.*?)```", content, re.DOTALL)
    c.passed = len(bash_blocks) >= 2
    c.detail = f"{len(bash_blocks)} bash blocks found"
    checks.append(c)

    c = Check("install_under_30_lines", 5, "Quickstart is under 30 lines (not overwhelming)",
              "Keep quickstart concise — move details to separate docs")
    # Find quickstart section and measure its length
    qs_match = re.search(r"(## (?:Quick ?start|Install|Getting Started).*?)(?=\n## |\Z)", content, re.I | re.DOTALL)
    if qs_match:
        qs_lines = len(qs_match.group(1).strip().split("\n"))
        c.passed = qs_lines <= 30
        c.detail = f"{qs_lines} lines"
    checks.append(c)

    # ── 4. Architecture / How It Works (10 points) ───────────────
    c = Check("architecture", 5, "Architecture section or diagram",
              "Add ## Architecture with a visual diagram")
    c.passed = bool(re.search(r"## Architecture|## How .* Works|## Design", content, re.I))
    checks.append(c)

    c = Check("module_list", 5, "Module/component breakdown (table or list)",
              "Add a table or list showing each module and its purpose")
    # Count markdown tables
    table_count = len(re.findall(r"\|.*\|.*\|", content))
    c.passed = table_count >= 3
    c.detail = f"{table_count} table rows"
    checks.append(c)

    # ── 5. Customization / Config (8 points) ─────────────────────
    c = Check("customization", 4, "Customization/configuration section",
              "Add ## Customization showing how to adapt the project")
    c.passed = bool(re.search(r"## Custom|## Config|## Personali", content, re.I))
    checks.append(c)

    c = Check("config_example", 4, "YAML/JSON config example shown",
              "Show a real config snippet users can modify")
    c.passed = bool(re.search(r"```ya?ml|```json", content, re.I))
    checks.append(c)

    # ── 6. Project Structure (5 points) ──────────────────────────
    c = Check("project_tree", 5, "Project structure tree shown",
              "Add a ```tree or directory structure showing layout")
    c.passed = bool(re.search(r"├──|└──|comad-world/\n", content))
    checks.append(c)

    # ── 7. Requirements / Prereqs (5 points) ─────────────────────
    c = Check("requirements", 5, "Requirements/prerequisites listed",
              "Add ## Requirements with a table of needed tools")
    c.passed = bool(re.search(r"## Require|## Prereq|### Prereq", content, re.I))
    checks.append(c)

    # ── 8. FAQ (5 points) ────────────────────────────────────────
    c = Check("faq", 5, "FAQ section with common questions",
              "Add ## FAQ with Q: / A: pairs")
    c.passed = bool(re.search(r"## FAQ|## Frequently", content, re.I))
    checks.append(c)

    # ─��� 9. Community / Contributing (8 points) ───────────────────
    c = Check("contributing", 3, "Contributing link or section",
              "Link to CONTRIBUTING.md or add ## Contributing")
    c.passed = bool(re.search(r"contribut", lower))
    checks.append(c)

    c = Check("license_mentioned", 2, "License mentioned",
              "Add ## License with license type")
    c.passed = bool(re.search(r"## License|license.*MIT|MIT.*license", content, re.I))
    checks.append(c)

    c = Check("credits", 3, "Credits or acknowledgments",
              "Add ## Credits acknowledging tools/inspirations")
    c.passed = bool(re.search(r"## Credits|## Acknowledg|Built with", content, re.I))
    checks.append(c)

    # ── 10. SEO / Discoverability (7 points) ─────────────────────
    c = Check("emoji_or_icon", 2, "Strategic emoji or icon usage (not overdone)",
              "Add 1-3 emoji in key headers for visual scanning")
    emoji_pattern = re.compile("[\U0001F300-\U0001F9FF]|[\u2600-\u26FF]|[\u2700-\u27BF]")
    emoji_count = len(emoji_pattern.findall(content))
    c.passed = 1 <= emoji_count <= 15
    c.detail = f"{emoji_count} emoji"
    checks.append(c)

    c = Check("centered_header", 2, "Centered header (align=center) for visual appeal",
              "Use <p align='center'> or <h1 align='center'> for hero section")
    c.passed = bool(re.search(r'align="center"|align=.center', content))
    checks.append(c)

    c = Check("toc", 3, "Table of contents or navigation links",
              "Add anchor links at top: [Quickstart](#quickstart) · [Architecture](#architecture)")
    md_anchors = len(re.findall(r"\[.*?\]\(#.*?\)", content))
    html_anchors = len(re.findall(r'href="#[^"]*"', content))
    anchor_links = md_anchors + html_anchors
    c.passed = anchor_links >= 3
    c.detail = f"{anchor_links} anchor links"
    checks.append(c)

    # ── 11. Length / Readability (5 points) ───────────────────────
    c = Check("not_too_short", 2, "README is substantial (>100 lines)",
              "Expand README — top repos average 150-400 lines")
    c.passed = len(lines) > 100
    c.detail = f"{len(lines)} lines"
    checks.append(c)

    c = Check("not_too_long", 3, "README is not overwhelming (<500 lines)",
              "Move detailed docs to separate files, keep README focused")
    c.passed = len(lines) < 500
    c.detail = f"{len(lines)} lines"
    checks.append(c)

    return checks


def print_report(checks: list[Check], verbose: bool, fix_hints: bool):
    total_possible = sum(c.points for c in checks)
    total_scored = sum(c.points for c in checks if c.passed)
    score = round(total_scored / total_possible * 100)

    print()
    print("=" * 60)
    print(f"  README QA Score: {total_scored}/{total_possible} ({score}/100)")
    print("=" * 60)

    if score >= 90:
        print("  Status: PASS — Star-ready!")
    elif score >= 70:
        print(f"  Status: NEEDS WORK — {90 - score} more points to star-ready")
    else:
        print(f"  Status: MAJOR GAPS — {90 - score} more points needed")

    print()

    # Group by category
    categories = {}
    for c in checks:
        cat = c.name.split("_")[0]
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(c)

    for c in checks:
        icon = "✓" if c.passed else "✗"
        color_start = "\033[32m" if c.passed else "\033[31m"
        color_end = "\033[0m"

        if verbose or not c.passed:
            detail = f" ({c.detail})" if c.detail else ""
            print(f"  {color_start}{icon}{color_end} [{c.points}pt] {c.description}{detail}")
            if fix_hints and not c.passed:
                print(f"      → {c.fix_hint}")

    print()

    # Summary
    passed = sum(1 for c in checks if c.passed)
    failed = sum(1 for c in checks if not c.passed)
    print(f"  Checks: {passed} passed, {failed} failed, {len(checks)} total")
    print(f"  Score:  {score}/100 (target: 90)")
    print()

    return score


def main():
    verbose = "--verbose" in sys.argv or "-v" in sys.argv
    fix_hints = "--fix-hints" in sys.argv or "-f" in sys.argv

    content = load_readme()
    checks = run_checks(content)
    score = print_report(checks, verbose, fix_hints)

    # Exit code: 0 if >= 90, 1 otherwise
    sys.exit(0 if score >= 90 else 1)


if __name__ == "__main__":
    main()

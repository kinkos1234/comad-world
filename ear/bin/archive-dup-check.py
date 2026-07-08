#!/usr/bin/env python3
"""archive-dup-check — has this URL already been archived?

Used by the cdx command-mode backfill flow (and any agent doing catch-up).
Both Claude and Codex see the same archive directory now (Phase 1 symlink),
so a single check covers both.

Usage:
    archive-dup-check.py <url>...
    archive-dup-check.py --json <url>      # machine-readable output

Exit codes:
    0  all URLs already archived (or no URLs given)
    1  at least one URL is NEW (not archived)
    2  scan failed

Matching rules:
    A URL counts as archived if any frontmatter `source:` OR `geeknews:` value
    in archive/*.md equals it (string equality, after stripping <>()[]{}.,).
    Also tolerates `?utm_*` differences via a normalized comparison.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode

ARCHIVE = Path("/Users/jhkim/Programmer/01-comad/comad-world/ear/archive")
TRACKING_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "ref", "ref_src", "fbclid", "gclid", "mc_cid", "mc_eid",
}

FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---", re.DOTALL)
URL_FIELD_RE = re.compile(
    r"^(?:source|geeknews):\s*(.+?)\s*$",
    re.MULTILINE,
)


def normalize_url(u: str) -> str:
    """Strip tracking params + fragment + trailing slash for comparison."""
    u = u.strip().strip("\"'<>()[]{},.")
    if not u:
        return u
    try:
        p = urlparse(u)
        q = [(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True)
             if k.lower() not in TRACKING_PARAMS]
        new = p._replace(query=urlencode(q), fragment="")
        s = urlunparse(new)
        return s.rstrip("/")
    except Exception:
        return u


def collect_archived_urls() -> set[str]:
    out: set[str] = set()
    if not ARCHIVE.exists():
        return out
    for md in ARCHIVE.glob("*.md"):
        try:
            text = md.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        m = FRONTMATTER_RE.match(text)
        if not m:
            continue
        for url_match in URL_FIELD_RE.finditer(m.group(1)):
            v = url_match.group(1).strip().strip("\"'")
            if v and v != '""' and not v.lower().startswith("none"):
                out.add(normalize_url(v))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("urls", nargs="*")
    ap.add_argument("--json", action="store_true", help="JSON output")
    args = ap.parse_args()

    if not args.urls:
        print("usage: archive-dup-check.py <url>...", file=sys.stderr)
        return 0

    try:
        archived = collect_archived_urls()
    except Exception as e:
        print(f"scan failed: {e}", file=sys.stderr)
        return 2

    results = []
    any_new = False
    for url in args.urls:
        norm = normalize_url(url)
        is_archived = norm in archived
        results.append({"url": url, "archived": is_archived, "normalized": norm})
        if not is_archived:
            any_new = True

    if args.json:
        print(json.dumps({"results": results, "any_new": any_new}, indent=2))
    else:
        for r in results:
            mark = "✅ archived" if r["archived"] else "❌ NEW"
            print(f"{mark}  {r['url']}")
        print(f"\n[total {len(args.urls)}, archived {sum(1 for r in results if r['archived'])}, new {sum(1 for r in results if not r['archived'])}]")

    return 1 if any_new else 0


if __name__ == "__main__":
    sys.exit(main())

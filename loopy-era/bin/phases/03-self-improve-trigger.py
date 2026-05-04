#!/usr/bin/env python3
"""03 self_improve_trigger — count signals waiting in pending/.

Reuses the existing T6 capture: ~/.claude/.comad/pending/*.json (already
populated by Stop hook on every fix:/feat:/bugfix: commit). This phase
only TALLIES the signals; the actual analysis happens in phase 04 worker.

Stdout: {status, output:{pending_count, recurring_count, sample_signals}}
"""
from __future__ import annotations

import json
import pathlib
import re
import sys


def main() -> int:
    payload = json.loads(sys.stdin.read() or "{}")
    loopy = pathlib.Path(payload.get("loopy_dir",
                                     str(pathlib.Path.home() / ".comad/loopy-era")))
    pending_dir = loopy / "pending"  # symlink to ~/.claude/.comad/pending
    if not pending_dir.exists():
        out = {"status": "noop", "output": {"reason": "no pending directory"}}
        print(json.dumps(out, ensure_ascii=False))
        return 0

    pending = sorted(pending_dir.glob("*.json"))
    pending_count = len(pending)

    # Count recurring patterns from feedback memory
    home = pathlib.Path.home()
    recurring_count = 0
    seen_pattern = re.compile(r"Seen\s+([2-9]|[1-9]\d+)\s*회")
    mem_dir = home / ".claude" / "projects"
    if mem_dir.exists():
        for fb in mem_dir.glob("*/memory/feedback_*.md"):
            try:
                if seen_pattern.search(fb.read_text(encoding="utf-8", errors="replace")):
                    recurring_count += 1
            except OSError:
                pass

    sample = []
    for p in pending[:3]:
        try:
            obj = json.loads(p.read_text())
            sample.append({
                "commit": (obj.get("commit") or "")[:12],
                "subject": (obj.get("subject") or "")[:80],
                "kind": obj.get("kind"),
            })
        except (OSError, json.JSONDecodeError):
            continue

    out = {
        "status": "ok",
        "output": {
            "pending_count": pending_count,
            "recurring_count": recurring_count,
            "sample_signals": sample,
        },
        "summary": f"signals: pending={pending_count}, recurring={recurring_count}",
    }
    print(json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""05 verify_initial — measure l6_blocker_count.

Definition of l6_blocker_count for our setup:
  pending_count          (unprocessed fix:/feat: signals)
+ recurring_count        (feedback patterns Seen >= 2, excl. promoted & non-promotable)
+ qa_evidence_failures   (.qa-evidence.json verdicts that are not PASS in tracked projects — best-effort)
= l6_blocker_count

Stdout: {status, output:{metric_name, metric_value, breakdown}}
"""
from __future__ import annotations

import json
import pathlib
import re
import sys


def count_qa_evidence_failures() -> int:
    base = pathlib.Path.home() / "Programmer"
    if not base.exists():
        return 0
    n = 0
    try:
        # Best effort: only check 01-comad / 06-comad_codex / direct subdirs of Programmer
        for repo_root in (base / "01-comad", base / "06-comad_codex"):
            if not repo_root.exists():
                continue
            for qa in repo_root.rglob(".qa-evidence.json"):
                # Skip backups
                if ".bak" in str(qa):
                    continue
                try:
                    obj = json.loads(qa.read_text(encoding="utf-8"))
                    verdict = (obj.get("verdict") or "").upper()
                    if verdict and verdict != "PASS":
                        n += 1
                except (OSError, json.JSONDecodeError):
                    pass
    except OSError:
        pass
    return n


def main() -> int:
    payload = json.loads(sys.stdin.read() or "{}")
    loopy = pathlib.Path(payload.get("loopy_dir",
                                     str(pathlib.Path.home() / ".comad/loopy-era")))
    pending_dir = loopy / "pending"
    pending_count = sum(1 for _ in pending_dir.glob("*.json")) if pending_dir.exists() else 0

    seen_pat = re.compile(r"Seen\s+([2-9]|[1-9]\d+)\s*회")
    # A pattern already promoted to a HARD hook ("승격 완료"/"승격됨") is enforced
    # by that hook and is no longer an OPEN blocker. Excluding it keeps
    # l6_blocker_count reachable to 0 — otherwise append-only feedback memory
    # makes recurring permanent and the stopping_threshold unreachable.
    # (Must stay identical to 03-self-improve-trigger.py.)
    resolved_pat = re.compile(r"승격\s*완료|승격됨")
    # Exclude patterns explicitly declared NON-promotable ("grep 비대상" /
    # "패턴 아님") in their HARD 훅 후보 section — they have no grep-detectable
    # signature, can never become a HARD hook, and would otherwise be permanent
    # blockers. (Must stay identical to 03-self-improve-trigger.py.)
    not_promotable_pat = re.compile(r"grep[^\n]*비대상|패턴\s*아님")
    recurring_count = 0
    mem_dir = pathlib.Path.home() / ".claude/projects"
    if mem_dir.exists():
        for fb in mem_dir.glob("*/memory/feedback_*.md"):
            try:
                text = fb.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if (seen_pat.search(text)
                    and not resolved_pat.search(text)
                    and not not_promotable_pat.search(text)):
                recurring_count += 1

    qa_fail = count_qa_evidence_failures()

    metric = pending_count + recurring_count + qa_fail
    out = {
        "status": "ok",
        "output": {
            "metric_name": "l6_blocker_count",
            "metric_value": metric,
            "breakdown": {
                "pending_count": pending_count,
                "recurring_count": recurring_count,
                "qa_evidence_failures": qa_fail,
            },
        },
        "summary": f"l6_blocker_count={metric} (p={pending_count} r={recurring_count} q={qa_fail})",
    }
    print(json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())

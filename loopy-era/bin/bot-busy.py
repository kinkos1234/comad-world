#!/usr/bin/env python3
"""bot-busy — is the active bot session ACTUALLY executing (not just alive)?

Exit 0 = BUSY  (caller should skip / defer).
Exit 1 = idle / dead / no lock  (caller should PROCEED).

Why: the legacy mutex skipped whenever the active-bot PID was merely *alive*.
But ccc/ccd are persistent 24/7 Discord daemons, so that blocked the nightly
crons (auto-dream, nightly-audit) FOREVER. Instead we measure ACTIVITY: CPU-time
consumed by the bot process *tree* over a short sample. An idle session waiting
for Discord messages burns ~0 CPU; one actively processing a turn (tool exec,
parsing, streaming) burns measurably more.

On any uncertainty we return 1 (proceed) — the failure we are fixing was
over-blocking, so err toward running.

Tunables:
  COMAD_BOT_BUSY_CPU     CPU-seconds threshold over the sample (default 0.5)
  COMAD_BOT_BUSY_SAMPLE  wall-clock sample seconds (default 2.0)
"""
from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys
import time

ACTIVE_BOT = pathlib.Path(os.environ.get("HOME", "/")) / ".comad" / "active-bot.json"
THRESH = float(os.environ.get("COMAD_BOT_BUSY_CPU", "0.5"))
SAMPLE = float(os.environ.get("COMAD_BOT_BUSY_SAMPLE", "2.0"))


def _cputime_to_s(t: str) -> float:
    t = t.strip()
    if not t:
        return 0.0
    d = 0.0
    if "-" in t:            # DD-HH:MM:SS
        dd, t = t.split("-", 1)
        d = float(dd) * 86400
    s = 0.0
    for p in t.split(":"):  # HH:MM:SS | MM:SS.ss | SS.ss
        try:
            s = s * 60 + float(p)
        except ValueError:
            return 0.0
    return d + s


def _tree_cpu(pid: str) -> float | None:
    """Cumulative CPU seconds for pid + its descendants (tool subprocesses)."""
    try:
        out = subprocess.run(["ps", "-Ao", "pid,ppid,cputime"],
                             capture_output=True, text=True, timeout=5).stdout
    except Exception:
        return None
    rows = [r.split(None, 2) for r in out.splitlines()[1:] if r.strip()]
    kids = {str(pid)}
    for _ in range(5):  # gather descendants (bounded depth)
        for r in rows:
            if len(r) >= 3 and r[1] in kids:
                kids.add(r[0])
    total = 0.0
    for r in rows:
        if len(r) >= 3 and r[0] in kids:
            total += _cputime_to_s(r[2])
    return total


def main() -> int:
    try:
        pid = json.loads(ACTIVE_BOT.read_text()).get("pid")
    except Exception:
        return 1  # no / invalid lock → proceed
    if not pid:
        return 1
    try:
        os.kill(int(pid), 0)
    except Exception:
        return 1  # dead → proceed
    a = _tree_cpu(pid)
    if a is None:
        return 1  # cannot measure → proceed (never block forever)
    time.sleep(SAMPLE)
    b = _tree_cpu(pid)
    if b is None:
        return 1
    return 0 if (b - a) > THRESH else 1


if __name__ == "__main__":
    sys.exit(main())

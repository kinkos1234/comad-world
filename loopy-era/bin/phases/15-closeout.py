#!/usr/bin/env python3
"""15 closeout — append a row to results.tsv summarizing the cycle.

results.tsv columns are inherited from harness-report (Phase 1 of the
earlier session). We add `notes` = "loopy:iter-N (verdict)".

Stdout: {status, output:{row_appended, score}}
"""
from __future__ import annotations

import datetime
import json
import pathlib
import subprocess
import sys


HARNESS_REPORT = pathlib.Path.home() / ".claude/skills/harness-report/bin/harness-report.py"
KB_BIN = pathlib.Path.home() / ".claude/skills/comad-memory/bin"


def kb_maintain() -> dict:
    """Run incremental embed + dry-run consolidate. Soft-fail."""
    result: dict = {"embed": None, "consolidate": None}
    embed = KB_BIN / "embed.py"
    if embed.exists():
        try:
            r = subprocess.run([sys.executable, str(embed)],
                              capture_output=True, text=True, timeout=120)
            try:
                result["embed"] = json.loads((r.stdout or "").strip().splitlines()[-1])
            except (json.JSONDecodeError, IndexError):
                result["embed"] = {"exit": r.returncode,
                                  "stderr": (r.stderr or "")[-200:]}
        except (subprocess.TimeoutExpired, OSError) as e:
            result["embed"] = {"reason": f"embed: {e}"}

    consolidate = KB_BIN / "consolidate.py"
    if consolidate.exists():
        try:
            r = subprocess.run([sys.executable, str(consolidate)],
                              capture_output=True, text=True, timeout=120)
            try:
                obj = json.loads(r.stdout or "{}")
                result["consolidate"] = {
                    "candidates": obj.get("candidates"),
                    "buckets": obj.get("buckets"),
                    "applied": obj.get("applied"),
                }
            except json.JSONDecodeError:
                result["consolidate"] = {"exit": r.returncode}
        except (subprocess.TimeoutExpired, OSError) as e:
            result["consolidate"] = {"reason": f"consolidate: {e}"}
    return result


def main() -> int:
    payload = json.loads(sys.stdin.read() or "{}")
    state = payload.get("state") or {}
    iteration = payload.get("iteration", 0)
    metric_value = state.get("current_metric_value")
    stopping = state.get("stopping_condition", False)
    verdict = "DONE" if stopping else "ACTIVE"
    notes = f"loopy:iter-{iteration} {verdict} blocker={metric_value}"

    kb = kb_maintain()

    # Defer to harness-report.py — it already knows how to compose the TSV row
    # from the global SoT. We pass --notes; it does the measure + append.
    if HARNESS_REPORT.exists():
        try:
            r = subprocess.run(
                [sys.executable, str(HARNESS_REPORT), "--notes", notes],
                capture_output=True, text=True, timeout=30,
            )
            out = {
                "status": "ok" if r.returncode in (0, 1) else "fail",
                "output": {
                    "row_appended": True,
                    "harness_exit": r.returncode,
                    "tail": (r.stdout or "")[-500:],
                    "kb": kb,
                },
                "summary": f"results.tsv +1 ({notes})",
            }
        except (subprocess.TimeoutExpired, OSError) as e:
            out = {"status": "fail",
                   "output": {"reason": f"harness-report invocation: {e}"},
                   "summary": "closeout fail"}
    else:
        # Fallback: append a minimal row directly
        results = pathlib.Path.home() / ".comad/loopy-era/results.tsv"
        ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
        try:
            need_header = not results.exists() or results.stat().st_size == 0
            with results.open("a") as f:
                if need_header:
                    f.write("ts\titeration\tmetric\tnotes\n")
                f.write(f"{ts}\t{iteration}\t{metric_value}\t{notes}\n")
            out = {
                "status": "ok",
                "output": {"row_appended": True, "fallback": True, "kb": kb},
                "summary": f"results.tsv (fallback) +1",
            }
        except OSError as e:
            out = {"status": "fail",
                   "output": {"reason": str(e)},
                   "summary": "closeout fail"}

    print(json.dumps(out, ensure_ascii=False))
    return 0 if out["status"] == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())

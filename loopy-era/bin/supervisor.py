#!/usr/bin/env python3
"""loopy-era supervisor — 15-phase orchestrator (Codex Harness System port).

Single source of truth at ~/.comad/loopy-era/. Both Claude Code and Codex
sessions invoke this same supervisor; phase workers under bin/phases/ run
independent of which LLM the user chose.

Subcommands:
    supervisor.py status         show state.json summary
    supervisor.py tick           run one full PHASE_ORDER cycle
    supervisor.py tick --dry-run rehearse phases without state mutation
    supervisor.py phase <name>   run a single phase (debug)
    supervisor.py reset --force  reset state to iteration 0 (debug)

Exit codes:
    0  cycle / phase completed (or skip is intentional)
    1  cycle / phase failed
    2  another supervisor running (lock held)
    64 usage error

Phase contract:
    Each phase worker lives at bin/phases/<NN-name>.{py,sh}.
    Stdin:  JSON of {state, iteration, scope}
    Stdout: JSON of {status, summary, output, ...}
    Exit:   0 = ok, 1 = fail, 2 = skip (intentional, e.g. team_plan when
            blocker_count == 0)
    Missing worker → supervisor logs {"status": "noop", "reason": "no worker"}
    and continues. This is intentional: phases can be implemented incrementally.
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import pathlib
import subprocess
import sys
import time

LOOPY = pathlib.Path(os.environ.get("COMAD_LOOPY_DIR",
                                     str(pathlib.Path.home() / ".comad/loopy-era")))
STATE_FILE = LOOPY / "state.json"
LOCK_FILE = LOOPY / ".supervisor.lock"
LOG_FILE = LOOPY / "logs/supervisor.log"
METRICS_FILE = LOOPY / "metrics.jsonl"
RESULTS_FILE = LOOPY / "results.tsv"
PHASE_DIR = LOOPY / "bin/phases"
HISTORY_DIR = LOOPY / "phase_history"

PHASE_ORDER = [
    "01-init-project",
    "02-qa-scenario-gen",
    "03-self-improve-trigger",
    "04-self-improve-worker-initial",
    "05-verify-initial",
    "06-adversarial-review-initial",
    "07-team-plan",
    "08-team-execute",
    "09-qa-cycle",
    "10-qa-fix-retry",
    "11-inject-adversarial-findings",
    "12-self-improve-worker-adversarial",
    "13-verify-final",
    "14-adversarial-review-final",
    "15-closeout",
]

PHASE_TIMEOUT = {
    "04-self-improve-worker-initial": 2400,
    "12-self-improve-worker-adversarial": 2400,
    "08-team-execute": 1800,
    "09-qa-cycle": 1200,
    "10-qa-fix-retry": 1200,
}
DEFAULT_TIMEOUT = 600


def now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def log(msg: str) -> None:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with LOG_FILE.open("a") as f:
        f.write(f"[{now_iso()}] {msg}\n")


# ─── lockfile (single supervisor) ───────────────────────────────────────────
def acquire_lock() -> bool:
    LOOPY.mkdir(parents=True, exist_ok=True)
    if LOCK_FILE.exists():
        try:
            pid = int(LOCK_FILE.read_text().strip())
            os.kill(pid, 0)
            return False  # alive holder
        except (ValueError, ProcessLookupError, PermissionError, OSError):
            LOCK_FILE.unlink(missing_ok=True)
    LOCK_FILE.write_text(str(os.getpid()))
    return True


def release_lock() -> None:
    try:
        if LOCK_FILE.exists() and int(LOCK_FILE.read_text().strip()) == os.getpid():
            LOCK_FILE.unlink()
    except (ValueError, OSError):
        pass


# ─── state I/O ──────────────────────────────────────────────────────────────
def read_state() -> dict:
    if not STATE_FILE.exists():
        return {"schema_version": "0.1", "iteration": 0, "status": "uninitialized"}
    return json.loads(STATE_FILE.read_text())


def write_state(state: dict, dry_run: bool = False) -> None:
    if dry_run:
        log(f"dry-run: skip state write ({state.get('status')})")
        return
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n")


def append_metrics(record: dict) -> None:
    METRICS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with METRICS_FILE.open("a") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def save_phase_output(iteration: int, phase: str, output: dict) -> pathlib.Path:
    iter_dir = HISTORY_DIR / f"iter-{iteration:04d}"
    iter_dir.mkdir(parents=True, exist_ok=True)
    out_path = iter_dir / f"{phase}.json"
    out_path.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n")
    return out_path


# ─── phase invocation ───────────────────────────────────────────────────────
def find_worker(phase: str) -> pathlib.Path | None:
    for ext in (".py", ".sh"):
        p = PHASE_DIR / f"{phase}{ext}"
        if p.exists() and os.access(p, os.X_OK):
            return p
    return None


def call_phase(phase: str, state: dict, iteration: int, scope: dict) -> dict:
    worker = find_worker(phase)
    if not worker:
        log(f"phase {phase}: no worker (noop)")
        return {
            "status": "noop",
            "reason": "no worker installed",
            "phase": phase,
            "iteration": iteration,
        }

    payload = json.dumps({
        "state": state,
        "iteration": iteration,
        "scope": scope,
        "loopy_dir": str(LOOPY),
    }, ensure_ascii=False)

    timeout = PHASE_TIMEOUT.get(phase, DEFAULT_TIMEOUT)
    cmd = [str(worker)] if worker.suffix == ".sh" else ["python3", str(worker)]
    t0 = time.time()
    try:
        result = subprocess.run(
            cmd,
            input=payload,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(LOOPY),
        )
    except subprocess.TimeoutExpired:
        log(f"phase {phase}: TIMEOUT after {timeout}s")
        return {
            "status": "fail", "reason": "timeout",
            "phase": phase, "iteration": iteration,
            "duration_s": timeout,
        }
    duration = round(time.time() - t0, 2)

    # parse JSON output (last JSON object on stdout)
    output = None
    stdout = (result.stdout or "").strip()
    if stdout:
        try:
            output = json.loads(stdout)
        except json.JSONDecodeError:
            for line in reversed(stdout.splitlines()):
                line = line.strip()
                if line.startswith("{") and line.endswith("}"):
                    try:
                        output = json.loads(line)
                        break
                    except json.JSONDecodeError:
                        continue

    if output is None:
        output = {"status": "fail", "reason": "non-JSON output",
                  "stdout_tail": stdout[-400:],
                  "stderr_tail": (result.stderr or "")[-400:]}

    output.setdefault("phase", phase)
    output.setdefault("iteration", iteration)
    output["duration_s"] = duration
    output["exit_code"] = result.returncode

    if result.returncode == 2:
        output["status"] = output.get("status", "skip")
    elif result.returncode != 0 and output.get("status") not in ("fail", "skip"):
        output["status"] = "fail"

    log(f"phase {phase}: {output.get('status')} ({duration}s) exit={result.returncode}")
    return output


# ─── conditional skip rules ────────────────────────────────────────────────
def should_skip(phase: str, state: dict, history: dict) -> tuple[bool, str]:
    """Encodes the supervisor-level branching the upstream Codex Harness uses.

    Returns (skip, reason).
    """
    if phase in ("07-team-plan", "08-team-execute"):
        rev = history.get("06-adversarial-review-initial") or {}
        blockers = rev.get("output", {}).get("blocker_count")
        if blockers == 0 or rev.get("status") == "noop":
            return True, "blocker_count == 0 (or review skipped)"
    if phase == "10-qa-fix-retry":
        qa = history.get("09-qa-cycle") or {}
        if qa.get("status") in ("ok", "noop", "skip"):
            return True, "qa_cycle did not fail"
    if phase == "12-self-improve-worker-adversarial":
        rev = history.get("06-adversarial-review-initial") or {}
        findings = rev.get("output", {}).get("findings", []) or []
        if not findings:
            return True, "no adversarial findings to inject"
    return False, ""


# ─── tick ───────────────────────────────────────────────────────────────────
def cmd_tick(args: argparse.Namespace) -> int:
    if not args.dry_run and not acquire_lock():
        sys.stderr.write("supervisor: another instance running, refusing\n")
        return 2
    try:
        state = read_state()
        iteration = state.get("iteration", 0) + 1
        started_at = now_iso()
        state.update({
            "iteration": iteration,
            "status": "running",
            "last_started_at": started_at,
            "current_phase": None,
        })
        write_state(state, args.dry_run)
        log(f"=== tick start: iteration={iteration} dry_run={args.dry_run} ===")

        history: dict[str, dict] = {}
        cycle = {
            "iteration": iteration,
            "started_at": started_at,
            "phases": [],
            "summary": {},
            "dry_run": args.dry_run,
        }

        for phase in PHASE_ORDER:
            skip, reason = should_skip(phase, state, history)
            if skip:
                rec = {"status": "skip", "phase": phase, "iteration": iteration,
                       "reason": reason, "duration_s": 0.0}
            else:
                state["current_phase"] = phase
                write_state(state, args.dry_run)
                rec = call_phase(phase, state, iteration,
                                 scope={"reason": "tick"})
            history[phase] = rec
            cycle["phases"].append(rec)
            if not args.dry_run:
                save_phase_output(iteration, phase, rec)

        # Aggregate metrics (verify_final → current_metric_value)
        verify_final = history.get("13-verify-final") or {}
        metric_value = verify_final.get("output", {}).get("metric_value")
        if metric_value is None:
            verify_initial = history.get("05-verify-initial") or {}
            metric_value = verify_initial.get("output", {}).get("metric_value")

        threshold = state.get("stopping_threshold", 0)
        stopping = False
        try:
            stopping = metric_value is not None and float(metric_value) <= float(threshold)
        except (TypeError, ValueError):
            pass

        completed_at = now_iso()
        state.update({
            "status": "completed" if stopping else "active",
            "current_phase": None,
            "last_phase": PHASE_ORDER[-1],
            "last_completed_at": completed_at,
            "current_metric_value": metric_value,
            "stopping_condition": stopping,
            "team_plan": history.get("07-team-plan", {"status": "skip"}),
            "qa_cycle": history.get("09-qa-cycle", {"status": "unknown"}),
        })
        write_state(state, args.dry_run)
        cycle["summary"] = {
            "completed_at": completed_at,
            "metric_value": metric_value,
            "stopping_condition": stopping,
            "phase_status": {p: rec.get("status") for p, rec in history.items()},
        }
        if not args.dry_run:
            append_metrics({
                "ts": completed_at,
                "iteration": iteration,
                "metric_name": state.get("metric_name"),
                "metric_value": metric_value,
                "stopping_condition": stopping,
                "phase_status": cycle["summary"]["phase_status"],
            })

        if args.json:
            print(json.dumps(cycle, ensure_ascii=False, indent=2))
        else:
            print(f"loopy-era tick: iter={iteration} status={state['status']} "
                  f"metric={metric_value} stopping={stopping}")
            for p, rec in history.items():
                print(f"  {p}: {rec.get('status')} ({rec.get('duration_s', 0)}s)")

        log(f"=== tick end: iteration={iteration} status={state['status']} ===")
        return 0
    finally:
        release_lock()


# ─── status / phase / reset ────────────────────────────────────────────────
def cmd_status(args: argparse.Namespace) -> int:
    state = read_state()
    if args.json:
        print(json.dumps(state, ensure_ascii=False, indent=2))
        return 0
    print(f"loopy-era state — iteration {state.get('iteration', 0)}")
    print(f"  status:           {state.get('status')}")
    print(f"  metric:           {state.get('metric_name')}={state.get('current_metric_value')}")
    print(f"  stopping:         {state.get('stopping_condition')}")
    print(f"  last_phase:       {state.get('last_phase')}")
    print(f"  last_started_at:  {state.get('last_started_at')}")
    print(f"  last_completed:   {state.get('last_completed_at')}")
    return 0


def cmd_phase(args: argparse.Namespace) -> int:
    if args.name not in PHASE_ORDER:
        print(f"unknown phase: {args.name}", file=sys.stderr)
        print(f"valid: {', '.join(PHASE_ORDER)}", file=sys.stderr)
        return 64
    state = read_state()
    iteration = state.get("iteration", 0)
    rec = call_phase(args.name, state, iteration, scope={"reason": "manual"})
    print(json.dumps(rec, ensure_ascii=False, indent=2))
    return 0 if rec.get("status") in ("ok", "noop", "skip") else 1


def cmd_reset(args: argparse.Namespace) -> int:
    if not args.force:
        print("refuse: pass --force to confirm reset", file=sys.stderr)
        return 64
    state = {
        "schema_version": "0.1",
        "iteration": 0,
        "status": "uninitialized",
        "metric_name": "l6_blocker_count",
        "current_metric_value": None,
        "stopping_condition": False,
        "stopping_threshold": 0,
        "last_started_at": None,
        "last_completed_at": None,
        "last_phase": None,
        "current_phase": None,
        "team_plan": {"status": "skip", "reason": "reset"},
        "qa_cycle": {"status": "unknown"},
        "next_run_at": None,
        "created_at": now_iso(),
        "notes": f"reset via supervisor.py at {now_iso()}",
    }
    write_state(state)
    print("loopy-era state reset to iteration 0")
    return 0


# ─── main ───────────────────────────────────────────────────────────────────
def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd")

    p_status = sub.add_parser("status")
    p_status.add_argument("--json", action="store_true")
    p_status.set_defaults(func=cmd_status)

    p_tick = sub.add_parser("tick")
    p_tick.add_argument("--dry-run", action="store_true")
    p_tick.add_argument("--json", action="store_true")
    p_tick.set_defaults(func=cmd_tick)

    p_phase = sub.add_parser("phase")
    p_phase.add_argument("name")
    p_phase.set_defaults(func=cmd_phase)

    p_reset = sub.add_parser("reset")
    p_reset.add_argument("--force", action="store_true")
    p_reset.set_defaults(func=cmd_reset)

    args = ap.parse_args()
    if not getattr(args, "func", None):
        ap.print_help(sys.stderr)
        return 64
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())

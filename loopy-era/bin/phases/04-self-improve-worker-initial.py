#!/usr/bin/env python3
"""04 self_improve_worker_initial — analyze ONE pending signal via LLM.

Minimal demonstrator for Phase F integration. Picks the oldest unprocessed
pending JSON, asks the env-selected LLM to extract a generalized pattern,
and writes the raw response to phase_history (no destructive mutation).

A future enhancement is the real self-improve-worker (worktree + 4-check
verification). This minimal version proves the LLM dispatch loop works.

Stdout: {status, output:{processed_signal, pattern_summary, llm_provider}}
Exit 2 = skip (no signals).
"""
from __future__ import annotations

import datetime
import json
import os
import pathlib
import sqlite3
import subprocess
import sys

KB_DB = pathlib.Path.home() / ".claude/.comad/memory/facts.sqlite"


def now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def kb_persist_pattern(summary_line: str, signal_name: str,
                       commit_sha: str, subject: str,
                       extracted_by: str) -> dict:
    """Insert one pattern fact into kb_facts. Soft-fail (returns dict)."""
    if not summary_line or summary_line.upper() == "NONE":
        return {"persisted": False, "reason": "empty or NONE"}
    if not KB_DB.exists():
        return {"persisted": False, "reason": "kb db missing"}
    try:
        conn = sqlite3.connect(str(KB_DB))
        try:
            ts = now_iso()
            source_id = f"loopy-pending:{signal_name}"
            existing = conn.execute(
                "SELECT 1 FROM kb_provenance WHERE source_kind=? AND source_id=? LIMIT 1",
                ("transcript", source_id),
            ).fetchone()
            if existing:
                return {"persisted": False, "reason": "already extracted"}
            cur = conn.execute(
                """INSERT INTO kb_facts
                   (scope, kind, summary, body, source_ref, confidence,
                    created_at, updated_at, extracted_by, metadata_json)
                   VALUES ('global', 'pattern', ?, ?, ?, 1.0, ?, ?, ?, ?)""",
                (summary_line[:300], summary_line, source_id, ts, ts,
                 extracted_by,
                 json.dumps({"commit": commit_sha, "subject": subject},
                           ensure_ascii=False)),
            )
            fid = cur.lastrowid
            conn.execute(
                """INSERT INTO kb_ontology (fact_id, domain, category,
                       tags_json, classified_at, classifier)
                   VALUES (?, 'loopy', 'pattern', '[]', ?, ?)""",
                (fid, ts, extracted_by),
            )
            conn.execute(
                """INSERT OR IGNORE INTO kb_provenance
                   (fact_id, source_kind, source_id, captured_at, snippet)
                   VALUES (?, 'transcript', ?, ?, ?)""",
                (fid, source_id, ts, summary_line[:200]),
            )
            conn.commit()
            return {"persisted": True, "fact_id": fid}
        finally:
            conn.close()
    except (sqlite3.Error, OSError) as e:
        return {"persisted": False, "reason": f"sqlite: {e}"}


def main() -> int:
    payload = json.loads(sys.stdin.read() or "{}")
    loopy = pathlib.Path(payload.get("loopy_dir",
                                     str(pathlib.Path.home() / ".comad/loopy-era")))
    pending_dir = loopy / "pending"
    if not pending_dir.exists():
        print(json.dumps({"status": "noop",
                          "output": {"reason": "no pending dir"}}))
        return 0

    candidates = sorted(pending_dir.glob("*.json"))
    if not candidates:
        print(json.dumps({"status": "skip",
                          "output": {"reason": "no pending signals"}}))
        return 2

    sig = candidates[0]
    try:
        obj = json.loads(sig.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        print(json.dumps({"status": "fail",
                          "output": {"reason": f"could not read {sig.name}: {e}"}}))
        return 1

    prompt = (
        "다음은 한 git fix/feat 커밋의 raw JSON 입니다. 일반화 가능한 실수 패턴을 "
        "분석해 아래 JSON 한 줄로만 답하세요 (다른 텍스트 절대 금지):\n"
        '{"pattern": "<일반화 가능한 실수 패턴 한 줄, 없으면 NONE>", '
        '"general": <true=다른 프로젝트에도 적용|false=이 프로젝트 특수>, '
        '"hard_candidate": <true=반복되면 자동 차단 훅 만들 가치 있음, 아니면 false>, '
        '"reason": "<한 줄 근거>"}\n\n'
        f"{json.dumps(obj, ensure_ascii=False, indent=2)[:2000]}"
    )

    dispatcher = loopy / "bin/llm-dispatch.sh"
    if not dispatcher.exists():
        print(json.dumps({"status": "fail",
                          "output": {"reason": "llm-dispatch.sh missing"}}))
        return 1

    try:
        result = subprocess.run(
            [str(dispatcher)],
            input=prompt,
            capture_output=True,
            text=True,
            timeout=180,
        )
    except subprocess.TimeoutExpired:
        print(json.dumps({"status": "fail",
                          "output": {"reason": "llm-dispatch timeout 180s"}}))
        return 1

    # R3a: structured analysis (pattern / generality / hard-candidate).
    raw_last = (result.stdout or "").strip().splitlines()
    raw_last = raw_last[-1].strip() if raw_last else ""
    try:
        analysis = json.loads(raw_last)
        if not isinstance(analysis, dict):
            analysis = {"pattern": raw_last}
    except (json.JSONDecodeError, ValueError):
        analysis = {"pattern": raw_last}  # fallback: treat line as the pattern
    pattern = (analysis.get("pattern") or "").strip()
    summary_line = "" if pattern.upper() == "NONE" else pattern
    is_general = bool(analysis.get("general"))
    is_hard_candidate = bool(analysis.get("hard_candidate"))

    extracted_by = os.environ.get("COMAD_LOOPY_LLM", "auto")
    kb = kb_persist_pattern(
        summary_line=summary_line,
        signal_name=sig.name,
        commit_sha=(obj.get("commit") or "")[:40],
        subject=(obj.get("subject") or "")[:120],
        extracted_by=extracted_by,
    )

    # success = the LLM responded (analysis done) — a NONE pattern is still a
    # valid, complete analysis, so it must count as ok (else it never archives).
    status = "ok" if (result.returncode == 0 and raw_last) else "fail"

    # Drain the queue: a successfully-analyzed signal moves to _processed/ so
    # pending self-clears (work-queue, not a defect count). On failure it stays
    # for retry next tick. [loopy l6_blocker fix 2026-05-30]
    archived = False
    if status == "ok":
        try:
            processed_dir = pending_dir / "_processed"
            processed_dir.mkdir(parents=True, exist_ok=True)
            sig.rename(processed_dir / sig.name)
            archived = True
        except OSError:
            archived = False

    # R3a (A+C): phase04 stays light, but a genuine *generalizable + HARD-worthy*
    # pattern is escalated as a DECISION (promote?) — heavy cross-cutting analysis
    # is the nightly-audit's job. Deduped (source+title), low urgency, soft-fail.
    escalated = None
    if summary_line and is_general and is_hard_candidate:
        try:
            sys.path.insert(0, str(pathlib.Path.home() / ".claude/hooks/lib"))
            import decisions as _dec
            escalated = _dec.record_decision(
                source="loopy-phase04",
                title=f"패턴 후보: {summary_line[:80]}",
                detail=(f"commit {(obj.get('commit') or '')[:12]} "
                        f"({(obj.get('subject') or '')[:90]}) — "
                        f"{(analysis.get('reason') or '')[:120]}"),
                options=["comad-promote로 HARD 승격", "feedback 메모리만 기록",
                         "무시(특수 케이스)"],
                urgency="low",
            )
        except Exception:
            escalated = None

    out = {
        "status": status,
        "output": {
            "processed_signal": sig.name,
            "archived": archived,
            "commit": (obj.get("commit") or "")[:12],
            "subject": (obj.get("subject") or "")[:120],
            "pattern_summary": summary_line[:300],
            "general": is_general,
            "hard_candidate": is_hard_candidate,
            "escalated_decision": escalated,
            "llm_provider": extracted_by,
            "llm_exit": result.returncode,
            "kb": kb,
        },
        "summary": (f"analyzed 1 signal: {summary_line[:80]}"
                    if summary_line else "analyzed 1 signal: no pattern (NONE)"),
    }
    print(json.dumps(out, ensure_ascii=False))
    return 0 if out["status"] == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())

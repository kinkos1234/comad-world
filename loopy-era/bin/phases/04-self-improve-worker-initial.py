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
        "다음은 한 git fix/feat 커밋의 raw JSON 입니다. "
        "이 커밋이 보여주는 일반화 가능한 실수 패턴이 있는지 분석해 주세요. "
        "있다면 한 줄 요약으로, 없다면 'NONE' 한 단어로 답하세요. "
        "추가 prose 없이 한 줄만.\n\n"
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

    summary = (result.stdout or "").strip().splitlines()
    summary_line = summary[-1].strip() if summary else ""

    extracted_by = os.environ.get("COMAD_LOOPY_LLM", "auto")
    kb = kb_persist_pattern(
        summary_line=summary_line,
        signal_name=sig.name,
        commit_sha=(obj.get("commit") or "")[:40],
        subject=(obj.get("subject") or "")[:120],
        extracted_by=extracted_by,
    )

    out = {
        "status": "ok" if result.returncode == 0 and summary_line else "fail",
        "output": {
            "processed_signal": sig.name,
            "commit": (obj.get("commit") or "")[:12],
            "subject": (obj.get("subject") or "")[:120],
            "pattern_summary": summary_line[:300],
            "llm_provider": extracted_by,
            "llm_exit": result.returncode,
            "kb": kb,
        },
        "summary": f"analyzed 1 signal: {summary_line[:80]}" if summary_line else "no LLM output",
    }
    print(json.dumps(out, ensure_ascii=False))
    return 0 if out["status"] == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())

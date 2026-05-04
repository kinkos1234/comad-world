#!/usr/bin/env python3
"""kb-sleep-tick — Layer 1 of the memory-bank auto-loop.

Runs every 2h via LaunchAgent (com.comad.kb-sleep). Non-destructive.
LLM 호출 안 함 (rule-based + idempotent steps only).

작업 순서:
  1. extract-facts.py --regex-only  : 모든 ~/.claude/projects/*/memory/*.md → kb_facts (idempotent)
  2. embed.py                        : 새 fact 만 incremental embedding
  3. consolidate.py (no --apply)     : SUPPORTS edge 만 추가, destructive merge 없음
  4. dream_pending 플래그 갱신       : 라인 임계 또는 lastRun 경과 기준
  5. memory-log 게시                 : kinkos1234.github.io/_posts/YYYY-MM-DD-mem-log.md
                                       (메타정보만 — 본문 비공개)
  6. git push (best-effort, fail soft)

stdout: JSON {status, summary, kb_delta, threshold, published, git}
exit 0 = ok / 1 = fail (dispatch retry next tick)
"""
from __future__ import annotations

import datetime
import json
import os
import pathlib
import re
import shutil
import sqlite3
import subprocess
import sys
import time

HOME = pathlib.Path.home()
KB_DB = HOME / ".claude/.comad/memory/facts.sqlite"
KB_BIN = HOME / ".claude/skills/comad-memory/bin"
MEMORY_GLOB = HOME / ".claude/projects"
SLEEP_STATE = HOME / ".claude/.comad-sleep-state.json"
LOG_DIR = HOME / ".comad/loopy-era/logs"
SITE_REPO = HOME / "Programmer/03-web/kinkos1234.github.io"
SITE_POSTS = SITE_REPO / "_posts"

DREAM_LINE_THRESHOLD = 3500
DREAM_DAYS_THRESHOLD = 7

LOG_DIR.mkdir(parents=True, exist_ok=True)
TICK_LOG = LOG_DIR / "kb-sleep-tick.log"


def now_utc_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def now_utc_date() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")


def now_kst_iso() -> str:
    kst = datetime.timezone(datetime.timedelta(hours=9))
    return datetime.datetime.now(kst).strftime("%Y-%m-%d %H:%M KST")


def log(msg: str) -> None:
    line = f"[{now_utc_iso()}] {msg}\n"
    sys.stderr.write(line)
    try:
        with TICK_LOG.open("a", encoding="utf-8") as f:
            f.write(line)
    except OSError:
        pass


def kb_snapshot(conn: sqlite3.Connection) -> dict:
    """Capture quick stats for diffing across ticks."""
    def one(q: str) -> int:
        return conn.execute(q).fetchone()[0]
    return {
        "active_facts": one("SELECT COUNT(*) FROM kb_facts WHERE is_active=1"),
        "archived_facts": one("SELECT COUNT(*) FROM kb_facts WHERE is_active=0"),
        "embeddings": one(
            "SELECT COUNT(*) FROM kb_embeddings e JOIN kb_facts f ON f.id=e.fact_id WHERE f.is_active=1"
        ),
        "relations": one("SELECT COUNT(*) FROM kb_relations"),
        "kinds": dict(conn.execute(
            "SELECT kind, COUNT(*) FROM kb_facts WHERE is_active=1 GROUP BY kind"
        ).fetchall()),
        "domains": dict(conn.execute(
            """SELECT o.domain, COUNT(*) FROM kb_ontology o
               JOIN kb_facts f ON f.id=o.fact_id WHERE f.is_active=1 GROUP BY o.domain"""
        ).fetchall()),
        "rel_types": dict(conn.execute(
            "SELECT relation_type, COUNT(*) FROM kb_relations GROUP BY relation_type"
        ).fetchall()),
    }


def kb_recent_facts_added(conn: sqlite3.Connection, since_iso: str, limit: int = 20) -> list[dict]:
    rows = conn.execute(
        """SELECT id, kind, scope, summary, created_at, extracted_by
           FROM kb_facts WHERE is_active=1 AND created_at >= ?
           ORDER BY created_at DESC LIMIT ?""",
        (since_iso, limit),
    ).fetchall()
    return [{"id": r[0], "kind": r[1], "scope": r[2],
             "summary": r[3][:100], "created_at": r[4], "by": r[5]} for r in rows]


def diff_dict(a: dict, b: dict) -> dict:
    keys = set(a) | set(b)
    return {k: (b.get(k, 0) - a.get(k, 0)) for k in keys
            if (b.get(k, 0) - a.get(k, 0)) != 0}


def md_total_lines() -> int:
    n = 0
    for p in MEMORY_GLOB.glob("*/memory/*.md"):
        try:
            n += sum(1 for _ in p.open(encoding="utf-8", errors="replace"))
        except OSError:
            pass
    return n


def md_files_count() -> int:
    return sum(1 for _ in MEMORY_GLOB.glob("*/memory/*.md"))


def run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    log(f"$ {' '.join(cmd)}")
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def step_extract() -> dict:
    """Walk every memory/*.md and extract via regex (no LLM)."""
    extract = KB_BIN / "extract-facts.py"
    if not extract.exists():
        return {"status": "skip", "reason": "extract-facts.py missing"}
    extracted = 0
    skipped = 0
    failed = 0
    for md in sorted(MEMORY_GLOB.glob("*/memory/*.md")):
        # MEMORY.md has no extractable frontmatter facts; skip
        if md.name == "MEMORY.md":
            continue
        try:
            r = run([sys.executable, str(extract), "--source", str(md),
                     "--regex-only", "--scope", "global"], timeout=30)
            if r.returncode != 0:
                failed += 1
                continue
            try:
                obj = json.loads((r.stdout or "").strip().splitlines()[-1])
                extracted += int(obj.get("extracted") or 0)
                if obj.get("status") == "noop":
                    skipped += 1
            except (json.JSONDecodeError, IndexError):
                pass
        except (subprocess.TimeoutExpired, OSError):
            failed += 1
    return {"status": "ok", "extracted": extracted,
            "skipped_idempotent": skipped, "failed": failed}


def step_embed() -> dict:
    embed = KB_BIN / "embed.py"
    if not embed.exists():
        return {"status": "skip"}
    try:
        r = run([sys.executable, str(embed)], timeout=180)
        try:
            return json.loads((r.stdout or "").strip().splitlines()[-1])
        except (json.JSONDecodeError, IndexError):
            return {"status": "fail", "exit": r.returncode,
                    "stderr": (r.stderr or "")[-200:]}
    except (subprocess.TimeoutExpired, OSError) as e:
        return {"status": "fail", "reason": str(e)}


def step_consolidate() -> dict:
    cons = KB_BIN / "consolidate.py"
    if not cons.exists():
        return {"status": "skip"}
    try:
        r = run([sys.executable, str(cons)], timeout=120)  # dry-run, rule-only
        try:
            obj = json.loads(r.stdout or "{}")
            return {
                "status": obj.get("status", "ok"),
                "candidates": obj.get("candidates"),
                "buckets": obj.get("buckets"),
                "applied": obj.get("applied"),
            }
        except json.JSONDecodeError:
            return {"status": "fail", "exit": r.returncode}
    except (subprocess.TimeoutExpired, OSError) as e:
        return {"status": "fail", "reason": str(e)}


def load_sleep_state() -> dict:
    if not SLEEP_STATE.exists():
        return {}
    try:
        return json.loads(SLEEP_STATE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def save_sleep_state(state: dict) -> None:
    try:
        SLEEP_STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2),
                              encoding="utf-8")
    except OSError as e:
        log(f"sleep state write failed: {e}")


def days_since(iso: str | None) -> float:
    if not iso:
        return 999.0
    try:
        dt = datetime.datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return 999.0
    delta = datetime.datetime.now(datetime.timezone.utc) - dt
    return delta.total_seconds() / 86400.0


def update_dream_pending(state: dict, lines: int) -> dict:
    last_run = state.get("lastRun")
    days = days_since(last_run)
    pending = (lines >= DREAM_LINE_THRESHOLD) or (days >= DREAM_DAYS_THRESHOLD)
    state["dream_pending"] = bool(pending)
    state["dream_check"] = {
        "lines": lines,
        "line_threshold": DREAM_LINE_THRESHOLD,
        "days_since_dream": round(days, 1),
        "days_threshold": DREAM_DAYS_THRESHOLD,
        "checked_at": now_utc_iso(),
    }
    return state


# ─────────────────────────────────────────────────────────────────
# memory-log post writer
# ─────────────────────────────────────────────────────────────────

POST_HEADER = """---
layout: single
title: "Memory Log — {date}"
categories: [memory-log]
tags: [memory, kb-facts, auto]
permalink: /memory-log/{date}/
classes: wide
toc: true
toc_label: "Tick 목록"
read_time: false
share: false
comments: false
sidebar:
  nav: false
---

> 자동 생성된 메모리 변경이력. 본문은 비공개, 메타정보(파일/카운트/엣지/임계치)만 게시됩니다.
> 주기: 2시간마다 (LaunchAgent `com.comad.kb-sleep`).

"""

ENTRY_TEMPLATE = """## {kst} (tick #{tick_no})

**KB 변화**

| 항목 | 이전 | 이후 | Δ |
|---|---|---|---|
| active facts | {prev_active} | {now_active} | {d_active:+d} |
| relations | {prev_rel} | {now_rel} | {d_rel:+d} |
| embeddings | {prev_emb} | {now_emb} | {d_emb:+d} |

**워커 단계**

- extract: {extract_brief}
- embed: {embed_brief}
- consolidate: {cons_brief}

**메모리 임계치**

- `.md` 총 라인: **{md_lines}** / threshold {line_th} → {dream_flag}
- 마지막 dream: **{days_since_dream}일 전** / threshold {day_th}일

{recent_block}
---
"""


def render_recent_block(recent: list[dict]) -> str:
    if not recent:
        return ""
    lines = ["**이번 사이클 신규 facts**", ""]
    for f in recent[:10]:
        lines.append(f"- `#{f['id']}` [{f['kind']}] *{f['scope']}* — {f['summary']}…")
    return "\n".join(lines) + "\n"


def render_entry(prev: dict, now: dict, tick_no: int,
                 extract_r: dict, embed_r: dict, cons_r: dict,
                 md_lines: int, days_since_dream: float,
                 recent: list[dict]) -> str:
    d_active = now["active_facts"] - prev.get("active_facts", 0)
    d_rel = now["relations"] - prev.get("relations", 0)
    d_emb = now["embeddings"] - prev.get("embeddings", 0)

    extract_brief = (f"+{extract_r.get('extracted', 0)} new "
                    f"({extract_r.get('skipped_idempotent', 0)} idempotent skip, "
                    f"{extract_r.get('failed', 0)} fail)")
    embed_brief = (f"{embed_r.get('embedded', 0)} embedded"
                  + (f" / {embed_r.get('failed', 0)} fail" if embed_r.get('failed') else "")
                  + f" — {embed_r.get('status', 'unknown')}")
    cons_brief = (f"{cons_r.get('candidates', 0)} candidates "
                 f"({cons_r.get('buckets', 0)} buckets)")

    dream_flag = ("🌙 **dream pending**" if md_lines >= DREAM_LINE_THRESHOLD
                  else "✅ ok")

    return ENTRY_TEMPLATE.format(
        kst=now_kst_iso(), tick_no=tick_no,
        prev_active=prev.get("active_facts", 0), now_active=now["active_facts"], d_active=d_active,
        prev_rel=prev.get("relations", 0), now_rel=now["relations"], d_rel=d_rel,
        prev_emb=prev.get("embeddings", 0), now_emb=now["embeddings"], d_emb=d_emb,
        extract_brief=extract_brief, embed_brief=embed_brief, cons_brief=cons_brief,
        md_lines=md_lines, line_th=DREAM_LINE_THRESHOLD, dream_flag=dream_flag,
        days_since_dream=round(days_since_dream, 1), day_th=DREAM_DAYS_THRESHOLD,
        recent_block=render_recent_block(recent),
    )


def append_post(date: str, entry: str) -> dict:
    if not SITE_REPO.exists():
        return {"status": "skip", "reason": "site repo missing"}
    SITE_POSTS.mkdir(exist_ok=True)
    post_path = SITE_POSTS / f"{date}-mem-log.md"
    try:
        if post_path.exists():
            existing = post_path.read_text(encoding="utf-8")
            # split header from body
            m = re.match(r"^(---.*?---\n\n.*?\n)(.*)$", existing, re.DOTALL)
            if m:
                header_part, body_part = m.group(1), m.group(2)
            else:
                header_part = existing
                body_part = ""
            new_content = header_part + entry + body_part
        else:
            header = POST_HEADER.format(date=date)
            new_content = header + entry
        post_path.write_text(new_content, encoding="utf-8")
        return {"status": "ok", "path": str(post_path),
                "size_bytes": post_path.stat().st_size}
    except OSError as e:
        return {"status": "fail", "reason": str(e)}


def git_publish(date: str) -> dict:
    """git pull --rebase, add post, commit, push. Soft-fail."""
    if not (SITE_REPO / ".git").exists():
        return {"status": "skip", "reason": ".git missing"}
    if not shutil.which("git"):
        return {"status": "skip", "reason": "git not installed"}

    def g(*args: str, timeout: int = 30) -> subprocess.CompletedProcess:
        return subprocess.run(["git", "-C", str(SITE_REPO), *args],
                            capture_output=True, text=True, timeout=timeout)

    try:
        # Stash any unrelated user edits to be safe
        st = g("status", "--porcelain")
        dirty_other = any(
            ln and not ln.endswith(f"_posts/{date}-mem-log.md")
            for ln in (st.stdout or "").splitlines()
            if ln.strip()
        )
        stashed = False
        if dirty_other:
            r = g("stash", "push", "-m", f"kb-sleep-tick auto-stash {now_utc_iso()}")
            stashed = (r.returncode == 0 and "No local changes" not in (r.stdout + r.stderr))
            log(f"stash result rc={r.returncode} stashed={stashed}")

        r = g("pull", "--rebase", "--autostash", timeout=60)
        if r.returncode != 0:
            log(f"pull failed: {r.stderr[-200:]}")
            if stashed:
                g("stash", "pop")
            return {"status": "fail", "reason": "pull rebase failed",
                    "stderr": (r.stderr or "")[-200:]}

        post_rel = f"_posts/{date}-mem-log.md"
        r = g("add", post_rel)
        if r.returncode != 0:
            return {"status": "fail", "reason": "add failed",
                    "stderr": (r.stderr or "")[-200:]}

        r = g("diff", "--cached", "--quiet")
        if r.returncode == 0:
            # nothing to commit (post identical)
            if stashed:
                g("stash", "pop")
            return {"status": "noop", "reason": "no changes staged"}

        msg = f"chore(memory-log): tick {now_utc_iso()}"
        r = g("commit", "-m", msg)
        if r.returncode != 0:
            return {"status": "fail", "reason": "commit failed",
                    "stderr": (r.stderr or "")[-200:]}

        r = g("push", "origin", "HEAD", timeout=60)
        if r.returncode != 0:
            return {"status": "fail", "reason": "push failed",
                    "stderr": (r.stderr or "")[-300:]}

        if stashed:
            g("stash", "pop")
        return {"status": "ok", "commit_msg": msg}
    except subprocess.TimeoutExpired as e:
        return {"status": "fail", "reason": f"timeout: {e}"}
    except OSError as e:
        return {"status": "fail", "reason": str(e)}


def main() -> int:
    no_push = "--no-push" in sys.argv or os.environ.get("KB_SLEEP_NO_PUSH") == "1"
    started = time.time()
    log(f"=== kb-sleep-tick start (no_push={no_push}) ===")

    if not KB_DB.exists():
        print(json.dumps({"status": "fail", "reason": "kb db missing"}))
        return 1

    # Tick number — increment in sleep_state
    state = load_sleep_state()
    state.setdefault("kbSleepTickCount", 0)
    state["kbSleepTickCount"] += 1
    tick_no = state["kbSleepTickCount"]

    # Capture snapshot before
    conn = sqlite3.connect(str(KB_DB))
    try:
        prev = kb_snapshot(conn)
    finally:
        conn.close()
    log(f"prev: {prev}")

    cycle_started_at = now_utc_iso()

    # Run pipeline (each step is soft-fail)
    extract_r = step_extract()
    log(f"extract: {extract_r}")
    embed_r = step_embed()
    log(f"embed: {embed_r}")
    cons_r = step_consolidate()
    log(f"consolidate: {cons_r}")

    # Capture snapshot after
    conn = sqlite3.connect(str(KB_DB))
    try:
        now = kb_snapshot(conn)
        recent = kb_recent_facts_added(conn, cycle_started_at, limit=20)
    finally:
        conn.close()
    log(f"now: {now}")

    # Memory threshold
    md_lines = md_total_lines()
    state = update_dream_pending(state, md_lines)
    days_since_dream = state["dream_check"]["days_since_dream"]

    # Render + publish entry
    entry = render_entry(prev, now, tick_no, extract_r, embed_r, cons_r,
                        md_lines, days_since_dream, recent)
    publish_r = append_post(now_utc_date(), entry)
    log(f"publish: {publish_r.get('status')} {publish_r.get('path', '')}")

    git_r = {"status": "skip", "reason": "publish failed"}
    if publish_r.get("status") == "ok":
        if no_push:
            git_r = {"status": "skip", "reason": "no-push flag"}
        else:
            git_r = git_publish(now_utc_date())
            log(f"git: {git_r.get('status')}")

    # Persist state with kb stats too
    state["lastKbTick"] = now_utc_iso()
    state["lastKbSnapshot"] = now
    save_sleep_state(state)

    out = {
        "status": "ok",
        "tick": tick_no,
        "elapsed_sec": round(time.time() - started, 1),
        "kb_delta": {
            "active_facts": now["active_facts"] - prev.get("active_facts", 0),
            "relations": now["relations"] - prev.get("relations", 0),
            "embeddings": now["embeddings"] - prev.get("embeddings", 0),
        },
        "kb_now": now,
        "threshold": {
            "md_lines": md_lines,
            "dream_pending": state["dream_pending"],
            "days_since_dream": days_since_dream,
        },
        "steps": {"extract": extract_r, "embed": embed_r, "consolidate": cons_r},
        "publish": publish_r,
        "git": git_r,
    }
    print(json.dumps(out, ensure_ascii=False))
    log(f"=== kb-sleep-tick done — published={publish_r.get('status')} git={git_r.get('status')} ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())

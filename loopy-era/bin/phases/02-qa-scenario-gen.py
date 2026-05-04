#!/usr/bin/env python3
"""02 qa_scenario_gen — set `required` flags on 7 QA scenarios.

Reads project-profile.json. Auto-decides required scenarios from heuristics:
  - frontends (next/react/vue/svelte) → ui-button-event, modal/confirm/alert,
    browser-console-clean
  - backend services → api-flow
  - any DB hint (drizzle, prisma, knex, sqlx, sqlalchemy) → database-state

Stdout: {status, output:{required:[...], non_required:[...]}}
"""
from __future__ import annotations

import json
import pathlib
import sys


FRONTEND_FRAMEWORKS = {"next", "react", "vue", "svelte", "astro", "vite"}
DB_HINTS = ("drizzle", "prisma", "knex", "sequelize", "typeorm",
            "sqlx", "sqlalchemy", "neo4j", "mongo", "redis", "pg", "postgres")
SERVICE_HINTS = ("fastify", "express", "koa", "hono", "fastapi", "flask",
                 "actix", "axum", "gin", "echo")


def main() -> int:
    payload = json.loads(sys.stdin.read() or "{}")
    loopy = pathlib.Path(payload.get("loopy_dir",
                                     str(pathlib.Path.home() / ".comad/loopy-era")))
    profile_path = loopy / "project-profile.json"
    scenarios_path = loopy / "qa-scenarios.json"

    if not profile_path.exists():
        out = {"status": "noop", "output": {"reason": "no project-profile yet"},
               "summary": "skip — phase 01 hasn't profiled a project"}
        print(json.dumps(out, ensure_ascii=False))
        return 0

    profile = json.loads(profile_path.read_text())
    if not profile.get("project_root"):
        out = {"status": "noop", "output": {"reason": "profile has no project_root"},
               "summary": "skip — no project bound"}
        print(json.dumps(out, ensure_ascii=False))
        return 0

    fw = set(profile.get("frameworks") or [])
    is_frontend = bool(fw & FRONTEND_FRAMEWORKS)

    # Sniff package manifest for DB / service hints
    root = pathlib.Path(profile["project_root"])
    blob = ""
    for name in ("package.json", "pyproject.toml", "Cargo.toml", "go.mod"):
        p = root / name
        if p.exists():
            try:
                blob += p.read_text(errors="replace") + "\n"
            except OSError:
                pass
    blob_low = blob.lower()
    has_db = any(h in blob_low for h in DB_HINTS)
    has_service = any(h in blob_low for h in SERVICE_HINTS) or is_frontend  # frontends often have an API route

    # Mutate scenarios.json — set `required` per heuristic, leave commands untouched.
    scenarios = json.loads(scenarios_path.read_text())
    s = scenarios["scenarios"]
    s["ui-button-event"]["required"] = is_frontend
    s["modal-popup"]["required"] = is_frontend
    s["confirm-dialog"]["required"] = is_frontend
    s["alert-dialog"]["required"] = is_frontend
    s["browser-console-clean"]["required"] = is_frontend
    s["api-flow"]["required"] = has_service
    s["database-state"]["required"] = has_db
    scenarios_path.write_text(json.dumps(scenarios, indent=2, ensure_ascii=False) + "\n")

    required = [k for k, v in s.items() if v["required"]]
    non_required = [k for k, v in s.items() if not v["required"]]
    out = {
        "status": "ok",
        "output": {"required": required, "non_required": non_required,
                   "is_frontend": is_frontend, "has_db": has_db, "has_service": has_service},
        "summary": f"required: {len(required)}/7",
    }
    print(json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())

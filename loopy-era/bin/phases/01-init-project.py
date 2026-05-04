#!/usr/bin/env python3
"""01 init_project — detect stack + populate project-profile.json.

Stdin:  {state, iteration, scope, loopy_dir}
Stdout: {status, output:{project_root, language, build/test/lint/type commands}}

Project root resolution priority:
    1. scope.project_root (from caller)
    2. $COMAD_PROJECT_ROOT
    3. cwd if it's a git toplevel
    4. None (skip — daemon-mode tick has no project)
"""
from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys


def find_git_toplevel(start: pathlib.Path) -> pathlib.Path | None:
    try:
        r = subprocess.run(["git", "rev-parse", "--show-toplevel"],
                           cwd=start, capture_output=True, text=True, timeout=5)
        if r.returncode == 0:
            return pathlib.Path(r.stdout.strip())
    except (subprocess.TimeoutExpired, OSError):
        pass
    return None


def detect_stack(root: pathlib.Path) -> dict:
    files = {p.name for p in root.iterdir() if p.is_file()}
    out = {
        "language": "unknown",
        "frameworks": [],
        "build_command": None,
        "test_command": None,
        "lint_command": None,
        "type_command": None,
    }
    if "package.json" in files:
        out["language"] = "TypeScript/JavaScript"
        if "bun.lockb" in files or "bun.lock" in files:
            out["build_command"] = "bun run build"
            out["test_command"] = "bun test"
        elif "pnpm-lock.yaml" in files:
            out["build_command"] = "pnpm build"
            out["test_command"] = "pnpm test"
        else:
            out["build_command"] = "npm run build"
            out["test_command"] = "npm test"
        # Common lint/type
        out["lint_command"] = "npm run lint --if-present"
        out["type_command"] = "npx tsc --noEmit --skipLibCheck"
        try:
            pkg = json.loads((root / "package.json").read_text())
            scripts = (pkg.get("scripts") or {})
            if "lint" in scripts:
                out["lint_command"] = f"npm run lint"
            if "typecheck" in scripts or "type-check" in scripts:
                out["type_command"] = f"npm run typecheck"
            deps = list((pkg.get("dependencies") or {}).keys()) + \
                   list((pkg.get("devDependencies") or {}).keys())
            for fw in ("next", "react", "vue", "svelte", "astro", "vite"):
                if fw in deps:
                    out["frameworks"].append(fw)
        except (OSError, json.JSONDecodeError):
            pass
    elif "pyproject.toml" in files:
        out["language"] = "Python"
        if (root / "uv.lock").exists():
            out["build_command"] = "uv build"
            out["test_command"] = "uv run pytest"
        else:
            out["build_command"] = "python -m build"
            out["test_command"] = "pytest"
        out["lint_command"] = "ruff check ."
        out["type_command"] = "mypy ."
    elif "Cargo.toml" in files:
        out["language"] = "Rust"
        out["build_command"] = "cargo build"
        out["test_command"] = "cargo test"
        out["lint_command"] = "cargo clippy"
    elif "go.mod" in files:
        out["language"] = "Go"
        out["build_command"] = "go build ./..."
        out["test_command"] = "go test ./..."
        out["lint_command"] = "go vet ./..."
    elif "Makefile" in files:
        out["language"] = "Make-driven"
        out["build_command"] = "make build"
        out["test_command"] = "make test"
    return out


def main() -> int:
    payload = json.loads(sys.stdin.read() or "{}")
    scope = payload.get("scope") or {}
    loopy = pathlib.Path(payload.get("loopy_dir",
                                     str(pathlib.Path.home() / ".comad/loopy-era")))
    profile_path = loopy / "project-profile.json"

    # Resolve project root
    candidates = []
    if scope.get("project_root"):
        candidates.append(pathlib.Path(scope["project_root"]))
    env_root = os.environ.get("COMAD_PROJECT_ROOT")
    if env_root:
        candidates.append(pathlib.Path(env_root))
    candidates.append(pathlib.Path(os.environ.get("PWD", os.getcwd())))

    project_root: pathlib.Path | None = None
    for c in candidates:
        if not c.exists() or not c.is_dir():
            continue
        top = find_git_toplevel(c)
        if top:
            project_root = top
            break
        # Allow non-git dirs that have a manifest
        manifests = ("package.json", "pyproject.toml", "Cargo.toml", "go.mod", "Makefile")
        if any((c / m).exists() for m in manifests):
            project_root = c
            break

    if project_root is None:
        result = {
            "status": "noop",
            "output": {"project_root": None, "reason": "no manifest in candidate paths"},
            "summary": "no project to profile (daemon-mode tick OK)",
        }
        print(json.dumps(result, ensure_ascii=False))
        return 0

    stack = detect_stack(project_root)

    profile = json.loads(profile_path.read_text()) if profile_path.exists() else {"schema_version": "0.1"}
    profile.update({
        "detected_at": __import__("datetime").datetime.now(
            __import__("datetime").timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "project_root": str(project_root),
        **stack,
    })
    profile_path.write_text(json.dumps(profile, indent=2, ensure_ascii=False) + "\n")

    result = {
        "status": "ok",
        "output": {
            "project_root": str(project_root),
            "language": stack["language"],
            "frameworks": stack["frameworks"],
            "build_command": stack["build_command"],
            "test_command": stack["test_command"],
        },
        "summary": f"profiled {project_root.name} ({stack['language']})",
    }
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""comad 온톨로지 레지스트리 v0.1 — 파일이 진실원, DB 는 캐시.

객체 7종(memory/skill/agent/cron/hook/rule/decision)을 스캔해 SQLite 에
objects/links/FTS 를 재빌드하고, search/show/links 질의를 제공한다.
"""
import json, os, plistlib, re, sqlite3, sys, time

HOME = os.path.expanduser("~")
MEM_DIR = f"{HOME}/.claude/projects/-Users-jhkim--claude/memory"
SKILL_DIR = f"{HOME}/.claude/skills"
AGENT_DIR = f"{HOME}/.claude/agents"
CRON_DIR = f"{HOME}/Library/LaunchAgents"
HOOK_DIR = f"{HOME}/.claude/hooks"
RULE_DIR = f"{HOME}/.claude/rules"
DEC_DIR = f"{HOME}/.claude/.comad/decisions"
DB_DIR = f"{HOME}/.claude/.comad/ontology"
DB = f"{DB_DIR}/registry.db"
AUDIT = f"{DB_DIR}/audit.jsonl"
ACTIONS_JSON = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "actions.json"))
HOOK_EVENTS = ["pre-tool-use", "post-tool-use", "stop", "user-prompt-submit"]
BODY_CAP = 100_000


def read(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read(BODY_CAP)
    except OSError:
        return ""


def frontmatter(text):
    """--- 블록에서 name/description/type 을 얻는다 (naive, stdlib only)."""
    fm = {}
    m = re.match(r"^---\n(.*?)\n---", text, re.S)
    if not m:
        return fm
    block = m.group(1)
    for key in ("name", "description"):
        km = re.search(rf"^{key}:\s*(.+)$", block, re.M)
        if km:
            fm[key] = km.group(1).strip().strip('"\'')
    # metadata.type — node_type 은 제외하고 마지막 type 을 취한다
    types = re.findall(r"^\s*(?<!node_)type:\s*(\S+)", block, re.M)
    types = [t for t in types if t != "memory"]
    if types:
        fm["mtype"] = types[-1]
    return fm


def scan():
    """전 소스를 스캔해 (objects, bodies) 를 돌려준다."""
    objs = {}   # id -> dict
    bodies = {} # id -> full text (링크 추출·FTS 용)

    def add(otype, slug, title, desc, path, body, **extra):
        oid = f"{otype}:{slug}"
        try:
            mtime = int(os.path.getmtime(path)) if path and os.path.exists(path) else 0
        except OSError:
            mtime = 0
        objs[oid] = dict(id=oid, type=otype, slug=slug, title=title or slug,
                         description=desc or "", path=path or "", mtime=mtime,
                         extra=json.dumps(extra, ensure_ascii=False) if extra else "")
        bodies[oid] = body or ""

    # memory
    if os.path.isdir(MEM_DIR):
        for fn in sorted(os.listdir(MEM_DIR)):
            if not fn.endswith(".md") or fn == "MEMORY.md":
                continue
            path = f"{MEM_DIR}/{fn}"
            text = read(path)
            fm = frontmatter(text)
            slug = fm.get("name") or fn[:-3]
            add("memory", slug, slug, fm.get("description"), path, text,
                mtype=fm.get("mtype", ""))

    # skill
    if os.path.isdir(SKILL_DIR):
        for d in sorted(os.listdir(SKILL_DIR)):
            sk = f"{SKILL_DIR}/{d}/SKILL.md"
            if not os.path.isfile(sk):
                continue
            text = read(sk)
            fm = frontmatter(text)
            add("skill", d, fm.get("name") or d, fm.get("description"), sk, text)

    # agent
    if os.path.isdir(AGENT_DIR):
        for fn in sorted(os.listdir(AGENT_DIR)):
            if not fn.endswith(".md"):
                continue
            path = f"{AGENT_DIR}/{fn}"
            text = read(path)
            fm = frontmatter(text)
            slug = fn[:-3]
            add("agent", slug, fm.get("name") or slug, fm.get("description"), path, text)

    # cron (launchd com.comad.*)
    if os.path.isdir(CRON_DIR):
        for fn in sorted(os.listdir(CRON_DIR)):
            if not (fn.startswith("com.comad.") and fn.endswith(".plist")):
                continue
            path = f"{CRON_DIR}/{fn}"
            try:
                with open(path, "rb") as f:
                    pl = plistlib.load(f)
            except Exception:
                continue
            label = pl.get("Label", fn[:-6])
            slug = label.replace("com.comad.", "")
            prog = pl.get("ProgramArguments") or ([pl["Program"]] if pl.get("Program") else [])
            cal = pl.get("StartCalendarInterval")
            if isinstance(cal, dict):
                cal = [cal]
            if cal:
                sched = " · ".join(
                    f"{c.get('Weekday','*')}w {c.get('Hour','*')}:{str(c.get('Minute','*')).zfill(2)}"
                    for c in cal)
            elif pl.get("StartInterval"):
                sched = f"every {pl['StartInterval']}s"
            else:
                sched = "manual/other"
            cmd = " ".join(str(a) for a in prog)
            add("cron", slug, label, f"[{sched}] {cmd}"[:300], path, cmd,
                schedule=sched, command=cmd)

    # hook (event 디렉터리, stem 단위로 sh/py 래퍼 묶음)
    for ev in HOOK_EVENTS:
        d = f"{HOOK_DIR}/{ev}"
        if not os.path.isdir(d):
            continue
        stems = {}
        for fn in sorted(os.listdir(d)):
            stem, ext = os.path.splitext(fn)
            if ext not in (".sh", ".py") or fn.startswith("_"):
                continue
            stems.setdefault(stem, []).append(fn)
        for stem, files in stems.items():
            paths = [f"{d}/{f}" for f in files]
            body = "\n".join(read(p) for p in paths)
            add("hook", f"{ev}/{stem}", stem, f"{ev} hook ({', '.join(files)})",
                paths[0], body, event=ev, files=files)

    # rule
    if os.path.isdir(RULE_DIR):
        for fn in sorted(os.listdir(RULE_DIR)):
            if not fn.endswith(".md"):
                continue
            path = f"{RULE_DIR}/{fn}"
            text = read(path)
            tm = re.search(r"^#\s+(.+)$", text, re.M)
            add("rule", fn[:-3], tm.group(1).strip() if tm else fn[:-3],
                "", path, text)

    # decision (open + resolved)
    for sub, status in (("", "open"), ("/_resolved", "resolved")):
        d = f"{DEC_DIR}{sub}"
        if not os.path.isdir(d):
            continue
        for fn in sorted(os.listdir(d)):
            if not fn.endswith(".json"):
                continue
            path = f"{d}/{fn}"
            try:
                dec = json.loads(read(path))
            except Exception:
                continue
            slug = dec.get("id", fn[:-5])
            body = json.dumps(dec, ensure_ascii=False)
            add("decision", slug, dec.get("title", slug),
                f"[{status}·{dec.get('urgency','?')}] {dec.get('detail','')[:200]}",
                path, body, status=status, source=dec.get("source", ""))

    # action (카탈로그 — Kinetic 층)
    for a in load_actions():
        exe = " ".join(a.get("executor") or ["(manual)"])
        add("action", a["id"], a["title"],
            f"[{a['effect']}·{a['approval']}] {exe} {a.get('args', '')}".strip(),
            ACTIONS_JSON, json.dumps(a, ensure_ascii=False),
            domain=a.get("domain", ""), effect=a["effect"], approval=a["approval"])

    return objs, bodies


def load_actions():
    try:
        with open(ACTIONS_JSON, encoding="utf-8") as f:
            return json.load(f)["actions"]
    except (OSError, json.JSONDecodeError, KeyError):
        return []


WIKILINK = re.compile(r"\[\[([A-Za-z0-9_-]+)\]\]")


def extract_links(objs, bodies):
    links = []  # (src, dst, type, evidence)
    mem_by_slug = {o["slug"]: o["id"] for o in objs.values() if o["type"] == "memory"}
    mem_norm = {s.replace("-", "_"): i for s, i in mem_by_slug.items()}

    # mentions 후보: 구분자 포함 + 길이>=6 인 slug 만 (일반단어 오탐 방지)
    cand = {}
    for o in objs.values():
        s = o["slug"].split("/")[-1]  # hook 은 stem 만
        if len(s) >= 6 and re.search(r"[a-z0-9][-_][a-z0-9]", s):
            cand.setdefault(s, o["id"])
    cand_re = {s: re.compile(rf"(?<![A-Za-z0-9_-]){re.escape(s)}(?![A-Za-z0-9_-])")
               for s in cand}

    for oid, body in bodies.items():
        if not body:
            continue
        # references — [[wikilink]] (memory 대상, -/_ 정규화)
        for m in WIKILINK.finditer(body):
            t = m.group(1)
            dst = mem_by_slug.get(t) or mem_norm.get(t.replace("-", "_"))
            if dst and dst != oid:
                links.append((oid, dst, "references", f"[[{t}]]"))
        # mentions — 단어경계 slug 등장
        for s, rx in cand_re.items():
            dst = cand[s]
            if dst == oid:
                continue
            m = rx.search(body)
            if m:
                a = max(0, m.start() - 30)
                ev = body[a:m.end() + 30].replace("\n", " ").strip()
                links.append((oid, dst, "mentions", ev[:120]))

    # runs — cron 커맨드 경로가 skill/hook 에 속하면 연결
    skill_dirs = {f"{SKILL_DIR}/{o['slug']}/": o["id"]
                  for o in objs.values() if o["type"] == "skill"}
    hook_paths = {o["path"]: o["id"] for o in objs.values() if o["type"] == "hook"}
    for o in objs.values():
        if o["type"] != "cron":
            continue
        cmd = json.loads(o["extra"]).get("command", "") if o["extra"] else ""
        for tok in cmd.split():
            tok = tok.replace("$HOME", HOME).replace("~", HOME)
            if tok in hook_paths:
                links.append((o["id"], hook_paths[tok], "runs", tok))
            else:
                for sd, sid in skill_dirs.items():
                    if tok.startswith(sd):
                        links.append((o["id"], sid, "runs", tok))
                        break

    # action 링크 — executes(실행 스크립트가 속한 skill/hook) · gated_by(강제 훅)
    for o in objs.values():
        if o["type"] != "action":
            continue
        a = json.loads(bodies[o["id"]])
        for h in a.get("gated_by", []):
            if h in objs:
                links.append((o["id"], h, "gated_by", "actions.json"))
        for tok in (a.get("executor") or []):
            tok = os.path.expanduser(tok.replace("$HOME", HOME))
            if tok in hook_paths:
                links.append((o["id"], hook_paths[tok], "executes", tok))
            for sd, sid in skill_dirs.items():
                if tok.startswith(sd):
                    links.append((o["id"], sid, "executes", tok))
                    break

    # dedupe (src,dst,type)
    seen, out = set(), []
    for l in links:
        k = l[:3]
        if k not in seen:
            seen.add(k)
            out.append(l)
    return out


def build():
    os.makedirs(DB_DIR, exist_ok=True)
    objs, bodies = scan()
    links = extract_links(objs, bodies)
    con = sqlite3.connect(DB)
    cur = con.cursor()
    cur.executescript("""
        DROP TABLE IF EXISTS objects; DROP TABLE IF EXISTS links;
        DROP TABLE IF EXISTS objects_fts;
        CREATE TABLE objects(id TEXT PRIMARY KEY, type TEXT, slug TEXT,
            title TEXT, description TEXT, path TEXT, mtime INTEGER, extra TEXT);
        CREATE TABLE links(src TEXT, dst TEXT, type TEXT, evidence TEXT);
        CREATE INDEX idx_links_src ON links(src);
        CREATE INDEX idx_links_dst ON links(dst);
        CREATE VIRTUAL TABLE objects_fts USING fts5(id, title, description, body);
    """)
    for o in objs.values():
        cur.execute("INSERT INTO objects VALUES(?,?,?,?,?,?,?,?)",
                    (o["id"], o["type"], o["slug"], o["title"], o["description"],
                     o["path"], o["mtime"], o["extra"]))
        cur.execute("INSERT INTO objects_fts VALUES(?,?,?,?)",
                    (o["id"], o["title"], o["description"], bodies.get(o["id"], "")))
    cur.executemany("INSERT INTO links VALUES(?,?,?,?)", links)
    cur.execute("CREATE TABLE IF NOT EXISTS meta(k TEXT PRIMARY KEY, v TEXT)")
    cur.execute("INSERT OR REPLACE INTO meta VALUES('built_at',?)",
                (time.strftime("%Y-%m-%dT%H:%M:%S%z"),))
    con.commit()
    print(f"built: {len(objs)} objects, {len(links)} links -> {DB}")
    stats(con)


def connect():
    if not os.path.exists(DB):
        sys.exit("registry 없음 — 먼저 `onto.py build`")
    return sqlite3.connect(DB)


def stats(con=None):
    con = con or connect()
    cur = con.cursor()
    print("objects:")
    for t, n in cur.execute("SELECT type, COUNT(*) FROM objects GROUP BY type ORDER BY 2 DESC"):
        print(f"  {t:10} {n}")
    print("links:")
    for t, n in cur.execute("SELECT type, COUNT(*) FROM links GROUP BY type ORDER BY 2 DESC"):
        print(f"  {t:10} {n}")


def resolve(cur, key):
    """id 완전일치 → slug 완전일치 → slug LIKE 순으로 단일 객체를 찾는다."""
    for q, p in (("SELECT id FROM objects WHERE id=?", (key,)),
                 ("SELECT id FROM objects WHERE slug=?", (key,)),
                 ("SELECT id FROM objects WHERE slug LIKE ?", (f"%{key}%",))):
        rows = cur.execute(q, p).fetchall()
        if len(rows) == 1:
            return rows[0][0]
        if len(rows) > 1:
            sys.exit("모호함 — 후보:\n  " + "\n  ".join(r[0] for r in rows[:15]))
    sys.exit(f"객체 없음: {key}")


def search(q, otype=None):
    con = connect()
    cur = con.cursor()
    sql = ("SELECT f.id, o.type, o.title, snippet(objects_fts, 3, '[', ']', '…', 12) "
           "FROM objects_fts f JOIN objects o ON o.id=f.id WHERE objects_fts MATCH ?")
    args = [q]
    if otype:
        sql += " AND o.type=?"
        args.append(otype)
    sql += " ORDER BY rank LIMIT 20"
    try:
        rows = cur.execute(sql, args).fetchall()
    except sqlite3.OperationalError:
        rows = cur.execute(
            "SELECT id, type, title, description FROM objects "
            "WHERE title LIKE ? OR description LIKE ? LIMIT 20",
            (f"%{q}%", f"%{q}%")).fetchall()
    for oid, t, title, snip in rows:
        print(f"{oid}\n    {snip}")
    if not rows:
        print("(없음)")


def show(key):
    con = connect()
    cur = con.cursor()
    oid = resolve(cur, key)
    o = cur.execute("SELECT * FROM objects WHERE id=?", (oid,)).fetchone()
    cols = [d[0] for d in cur.description]
    d = dict(zip(cols, o))
    print(f"# {d['id']}\n  title: {d['title']}\n  path : {d['path']}")
    if d["description"]:
        print(f"  desc : {d['description'][:300]}")
    if d["extra"]:
        print(f"  extra: {d['extra'][:300]}")
    out = cur.execute("SELECT type, dst, evidence FROM links WHERE src=? ORDER BY type", (oid,)).fetchall()
    inc = cur.execute("SELECT type, src, evidence FROM links WHERE dst=? ORDER BY type", (oid,)).fetchall()
    if out:
        print(f"\n→ 나가는 링크 ({len(out)})")
        for t, dst, ev in out:
            print(f"  [{t}] {dst}  · {ev[:60]}")
    if inc:
        print(f"\n← 들어오는 링크 ({len(inc)})")
        for t, src, ev in inc:
            print(f"  [{t}] {src}  · {ev[:60]}")


def links_bfs(key, depth):
    con = connect()
    cur = con.cursor()
    root = resolve(cur, key)
    seen = {root}
    frontier = [(root, 0)]
    print(root)
    while frontier:
        oid, lv = frontier.pop(0)
        if lv >= depth:
            continue
        rows = cur.execute(
            "SELECT dst, type FROM links WHERE src=? UNION "
            "SELECT src, type FROM links WHERE dst=?", (oid, oid)).fetchall()
        for nxt, lt in rows:
            if nxt in seen:
                continue
            seen.add(nxt)
            print("  " * (lv + 1) + f"[{lt}] {nxt}")
            frontier.append((nxt, lv + 1))


def audit_log(action_id, args, result):
    os.makedirs(DB_DIR, exist_ok=True)
    with open(AUDIT, "a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                            "action": action_id, "args": args, "result": result},
                           ensure_ascii=False) + "\n")


def actions_cmd(domain=None):
    for a in load_actions():
        if domain and a.get("domain") != domain:
            continue
        tag = f"{a['effect']}·{a['approval']}"
        print(f"{a['id']:24} [{tag:18}] {a['title']}")


def act(action_id, extra_args, yes=False):
    """카탈로그 액션 디스패처 — effect/approval 을 강제하고 전 시도를 감사로그에 남긴다."""
    acts = {a["id"]: a for a in load_actions()}
    if action_id not in acts:
        sys.exit(f"카탈로그에 없는 액션: {action_id} — `onto.py actions` 로 확인")
    a = acts[action_id]
    if a["approval"] == "gate" or not a.get("executor"):
        audit_log(action_id, extra_args, "manual-only")
        sys.exit(f"[gate] 문서화 전용 액션 — 직접 실행하고 게이트 훅"
                 f"({', '.join(a.get('gated_by', []))})을 통과할 것")
    if a["approval"] == "hitl":
        import subprocess
        r = subprocess.run(["python3", f"{HOME}/.claude/hooks/lib/decisions.py", "add",
                            "--source", "ontology-act", "--title", f"승인 요청: {a['title']}",
                            "--detail", f"action={action_id} args={extra_args}"],
                           capture_output=True, text=True)
        audit_log(action_id, extra_args, "hitl-queued")
        sys.exit(f"[hitl] 결정큐에 승인 요청 생성됨 — 실행 안 함\n{r.stdout}")
    if a["effect"] != "read" and a["approval"] == "confirm" and not yes:
        audit_log(action_id, extra_args, "blocked-no-confirm")
        sys.exit(f"[confirm] 쓰기 액션 (대상 {a.get('targets')}) — --yes 붙여 재실행")
    import subprocess
    cmd = [os.path.expanduser(t.replace("$HOME", HOME)) for t in a["executor"]] + extra_args
    r = subprocess.run(cmd, capture_output=True, text=True)
    audit_log(action_id, extra_args, f"exit={r.returncode}")
    if r.stdout:
        print(r.stdout, end="")
    if r.stderr:
        print(r.stderr, file=sys.stderr, end="")
    sys.exit(r.returncode)


def main():
    args = sys.argv[1:]
    if not args:
        sys.exit(__doc__ + "\nusage: onto.py build|stats|search|show|links|actions [domain]|act <id> [args] [--yes]")
    cmd = args[0]
    if cmd == "build":
        build()
    elif cmd == "stats":
        stats()
    elif cmd == "search":
        otype = args[args.index("--type") + 1] if "--type" in args else None
        q = " ".join(a for a in args[1:] if not a.startswith("--") and a != otype)
        search(q, otype)
    elif cmd == "show":
        show(args[1])
    elif cmd == "actions":
        actions_cmd(args[1] if len(args) > 1 else None)
    elif cmd == "act":
        yes = "--yes" in args
        rest = [a for a in args[2:] if a != "--yes"]
        act(args[1], rest, yes)
    elif cmd == "links":
        depth = int(args[args.index("--depth") + 1]) if "--depth" in args else 2
        links_bfs(args[1], depth)
    else:
        sys.exit(f"unknown: {cmd}")


if __name__ == "__main__":
    main()

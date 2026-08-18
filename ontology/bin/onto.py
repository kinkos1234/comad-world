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
DELIVERABLES_JSON = f"{DB_DIR}/deliverables.json"
AUDIT = f"{DB_DIR}/audit.jsonl"
ACTIONS_JSON = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "actions.json"))
HOOK_EVENTS = ["pre-tool-use", "post-tool-use", "stop", "user-prompt-submit"]
SHOP_DBS = {"brands": "shop-brand", "vendors": "shop-vendor",
            "products": "shop-product", "po": "shop-po"}
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


def scan(with_shop=True):
    """전 소스를 스캔해 (objects, bodies, extra_links) 를 돌려준다."""
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

    # script — cron 커맨드가 가리키는 skill/hook 밖 스크립트 (레포 산개분)
    for o in list(objs.values()):
        if o["type"] != "cron":
            continue
        cmd = json.loads(o["extra"]).get("command", "") if o["extra"] else ""
        for tok in cmd.split():
            t = os.path.expanduser(tok.replace("$HOME", HOME))
            if not (os.path.isfile(t) and os.path.splitext(t)[1] in (".sh", ".py", ".mjs", ".js", ".ts")):
                continue
            if t.startswith(SKILL_DIR) or t.startswith(HOOK_DIR):
                continue
            slug = os.path.basename(t)
            prev = objs.get(f"script:{slug}")
            if prev and prev["path"] != t:  # 동명 스크립트 — 부모 디렉터리로 유일화
                slug = "/".join(t.split("/")[-2:])
            add("script", slug, slug, t.replace(HOME, "~"), t, read(t))

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

    extra_links = scan_shop(add) if with_shop else []
    extra_links += scan_deliverables(add, objs)
    return objs, bodies, extra_links


def scan_deliverables(add, objs):
    """납품 축 (Phase 4) — 프라이빗 SoT deliverables.json 의 client/deliverable 를 적재.
    링크: delivered_to(납품물→고객) · bundles(납품물→내부 컴포넌트 계보) ·
    governed_by(납품물→적용 규칙). bundles/governed_by 대상이 레지스트리에 없으면 경고."""
    try:
        with open(DELIVERABLES_JSON, encoding="utf-8") as f:
            d = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        print(f"[deliv] deliverables.json 없음/파손 — 스킵: {e}", file=sys.stderr)
        return []
    # memory 대상은 -/_ 정규화로 리졸브 (frontmatter name 이 파일명과 다른 경우)
    norm = {o["id"].replace("-", "_").lower(): o["id"] for o in objs.values()}

    def resolve_target(t):
        if t in objs:
            return t
        return norm.get(t.replace("-", "_").lower())

    links, missing = [], []
    for c in d.get("clients", []):
        body = json.dumps(c, ensure_ascii=False)
        add("client", c["id"], c.get("label", c["id"]),
            f"{c.get('channel', '')} {c.get('note', '')}".strip(),
            DELIVERABLES_JSON, body)
    for dv in d.get("deliverables", []):
        oid = f"deliverable:{dv['id']}"
        body = json.dumps(dv, ensure_ascii=False)
        st = f"[{dv.get('state', '?')}·{dv.get('version', '') or '-'}]"
        add("deliverable", dv["id"], dv.get("title", dv["id"]),
            f"{st} {dv.get('url', '')} {dv.get('note', '')}".strip(),
            DELIVERABLES_JSON, body, state=dv.get("state", ""), client=dv.get("client") or "")
        if dv.get("client"):
            links.append((oid, f"client:{dv['client']}", "delivered_to", dv.get("state", "")))
        if dv.get("product"):  # 기능 원형 — 의뢰인별 다중 납품을 한 product 로 묶는다
            pid = f"product:{dv['product']}"
            if pid not in objs:
                add("product", dv["product"], dv["product"],
                    "기능 원형 — 의뢰인별 납품 인스턴스의 공통 조상", DELIVERABLES_JSON, "")
            links.append((oid, pid, "instance_of", "deliverables.json"))
        for lt, key in (("bundles", "bundles"), ("governed_by", "governed_by")):
            for t in dv.get(key, []):
                rt_ = resolve_target(t)
                if rt_ or t.startswith(("client:", "deliverable:")):
                    links.append((oid, rt_ or t, lt, "deliverables.json"))
                else:
                    missing.append(f"{oid} -{lt}-> {t}")
    # products[] — 명시 선언된 기능 원형 (deliverable.product 자동 생성과 병합)
    for pr in d.get("products", []):
        pid = f"product:{pr['id']}"
        add("product", pr["id"], pr.get("title", pr["id"]),
            f"{'[영업가능] ' if pr.get('sellable') else ''}{pr.get('note', '')}".strip(),
            DELIVERABLES_JSON, json.dumps(pr, ensure_ascii=False),
            sellable=bool(pr.get("sellable")))
        impl = pr.get("implemented_in")
        if impl:
            links.append((pid, f"deliverable:{impl}", "implemented_in", "deliverables.json"))
    if missing:
        print(f"[deliv] 미등록 대상 {len(missing)}건: " + "; ".join(missing[:5]), file=sys.stderr)
    print(f"[deliv] client {len(d.get('clients', []))} · deliverable {len(d.get('deliverables', []))} · 링크 {len(links)}")
    return links


def scan_shop(add):
    """OFFCUT Notion 4 DB (브랜드·거래처·상품·PO) — relation 을 링크로 추출.
    네트워크·토큰 실패 시 경고만 내고 스킵한다 (오프라인 빌드 허용)."""
    try:
        sys.path.insert(0, f"{HOME}/.claude/skills/sales/scripts")
        import notion_sales as ns
    except Exception as e:
        print(f"[shop] notion helper 로드 실패 — 스킵: {e}", file=sys.stderr)
        return []
    page_map, rel_rows, seen = {}, [], {}
    for key, otype in SHOP_DBS.items():
        try:
            rows = ns.query_all(ns.DB[key])
        except Exception as e:
            print(f"[shop] {key} 조회 실패 — 스킵: {e}", file=sys.stderr)
            continue
        for pg in rows:
            title, flat, rels = "", {}, []
            for name, pr in pg["properties"].items():
                try:
                    if pr["type"] == "title":
                        title = ns.plain(pr)
                    elif pr["type"] == "relation":
                        rels.append((name, [r["id"] for r in pr["relation"]]))
                    else:
                        v = ns.plain(pr)
                        if v not in (None, "", []):
                            flat[name] = v
                except Exception:
                    pass
            if not title:
                continue
            slug = title
            n = seen.get((otype, slug), 0)
            seen[(otype, slug)] = n + 1
            if n:  # 동명 행 (옵션 분리 등) — 접미사로 유일화
                slug = f"{title} #{n + 1}"
            oid = f"{otype}:{slug}"
            page_map[pg["id"]] = oid
            body = json.dumps(flat, ensure_ascii=False)
            add(otype, slug, title, body[:250], "", body, notion_id=pg["id"])
            rel_rows.append((oid, rels))
    links = []
    for oid, rels in rel_rows:
        for name, ids in rels:
            for rid in ids:
                dst = page_map.get(rid)
                if dst and dst != oid:
                    links.append((oid, dst, "relates", name))
    print(f"[shop] {sum(1 for k in seen)}종 {len(page_map)}행, relation {len(links)}건")
    return links


def load_actions():
    try:
        with open(ACTIONS_JSON, encoding="utf-8") as f:
            return json.load(f)["actions"]
    except (OSError, json.JSONDecodeError, KeyError):
        return []


WIKILINK = re.compile(r"\[\[([A-Za-z0-9_-]+)\]\]")


def extract_links(objs, bodies, seed=None):
    links = list(seed or [])  # (src, dst, type, evidence)
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
    script_paths = {o["path"]: o["id"] for o in objs.values() if o["type"] == "script"}
    for o in objs.values():
        if o["type"] != "cron":
            continue
        cmd = json.loads(o["extra"]).get("command", "") if o["extra"] else ""
        for tok in cmd.split():
            tok = tok.replace("$HOME", HOME).replace("~", HOME)
            if tok in hook_paths:
                links.append((o["id"], hook_paths[tok], "runs", tok))
            elif tok in script_paths:
                links.append((o["id"], script_paths[tok], "runs", tok))
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
    objs, bodies, extra = scan(with_shop="--no-shop" not in sys.argv)
    links = extract_links(objs, bodies, seed=extra)
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
    bad = [x for x in extra_args if x in (a.get("forbid_args") or [])]
    if bad:
        audit_log(action_id, extra_args, f"forbidden-args:{bad}")
        sys.exit(f"[forbid] {bad} 는 이 액션에서 금지 — {a.get('note', '')}")
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

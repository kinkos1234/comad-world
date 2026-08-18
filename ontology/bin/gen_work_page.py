#!/usr/bin/env python3
"""영업용 공개 작업 사례 페이지 생성기 — 온톨로지 SoT(deliverables.json)가 소스.

사용: gen_work_page.py [출력경로=~/Programmer/03-web/kinkos1234.github.io/work.html]
규칙: 고객은 역할 익명 표기만 · 편집샵(OFFCUT/select-shop) 계열 제외 · 공개 URL 만 링크.
표기 오버라이드는 이 파일의 PUBLIC 맵에서만 관리한다 (SoT 는 건드리지 않는다).
"""
import json, os, sys, html, datetime

HOME = os.path.expanduser("~")
SOT = f"{HOME}/.claude/.comad/ontology/deliverables.json"
OUT = sys.argv[1] if len(sys.argv) > 1 else f"{HOME}/Programmer/03-web/kinkos1234.github.io/work.html"

EXCLUDE = {"select-shop-kit", "gongnyang-prompt-kit", "comadj-portfolio"}  # 편집샵 계열·내부 킷·허브 자신
# 공개 표기 오버라이드 — 실명·내부명 제거
PUBLIC = {
    "one-k-web":        ("ONE K", "SOOP 크루 56명 라이브 현황·티어 팬사이트 — 게시판 미러링·OCR 파이프라인 상시 운영", "https://onek-soop.com", "자사 운영"),
    "thegongsi":        ("The Gongsi", "한국 공시(DART) AI 리서치 터미널", "https://thegongsi.vercel.app", "자사 운영 · OSS"),
    "vidguide":         ("VidGuide", "AI 영상 제작 워크플로우 가이드 문서 사이트", "", "자사 운영"),
    "ccar":             ("CCAR", "VOC 수집→AI 전략 제언→주간 보고 자동화 사내 플랫폼 (1인 풀스택, 익명화 공개본)", "https://github.com/kinkos1234/ccar", "사내 실적 · 공개본"),
    "ccar-pro":         None,  # WIP 미영업 — 비공개
    "timeattack-tool":  ("SOOP 별풍선 타임어택 방송 도구", "실시간 채팅·후원 WebSocket 수신, 방송 오버레이 일체", "", "납품 · SOOP 방송인"),
    "sig-slot-machine": ("후원 추첨 슬롯머신", "시청자 추첨 방송 도구 — 의뢰인별 사본 2건 납품, 실방송 사용 중", "https://sig-slot.vercel.app", "납품 · 스트리머 2인"),
    "sig-hunter":       None,  # slot-machine 사례에 합산 표기
    "ph-tools":         ("스트리머 후원 툴셋", "코드 게이트 툴 8종 · SOOP 후원 이벤트 브릿지 · 브라우저 확장", "", "납품 · SOOP 스트리머"),
    "ph-scoreboard":    ("후원 순위 오버레이", "엑셀 연동 시즌 누적 순위 — 방송 오버레이 4포맷", "", "납품 · SOOP 스트리머"),
    "pyeongwang-portfolio": ("스트리머 포트폴리오 사이트", "방송인 소개·활동 아카이브 웹", "", "납품 · SOOP 스트리머"),
    "sneage-scoreboard": ("게임 콘텐츠 스코어보드", "스타크래프트×리니지 콘텐츠 실시간 점수판 (v14)", "", "납품 · 스트리머"),
    "unispa-site":      ("댄스크루 웹사이트", "크루 소개·영상 아카이브", "https://univspa.kr", "납품 완료"),
}
PRODUCTS_PUBLIC = {
    "car-cost-analysis":   ("제조 원가분석 시스템", "VOC·원가 데이터 파이프라인 — 사내 1인 풀스택 구축 실적 기반"),
    "slot-machine":        ("후원 추첨 슬롯머신", "납품 실적 2건 — 의뢰인별 테마 사본 제공"),
    "soop-live-detection": ("라이브 방송 감지 파이프라인", "SOOP·유튜브 동시 감지, 데이터센터 IP 환경 폴백 내장"),
    "board-mirror-sync":   ("게시판 미러링·정합성 파이프라인", "정정·삭제·재등록까지 따라가는 reconcile 설계"),
    "ocr-tier-pipeline":   ("이미지 보드 OCR 상태 추출", "오독 방지 다중 가드 — 사람 확정값 보호·서킷브레이커"),
    "donation-bridge":     ("후원 이벤트 브릿지", "SOOP WebSocket 프로토콜 실전 검증 — 오버레이·집계 연동"),
}

d = json.load(open(SOT, encoding="utf-8"))
cards_ops, cards_client = [], []
for dv in d["deliverables"]:
    if dv["id"] in EXCLUDE or PUBLIC.get(dv["id"]) is None and dv["id"] not in PUBLIC:
        continue
    ov = PUBLIC.get(dv["id"])
    if ov is None:
        continue
    title, desc, url, tag = ov
    link = f'<a href="{url}" target="_blank" rel="noopener">{html.escape(url.replace("https://",""))}</a>' if url else ""
    card = (f'<div class="card"><div class="tag">{html.escape(tag)}</div>'
            f'<h3>{html.escape(title)}</h3><p>{html.escape(desc)}</p>{link}</div>')
    (cards_ops if "자사" in tag or "사내" in tag else cards_client).append(card)

units = []
for pr in d.get("products", []):
    if not pr.get("sellable") or pr["id"] not in PRODUCTS_PUBLIC:
        continue
    t, desc = PRODUCTS_PUBLIC[pr["id"]]
    units.append(f'<div class="unit"><h4>{html.escape(t)}</h4><p>{html.escape(desc)}</p></div>')

today = datetime.date.today().isoformat()
page = f"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Comad J — Work</title>
<style>
:root {{ --paper:#F7F4EC; --ink:#151312; --sub:#5d574f; --hair:#d9d3c6; --accent:#B4552D; }}
* {{ margin:0; box-sizing:border-box; }}
body {{ background:var(--paper); color:var(--ink); font-family:Pretendard,-apple-system,"Apple SD Gothic Neo","Noto Sans KR",sans-serif; word-break:keep-all; line-height:1.6; }}
.wrap {{ max-width:880px; margin:0 auto; padding:64px 24px 96px; }}
header p.eyebrow {{ font-size:13px; letter-spacing:.14em; color:var(--accent); text-transform:uppercase; }}
h1 {{ font-size:clamp(28px,5vw,44px); font-weight:800; margin:8px 0 4px; }}
header p.lede {{ color:var(--sub); max-width:56ch; }}
h2 {{ font-size:14px; letter-spacing:.12em; color:var(--sub); text-transform:uppercase; margin:56px 0 16px; padding-top:16px; border-top:1px solid var(--hair); }}
.grid {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(250px,1fr)); gap:14px; }}
.card {{ border:1px solid var(--hair); border-radius:10px; padding:18px; background:rgba(255,255,255,.45); }}
.card .tag {{ font-size:11px; letter-spacing:.08em; color:var(--accent); margin-bottom:6px; }}
.card h3 {{ font-size:17px; margin-bottom:6px; }}
.card p {{ font-size:13.5px; color:var(--sub); margin-bottom:8px; }}
.card a {{ font-size:12.5px; color:var(--accent); text-decoration:none; border-bottom:1px solid var(--hair); }}
.unit {{ border-left:2px solid var(--hair); padding:2px 0 2px 14px; margin-bottom:14px; }}
.unit h4 {{ font-size:15px; }}
.unit p {{ font-size:13px; color:var(--sub); }}
footer {{ margin-top:64px; padding-top:16px; border-top:1px solid var(--hair); font-size:12.5px; color:var(--sub); display:flex; gap:16px; flex-wrap:wrap; }}
footer a {{ color:var(--ink); }}
</style></head><body><div class="wrap">
<header>
  <p class="eyebrow">Comad J · Selected Work</p>
  <h1>혼자서 시스템 하나를 끝까지.</h1>
  <p class="lede">데이터 파이프라인부터 방송 오버레이까지 — 기획·개발·배포·운영을 1인이 맡아
  실서비스로 굴리고 있는 작업들입니다. 아래 기능 유닛은 떼어서 별도 구축·납품이 가능합니다.</p>
</header>
<h2>운영 중인 서비스</h2><div class="grid">{''.join(cards_ops)}</div>
<h2>클라이언트 납품 사례</h2><div class="grid">{''.join(cards_client)}</div>
<h2>떼어 팔 수 있는 기능 유닛</h2>{''.join(units)}
<footer><a href="https://github.com/kinkos1234" target="_blank" rel="noopener">GitHub @kinkos1234</a>
<a href="/">← Home</a><span>updated {today} · generated from ontology registry</span></footer>
</div></body></html>"""
os.makedirs(os.path.dirname(OUT), exist_ok=True)
open(OUT, "w", encoding="utf-8").write(page)
print(f"written: {OUT} ({len(cards_ops)} ops, {len(cards_client)} client, {len(units)} units)")

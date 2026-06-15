#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""恩纳村 city页 + 详情页 渲染预览（跨manifest全局索引，含city-page hero fallback）。"""
import json, os, html, glob

ROOT = "/home/ubuntu/tools/travel_APP/travel_guide/data"
PB = f"{ROOT}/playbooks/日本"
IMG = f"{ROOT}/images"
OUT = "/home/ubuntu/.hermes-bot2/media_cache/enna_verify"
os.makedirs(OUT, exist_ok=True)

MANI = {}
for mf in glob.glob(f"{IMG}/*/manifest.json"):
    subdir = os.path.dirname(mf)
    try: data = json.load(open(mf, encoding="utf-8"))
    except Exception: continue
    for m in data:
        if m.get("status") != "ok": continue
        attr = m.get("attraction")
        if not attr: continue
        for p in [m] + m.get("extras", []):
            local = p.get("local")
            if not local: continue
            fp = f"{subdir}/{local}"
            if os.path.exists(fp): MANI.setdefault(attr, []).append(f"file://{fp}")

def images_for(name, limit=6): return MANI.get(name, [])[:limit]
def first_image(name):
    p = images_for(name, 1); return p[0] if p else None
def esc(s): return html.escape(str(s or ""))

CSS = """
* { box-sizing:border-box; margin:0; padding:0; }
body { background:#f2f4f7; font-family:-apple-system,'PingFang SC','Microsoft YaHei',sans-serif; width:375px; }
.container { padding-bottom:20px; }
.hero { position:relative; width:100%; height:190px; overflow:hidden; }
.hero-img { width:100%; height:100%; object-fit:cover; }
.hero-mask { position:absolute; left:0; right:0; bottom:0; height:60%; background:linear-gradient(to top,rgba(0,0,0,.6),rgba(0,0,0,0)); }
.hero-ttl { position:absolute; left:16px; bottom:14px; color:#fff; }
.hero-name { font-size:22px; font-weight:700; letter-spacing:1px; }
.hero-sub { font-size:13px; opacity:.9; margin-top:3px; }
.lead { font-size:13.5px; color:#555; line-height:1.7; background:#fff; margin:0 10px 10px; padding:12px; border-radius:8px; border-left:4px solid #0099cc; }
.sec { background:#fff; margin:0 10px 10px; padding:13px; border-radius:8px; }
.sec-h { display:flex; align-items:center; font-size:16px; font-weight:700; color:#20457c; margin-bottom:10px; }
.sec-h .bar { width:4px; height:16px; background:#0099cc; border-radius:2px; margin-right:7px; }
.sec-body { font-size:13.5px; color:#444; line-height:1.75; }
.att-grid { display:flex; flex-wrap:wrap; gap:8px; }
.att-card { width:calc(50% - 4px); border:1px solid #eef1f5; border-radius:8px; overflow:hidden; background:#fff; }
.att-img { width:100%; height:90px; object-fit:cover; display:block; }
.att-noimg { width:100%; height:90px; background:#e6eaf0; color:#aaa; display:flex; align-items:center; justify-content:center; font-size:12px; }
.att-b { padding:7px 9px; }
.att-nm { font-size:14px; font-weight:700; color:#20457c; }
.att-tg { font-size:11px; color:#888; margin-top:3px; line-height:1.5; }
.day { border-left:3px solid #0099cc; padding:2px 0 2px 11px; margin-bottom:11px; }
.day-c { font-size:13px; color:#444; line-height:1.7; white-space:pre-line; }
.day-t { display:block; font-weight:700; color:#20457c; font-size:14px; margin-bottom:3px; }
.tp-row { font-size:13px; color:#444; line-height:1.7; padding:5px 0; border-bottom:1px dashed #eef1f5; }
.tp-k { color:#0099cc; font-weight:700; margin-right:7px; }
.facts { display:flex; flex-wrap:wrap; background:#fff; margin:0 10px 10px; border-radius:8px; overflow:hidden; }
.fact { width:50%; padding:11px 13px; border-bottom:1px solid #eef1f5; }
.fact:nth-child(odd) { border-right:1px solid #eef1f5; }
.fact-k { font-size:11.5px; color:#999; }
.fact-v { font-size:15px; color:#20457c; font-weight:700; margin-top:3px; }
.fact-sub { font-size:11px; color:#999; font-weight:400; }
.route { display:flex; align-items:center; flex-wrap:wrap; gap:5px; background:#f0f7fb; border-radius:7px; padding:10px; }
.route-stop { background:#0099cc; color:#fff; padding:4px 9px; border-radius:12px; font-size:12.5px; font-weight:600; }
.route-arr { color:#0099cc; font-weight:700; }
.route-note { font-size:11.5px; color:#888; margin-top:7px; line-height:1.6; width:100%; }
.gallery { white-space:nowrap; overflow-x:auto; }
.gallery-img { display:inline-block; width:160px; height:110px; border-radius:6px; margin-right:7px; object-fit:cover; }
.act { border:1px solid #eef1f5; border-radius:7px; padding:10px 11px; margin-bottom:7px; }
.act-t { font-weight:700; color:#20457c; font-size:14px; display:flex; justify-content:space-between; align-items:center; gap:8px; }
.act-pr { font-size:11px; background:#fff1d6; color:#c47e00; padding:2px 7px; border-radius:9px; font-weight:700; white-space:nowrap; flex:0 0 auto; }
.act-m { font-size:12px; color:#777; margin-top:5px; line-height:1.6; }
.tips { background:#fff8ec; border:1px solid #ffe3b0; border-radius:7px; padding:11px; }
.tip-li { font-size:12.5px; color:#7a5b1e; padding:4px 0 4px 18px; position:relative; line-height:1.6; }
.tip-li::before { content:"\\26A0"; position:absolute; left:3px; top:4px; font-size:11px; }
.foot { text-align:center; color:#bbb; font-size:11px; padding:15px 0; }
"""

def hero(name, sub):
    img = first_image(name)
    if img:
        return f'<div class="hero"><img class="hero-img" src="{img}"><div class="hero-mask"></div><div class="hero-ttl"><div class="hero-name">{esc(name)}</div><div class="hero-sub">{esc(sub)}</div></div></div>'
    return f'<div class="sec" style="background:#ffe5e5"><div class="hero-name" style="color:#c00">[缺图灰块] {esc(name)}</div></div>'

def sec(title, body_html):
    return f'<div class="sec"><div class="sec-h"><span class="bar"></span>{esc(title)}</div>{body_html}</div>'

def render_attraction(d):
    h = [hero(d["name"], d.get("summary","")[:40])]
    h.append(f'<div class="lead">{esc(d.get("summary",""))}</div>')
    if d.get("facts"):
        fb = [f'<div class="fact"><div class="fact-k">{esc(f["k"])}</div><div class="fact-v">{esc(f["v"])} <span class="fact-sub">{esc(f.get("sub",""))}</span></div></div>' for f in d["facts"]]
        h.append(f'<div class="facts">{"".join(fb)}</div>')
    if d.get("route"):
        stops = '<span class="route-arr">→</span>'.join(f'<span class="route-stop">{esc(s)}</span>' for s in d["route"])
        h.append(sec("路线", f'<div class="route">{stops}<div class="route-note">{esc(d.get("route_note",""))}</div></div>'))
    gal = images_for(d["name"], 6)
    if len(gal) > 1:
        gimgs = "".join('<img class="gallery-img" src="%s">' % u for u in gal)
        h.append(sec("图集", '<div class="gallery">%s</div>' % gimgs))
    if d.get("activities"):
        ab = [f'<div class="act"><div class="act-t">{esc(a["name"])}<span class="act-pr">{esc(a.get("price",""))}</span></div><div class="act-m">{esc(a.get("detail",""))}</div></div>' for a in d["activities"]]
        h.append(sec("玩法", "".join(ab)))
    for s in d.get("sections", []):
        h.append(sec(s["title"], f'<div class="sec-body">{esc(s["content"])}</div>'))
    if d.get("tips"):
        tb = "".join(f'<div class="tip-li">{esc(t)}</div>' for t in d["tips"])
        h.append(sec("TIPS", f'<div class="tips">{tb}</div>'))
    h.append('<div class="foot">数据对齐 rilvtong.com · 仅供验收预览</div>')
    return "".join(h)

def city_hero_img(d):
    # backend fallback chain: city名 → page名 → 第一个有图的attraction
    return (first_image(d.get("city")) or first_image(d.get("name").replace("城市攻略",""))
            or next((first_image(a.get("image_alias") or a["name"]) for a in d.get("attractions",[]) if first_image(a.get("image_alias") or a["name"])), None))

def render_city(d):
    nm = d.get("name")
    img = city_hero_img(d)
    if img:
        h = [f'<div class="hero"><img class="hero-img" src="{img}"><div class="hero-mask"></div><div class="hero-ttl"><div class="hero-name">{esc(nm)}</div><div class="hero-sub">{esc(d.get("country"))} · {esc(d.get("city"))}</div></div></div>']
    else:
        h = [f'<div class="sec" style="background:#ffe5e5"><div class="hero-name" style="color:#c00">[缺图] {esc(nm)}</div></div>']
    h.append(f'<div class="lead">{esc(d.get("summary",""))}</div>')
    # 景点目录网格
    if d.get("attractions"):
        cards=[]
        for a in d["attractions"]:
            thumb=first_image(a.get("image_alias") or a["name"])
            imgd=f'<img class="att-img" src="{thumb}">' if thumb else '<div class="att-noimg">暂无图</div>'
            cards.append(f'<div class="att-card">{imgd}<div class="att-b"><div class="att-nm">{esc(a.get("display_name") or a["name"])}</div><div class="att-tg">{esc(a.get("tagline",""))}</div></div></div>')
        h.append(sec("景点目录", f'<div class="att-grid">{"".join(cards)}</div>'))
    # itinerary
    if d.get("itinerary"):
        days="".join(f'<div class="day"><div class="day-c"><text class="day-t">{esc(it.get("title"))}</text>{esc(it.get("detail"))}</div></div>' for it in d["itinerary"])
        h.append(sec("行程安排", days))
    # sections
    for s in d.get("sections", []):
        h.append(sec(s["title"], f'<div class="sec-body">{esc(s["content"])}</div>'))
    h.append('<div class="foot">数据对齐 rilvtong.com · 仅供验收预览</div>')
    return "".join(h)

def page(fn, kind):
    d = json.load(open(f"{PB}/{fn}", encoding="utf-8"))
    body = render_city(d) if kind=="city" else render_attraction(d)
    return f'<!DOCTYPE html><html><head><meta charset="utf-8"><style>{CSS}</style></head><body><div class="container">{body}</div></body></html>'

targets = {
    "01_恩纳村城市页.html": ("恩纳村城市攻略.json","city"),
    "02_万座毛.html": ("万座毛.json","attraction"),
    "03_海中公园.html": ("海中公园.json","attraction"),
}
for out,(fn,kind) in targets.items():
    open(f"{OUT}/{out}","w",encoding="utf-8").write(page(fn,kind))
    print("WROTE",out)
print("MANI数:",len(MANI))

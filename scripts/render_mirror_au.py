#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把瑞士 playbook JSON 渲染成 HTML 镜像（复刻 attraction.wxss + 后端挂图逻辑），用于截图验收。
1rpx = 0.5px（设计宽750rpx → 375px 手机）。图片用 file:// 绝对路径直接引用真实图库。"""
import json, os, re, html

ROOT = "/home/ubuntu/tools/travel_APP/travel_guide/data"
PB = f"{ROOT}/playbooks/澳大利亚"
IMG = f"{ROOT}/images"
MAPS = f"{ROOT}/maps"
OUT = "/home/ubuntu/.hermes-bot2/media_cache/au_verify"
os.makedirs(OUT, exist_ok=True)

# ---- 图库索引（复刻后端 ImageIndex.images_for / first_image）----
manifest = json.load(open(f"{IMG}/澳大利亚/manifest.json", encoding="utf-8"))
def images_for(name, limit=6):
    out = []
    for m in manifest:
        if m.get("status") == "ok" and m["attraction"] == name:
            pics = [m] + m.get("extras", [])
            for p in pics:
                fp = f"{IMG}/澳大利亚/{p['local']}"
                if os.path.exists(fp):
                    out.append(f"file://{fp}")
                if len(out) >= limit:
                    return out
    return out
def first_image(name):
    p = images_for(name, 1)
    return p[0] if p else None

def esc(s): return html.escape(str(s or ""))

# ---- CSS：把 wxss 的 rpx 全部 ÷2 转 px ----
CSS = """
* { box-sizing: border-box; margin:0; padding:0; }
body { background:#f2f4f7; font-family:-apple-system,'PingFang SC','Microsoft YaHei',sans-serif; width:375px; }
.container { padding-bottom:20px; }
.hero { position:relative; width:100%; height:190px; overflow:hidden; }
.hero-img { width:100%; height:100%; object-fit:cover; }
.hero-mask { position:absolute; left:0; right:0; bottom:0; height:60%; background:linear-gradient(to top,rgba(0,0,0,.6),rgba(0,0,0,0)); }
.hero-ttl { position:absolute; left:16px; bottom:14px; color:#fff; }
.hero-name { font-size:24px; font-weight:700; letter-spacing:1px; }
.hero-sub { font-size:13px; opacity:.9; margin-top:3px; }
.lead { font-size:13.5px; color:#555; line-height:1.7; background:#fff; margin:0 10px 10px; padding:12px; border-radius:8px; border-left:4px solid #0099cc; }
.sec { background:#fff; margin:0 10px 10px; padding:13px; border-radius:8px; }
.sec-h { display:flex; align-items:center; font-size:16px; font-weight:700; color:#20457c; margin-bottom:10px; }
.sec-h .bar { width:4px; height:16px; background:#0099cc; border-radius:2px; margin-right:7px; }
.sec-body { font-size:13.5px; color:#444; line-height:1.75; }
.mapbox { border-radius:7px; overflow:hidden; border:1px solid #e3e8ee; margin-bottom:9px; }
.map-img { width:100%; display:block; }
.map-cap { font-size:11.5px; color:#888; text-align:center; padding:6px; background:#fafbfc; }
.tp-row { font-size:13px; color:#555; line-height:1.7; margin-bottom:6px; }
.tp-k { color:#20457c; font-weight:600; margin-right:5px; }
.hotel { display:flex; gap:9px; padding:10px; border:1px solid #eef1f5; border-radius:7px; margin-bottom:7px; }
.hotel-score { flex:0 0 40px; height:40px; background:#0099cc; color:#fff; border-radius:6px; display:flex; align-items:center; justify-content:center; font-weight:700; font-size:16px; }
.hotel-info { flex:1; }
.hotel-name { font-weight:600; font-size:14px; color:#20457c; }
.hotel-go { font-size:11px; color:#0099cc; font-weight:400; }
.hotel-meta { font-size:11.5px; color:#888; margin-top:3px; line-height:1.5; }
.grid { display:flex; flex-wrap:wrap; justify-content:space-between; }
.att-card { width:48.5%; background:#fff; border-radius:8px; overflow:hidden; box-shadow:0 1px 6px rgba(0,0,0,.08); margin-bottom:9px; }
.att-ph { position:relative; width:100%; height:95px; background:#e8edf2; }
.att-img { width:100%; height:100%; object-fit:cover; }
.att-num { position:absolute; top:6px; left:6px; background:rgba(255,153,0,.95); color:#fff; font-size:11px; width:19px; height:19px; border-radius:50%; display:flex; align-items:center; justify-content:center; font-weight:700; }
.att-b { padding:8px 9px; }
.att-nm { font-weight:700; font-size:14px; color:#20457c; }
.att-ds { font-size:11px; color:#777; margin-top:3px; line-height:1.4; min-height:30px; }
.att-go { font-size:11px; color:#0099cc; margin-top:4px; font-weight:600; }
.day { display:flex; gap:9px; margin-bottom:8px; }
.day-d { flex:0 0 38px; height:38px; background:#20457c; color:#fff; border-radius:7px; display:flex; align-items:center; justify-content:center; font-size:16px; font-weight:700; }
.day-c { flex:1; background:#f7f9fb; border-radius:7px; padding:8px 10px; font-size:13px; color:#555; line-height:1.5; }
.day-t { display:block; color:#20457c; font-weight:600; margin-bottom:2px; }
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
.price { display:flex; align-items:baseline; flex-wrap:wrap; gap:6px; background:linear-gradient(135deg,#0099cc,#20457c); color:#fff; border-radius:8px; padding:13px 15px; margin-bottom:8px; }
.price-big { font-size:26px; font-weight:700; }
.price-u { font-size:13px; opacity:.9; }
.price-note { margin-left:auto; font-size:11.5px; opacity:.92; }
.act { border:1px solid #eef1f5; border-radius:7px; padding:10px 11px; margin-bottom:7px; }
.act-t { font-weight:700; color:#20457c; font-size:14px; display:flex; justify-content:space-between; align-items:center; }
.act-pr { font-size:11px; background:#fff1d6; color:#c47e00; padding:2px 7px; border-radius:9px; font-weight:700; }
.act-m { font-size:12px; color:#777; margin-top:5px; line-height:1.6; }
.gallery { white-space:nowrap; overflow-x:auto; }
.gallery-img { display:inline-block; width:160px; height:110px; border-radius:6px; margin-right:7px; object-fit:cover; }
.tips { background:#fff8ec; border:1px solid #ffe3b0; border-radius:7px; padding:11px; }
.tip-li { font-size:12.5px; color:#7a5b1e; padding:4px 0 4px 18px; position:relative; line-height:1.6; }
.tip-li::before { content:"⚠"; position:absolute; left:3px; top:4px; font-size:11px; }
.alt-box { background:#eef7f0; border-left:4px solid #2e7d32; border-radius:0 6px 6px 0; padding:10px 11px; font-size:12.5px; color:#2e5e36; line-height:1.65; }
.alt-k { display:block; font-weight:700; margin-bottom:3px; }
.foot { text-align:center; color:#bbb; font-size:11px; padding:15px 0; }
"""

def hero(name, sub):
    img = first_image(name)
    if img:
        return f'<div class="hero"><img class="hero-img" src="{img}"><div class="hero-mask"></div><div class="hero-ttl"><div class="hero-name">{esc(name)}</div><div class="hero-sub">{esc(sub)}</div></div></div>'
    return f'<div class="sec"><div class="hero-name" style="color:#20457c">{esc(name)}</div><div class="hero-sub" style="color:#888">{esc(sub)}</div></div>'

def sec(title, body_html):
    return f'<div class="sec"><div class="sec-h"><span class="bar"></span>{esc(title)}</div>{body_html}</div>'

def render_city(d):
    h = [hero(d["name"], d.get("summary","")[:40])]
    h.append(f'<div class="lead">{esc(d.get("summary",""))}</div>')
    # 交通
    tp = d.get("transport", {})
    tmap = d.get("transport_map","")
    tbody = []
    if tmap:
        mp = f"{MAPS}/{tmap.split('澳大利亚/')[-1]}" if "澳大利亚/" in tmap else f"{MAPS}/{tmap}"
        mp2 = f"{ROOT}/maps/{tmap}"
        if os.path.exists(mp2):
            tbody.append(f'<div class="mapbox"><img class="map-img" src="file://{mp2}"><div class="map-cap">城市间交通示意</div></div>')
    labels = {"fly_train":"✈ 飞机+火车","drive":"🚆 景观列车/自驾","local":"🚌 当地交通"}
    for k in ["fly_train","drive","local"]:
        if tp.get(k):
            tbody.append(f'<div class="tp-row"><span class="tp-k">{labels[k]}</span>{esc(tp[k])}</div>')
    if tbody:
        h.append(sec("交通", "".join(tbody)))
    # 酒店
    hotels = d.get("hotels", [])
    if hotels:
        hb = [f'<div class="lead-sm" style="font-size:12.5px;color:#777;margin-bottom:8px">{esc(d.get("hotel_intro",""))}</div>'] if d.get("hotel_intro") else []
        for ht in hotels:
            star = "★"*int(ht.get("star",0)) if ht.get("star") else ""
            hb.append(f'<div class="hotel"><div class="hotel-score">{esc(ht.get("score",""))}</div><div class="hotel-info"><div class="hotel-name">{esc(ht["name"])} <span class="hotel-go">订 ›</span></div><div class="hotel-meta">{star} {esc(ht.get("area",""))} · {esc(ht.get("reviews",""))}评价<br>{esc(ht.get("note",""))}</div></div></div>')
        h.append(sec("住哪里方便", "".join(hb)))
    # 景点目录网格
    atts = d.get("attractions", [])
    if atts:
        cards = []
        n = 0
        for a in atts:
            n += 1
            disp = a.get("display_name") or a["name"]
            img = first_image(a["name"])
            ph = f'<img class="att-img" src="{img}">' if img else '<div style="height:100%;display:flex;align-items:center;justify-content:center;color:#aab;font-size:11px">暂无图</div>'
            go = '<div class="att-go">查看详情 ›</div>' if a.get("has_detail") else ''
            cards.append(f'<div class="att-card"><div class="att-ph">{ph}<div class="att-num">{n}</div></div><div class="att-b"><div class="att-nm">{esc(disp)}</div><div class="att-ds">{esc(a.get("tagline",""))}</div>{go}</div></div>')
        h.append(sec("景点目录", f'<div class="grid">{"".join(cards)}</div>'))
    # 行程
    it = d.get("itinerary", [])
    if it:
        days = []
        for x in it:
            days.append(f'<div class="day"><div class="day-d">{esc(x["day"])}</div><div class="day-c"><span class="day-t">{esc(x["title"])}</span>{esc(x["detail"])}</div></div>')
        h.append(sec("行程建议", "".join(days)))
    # sections
    for s in d.get("sections", []):
        h.append(sec(s["title"], f'<div class="sec-body">{esc(s["content"])}</div>'))
    h.append('<div class="foot">数据对齐 oumengke.com · 仅供验收预览</div>')
    return "".join(h)

def render_attraction(d):
    h = [hero(d["name"], d.get("summary","")[:40])]
    h.append(f'<div class="lead">{esc(d.get("summary",""))}</div>')
    # facts
    facts = d.get("facts", [])
    if facts:
        fb = []
        for f in facts:
            fb.append(f'<div class="fact"><div class="fact-k">{esc(f["k"])}</div><div class="fact-v">{esc(f["v"])} <span class="fact-sub">{esc(f.get("sub",""))}</span></div></div>')
        h.append(f'<div class="facts">{"".join(fb)}</div>')
    # price
    pr = d.get("price")
    if pr:
        h.append(f'<div class="sec"><div class="price"><span class="price-big">{esc(pr["main"])}</span><span class="price-u">{esc(pr.get("unit",""))}</span><span class="price-note">{esc(pr.get("note",""))}</span></div><div class="sec-body">{esc(pr.get("detail",""))}</div></div>')
    # route
    rt = d.get("route", [])
    if rt:
        stops = '<span class="route-arr">→</span>'.join(f'<span class="route-stop">{esc(s)}</span>' for s in rt)
        h.append(sec("路线", f'<div class="route">{stops}<div class="route-note">{esc(d.get("route_note",""))}</div></div>'))
    # gallery
    gal = images_for(d["name"], 6)
    if len(gal) > 1:
        imgs = "".join(f'<img class="gallery-img" src="{u}">' for u in gal)
        h.append(sec("图集", f'<div class="gallery">{imgs}</div>'))
    # activities
    acts = d.get("activities", [])
    if acts:
        ab = []
        for a in acts:
            ab.append(f'<div class="act"><div class="act-t">{esc(a["name"])}<span class="act-pr">{esc(a.get("price",""))}</span></div><div class="act-m">{esc(a.get("detail",""))}</div></div>')
        h.append(sec("玩法", "".join(ab)))
    # sections
    for s in d.get("sections", []):
        h.append(sec(s["title"], f'<div class="sec-body">{esc(s["content"])}</div>'))
    # tips
    tips = d.get("tips", [])
    if tips:
        tb = "".join(f'<div class="tip-li">{esc(t)}</div>' for t in tips)
        h.append(sec("TIPS", f'<div class="tips">{tb}</div>'))
    # alt
    if d.get("alt"):
        h.append(f'<div class="sec"><div class="alt-box"><span class="alt-k">替代方案</span>{esc(d["alt"])}</div></div>')
    h.append('<div class="foot">数据对齐 oumengke.com · 仅供验收预览</div>')
    return "".join(h)

def page(fn):
    d = json.load(open(f"{PB}/{fn}", encoding="utf-8"))
    body = render_city(d) if d.get("type")=="city" else render_attraction(d)
    return f'<!DOCTYPE html><html><head><meta charset="utf-8"><style>{CSS}</style></head><body><div class="container">{body}</div></body></html>'

targets = {
    "01_city_sydney.html": "悉尼城市攻略.json",
}
for out, fn in targets.items():
    html_str = page(fn)
    with open(f"{OUT}/{out}", "w", encoding="utf-8") as f:
        f.write(html_str)
    print(f"WROTE {OUT}/{out}")

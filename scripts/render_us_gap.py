#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""渲染美国8个断链景点详情页HTML镜像（复刻 attraction.wxss），跨3个图库目录读manifest，用于截图验收。"""
import json, os, html, glob

ROOT = "/home/ubuntu/tools/travel_APP/travel_guide/data"
PB = f"{ROOT}/playbooks/美国"
IMG = f"{ROOT}/images"
OUT = "/home/ubuntu/.hermes-bot2/media_cache/us_gap_verify"
os.makedirs(OUT, exist_ok=True)

# 读全部manifest（含子目录），建 attraction -> [file://...] 索引
MANI = {}
for mf in glob.glob(f"{IMG}/*/manifest.json"):
    subdir = os.path.dirname(mf)
    try:
        data = json.load(open(mf, encoding="utf-8"))
    except Exception:
        continue
    for m in data:
        if m.get("status") != "ok":
            continue
        attr = m.get("attraction")
        if not attr:
            continue
        pics = [m] + m.get("extras", [])
        for p in pics:
            local = p.get("local")
            if not local:
                continue
            fp = f"{subdir}/{local}"
            if os.path.exists(fp):
                MANI.setdefault(attr, []).append(f"file://{fp}")

def images_for(name, limit=6):
    return MANI.get(name, [])[:limit]
def first_image(name):
    p = images_for(name, 1)
    return p[0] if p else None
def esc(s): return html.escape(str(s or ""))

# 复刻 render_la.py 的 CSS
CSS = """
* { box-sizing: border-box; margin:0; padding:0; }
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

def render_attraction(d, display_name):
    h = [hero(d["name"], d.get("summary","")[:40])]
    h.append(f'<div class="lead">{esc(d.get("summary",""))}</div>')
    facts = d.get("facts", [])
    if facts:
        fb = [f'<div class="fact"><div class="fact-k">{esc(f["k"])}</div><div class="fact-v">{esc(f["v"])} <span class="fact-sub">{esc(f.get("sub",""))}</span></div></div>' for f in facts]
        h.append(f'<div class="facts">{"".join(fb)}</div>')
    rt = d.get("route", [])
    if rt:
        stops = '<span class="route-arr">→</span>'.join(f'<span class="route-stop">{esc(s)}</span>' for s in rt)
        h.append(sec("路线", f'<div class="route">{stops}<div class="route-note">{esc(d.get("route_note",""))}</div></div>'))
    gal = images_for(d["name"], 6)
    if len(gal) > 1:
        imgs = "".join(f'<img class="gallery-img" src="{u}">' for u in gal)
        h.append(sec("图集", f'<div class="gallery">{imgs}</div>'))
    acts = d.get("activities", [])
    if acts:
        ab = [f'<div class="act"><div class="act-t">{esc(a["name"])}<span class="act-pr">{esc(a.get("price",""))}</span></div><div class="act-m">{esc(a.get("detail",""))}</div></div>' for a in acts]
        h.append(sec("玩法", "".join(ab)))
    for s in d.get("sections", []):
        h.append(sec(s["title"], f'<div class="sec-body">{esc(s["content"])}</div>'))
    tips = d.get("tips", [])
    if tips:
        tb = "".join(f'<div class="tip-li">{esc(t)}</div>' for t in tips)
        h.append(sec("TIPS", f'<div class="tips">{tb}</div>'))
    h.append('<div class="foot">数据对齐 meilvtong.com · 仅供验收预览</div>')
    return "".join(h)

def page(fn):
    d = json.load(open(f"{PB}/{fn}", encoding="utf-8"))
    body = render_attraction(d, d["name"])
    return f'<!DOCTYPE html><html><head><meta charset="utf-8"><style>{CSS}</style></head><body><div class="container">{body}</div></body></html>'

targets = {
    "01_休斯顿太空中心.html": "休斯顿太空中心.json",
    "02_夏威夷火山国家公园.html": "夏威夷火山国家公园.json",
    "03_奥兰多环球影城.html": "奥兰多环球影城.json",
    "04_迪士尼乐园区.html": "迪士尼乐园区.json",
    "05_SeaWorld海洋世界.html": "SeaWorld海洋世界.json",
    "06_SantaCruz.html": "Santa Cruz.json",
    "07_芝加哥艺术博物馆.html": "芝加哥艺术博物馆.json",
    "08_哈雷阿卡拉国家公园.html": "哈雷阿卡拉国家公园.json",
    "09_哈纳之路.html": "哈纳之路.json",
}
for out, fn in targets.items():
    with open(f"{OUT}/{out}", "w", encoding="utf-8") as f:
        f.write(page(fn))
    print(f"WROTE {out}")
print(f"\nMANI索引attraction数: {len(MANI)}")

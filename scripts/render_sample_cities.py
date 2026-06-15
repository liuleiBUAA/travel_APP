#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Sample city-page render preview across continents. Clones render_enna.py logic
but with a cross-continent targets list (国家/文件名)."""
import json, os, html, glob

ROOT = "/home/ubuntu/tools/travel_APP/travel_guide/data"
PBROOT = f"{ROOT}/playbooks"
IMG = f"{ROOT}/images"
OUT = "/home/ubuntu/.hermes-bot2/media_cache/sample_cities"
os.makedirs(OUT, exist_ok=True)

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
        for p in [m] + m.get("extras", []):
            local = p.get("local")
            if not local:
                continue
            fp = f"{subdir}/{local}"
            if os.path.exists(fp):
                MANI.setdefault(attr, []).append(f"file://{fp}")

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
.att-card { width:calc(50% - 4px); border:1px solid #eef1f5; border-radius:8px; overflow:hidden; background:#fff; position:relative; }
.att-img { width:100%; height:90px; object-fit:cover; display:block; }
.att-noimg { width:100%; height:90px; background:#e6eaf0; color:#aaa; display:flex; align-items:center; justify-content:center; font-size:12px; }
.att-b { padding:7px 9px; }
.att-nm { font-size:14px; font-weight:700; color:#20457c; }
.att-tg { font-size:11px; color:#888; margin-top:3px; line-height:1.5; }
.dot { position:absolute; top:6px; right:6px; font-size:10px; padding:2px 6px; border-radius:8px; font-weight:700; }
.dot.on { background:#2ecc71; color:#fff; }
.dot.off { background:rgba(0,0,0,.45); color:#fff; }
.foot { text-align:center; color:#bbb; font-size:11px; padding:15px 0; }
"""

def city_hero_img(d):
    return (first_image(d.get("city")) or first_image(d.get("name","").replace("城市攻略",""))
            or next((first_image(a.get("image_alias") or a["name"]) for a in d.get("attractions",[]) if first_image(a.get("image_alias") or a["name"])), None))

def sec(title, body_html):
    return f'<div class="sec"><div class="sec-h"><span class="bar"></span>{esc(title)}</div>{body_html}</div>'

def render_city(d):
    nm = d.get("name")
    img = city_hero_img(d)
    if img:
        h = [f'<div class="hero"><img class="hero-img" src="{img}"><div class="hero-mask"></div><div class="hero-ttl"><div class="hero-name">{esc(nm)}</div><div class="hero-sub">{esc(d.get("country"))} · {esc(d.get("city"))}</div></div></div>']
    else:
        h = [f'<div class="sec" style="background:#ffe5e5"><div class="hero-name" style="color:#c00">[缺图] {esc(nm)}</div></div>']
    h.append(f'<div class="lead">{esc(d.get("summary",""))}</div>')
    if d.get("attractions"):
        cards=[]
        for a in d["attractions"]:
            thumb=first_image(a.get("image_alias") or a["name"])
            imgd=f'<img class="att-img" src="{thumb}">' if thumb else '<div class="att-noimg">暂无图(灰块)</div>'
            dot='<span class="dot on">可点</span>' if a.get("has_detail") else '<span class="dot off">展示</span>'
            cards.append(f'<div class="att-card">{dot}{imgd}<div class="att-b"><div class="att-nm">{esc(a.get("display_name") or a["name"])}</div><div class="att-tg">{esc(a.get("tagline",""))}</div></div></div>')
        h.append(sec(f"景点目录（{len(d['attractions'])}卡）", f'<div class="att-grid">{"".join(cards)}</div>'))
    h.append('<div class="foot">仅供验收预览 · 🟢可点=有详情页 ⚫展示=点不进</div>')
    return "".join(h)

targets = {
    "EU1_因特拉肯.html": "瑞士/因特拉肯城市攻略.json",
    "EU2_罗马.html": "意大利/罗马城市攻略.json",
    "NA1_旧金山.html": "美国/旧金山城市攻略.json",
    "NA2_纽约.html": "美国/纽约城市攻略.json",
    "OC1_黄金海岸.html": "澳大利亚/黄金海岸城市攻略.json",
    "OC2_悉尼.html": "澳大利亚/悉尼城市攻略.json",
    "JP1_东京.html": "日本/东京城市攻略.json",
    "JP2_恩纳村.html": "日本/恩纳村城市攻略.json",
    "ME1_迪拜.html": "阿联酋/迪拜城市攻略.json",
}
for out, rel in targets.items():
    d = json.load(open(f"{PBROOT}/{rel}", encoding="utf-8"))
    body = render_city(d)
    doc = f'<!DOCTYPE html><html><head><meta charset="utf-8"><style>{CSS}</style></head><body><div class="container">{body}</div></body></html>'
    open(f"{OUT}/{out}", "w", encoding="utf-8").write(doc)
    print("WROTE", out)
print("MANI数:", len(MANI))

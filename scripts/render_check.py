#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""通用渲染器：从正式 playbooks 目录渲染任意国家景点/城市页为HTML，跨区域加载图库。
复刻 attraction.wxml/wxss + 后端挂图逻辑，用于抽查没验证的批次效果。"""
import json, os, html, glob, sys

ROOT = "/home/ubuntu/tools/travel_APP/travel_guide/data"
PB = f"{ROOT}/playbooks"
IMG = f"{ROOT}/images"
OUT = "/home/ubuntu/.hermes-bot2/media_cache/check_verify"
os.makedirs(OUT, exist_ok=True)

# 加载所有区域 manifest（跨区域匹配，复刻后端 ImageIndex glob 所有 manifest）
ALLMAN = []
for m in glob.glob(f"{IMG}/*/manifest.json"):
    region = os.path.basename(os.path.dirname(m))
    for x in json.load(open(m, encoding="utf-8")):
        x["_region"] = region
        ALLMAN.append(x)

def images_for(name, limit=6):
    out = []
    for m in ALLMAN:
        if m.get("status") == "ok" and m.get("attraction") == name:
            for p in [m] + m.get("extras", []):
                fp = f"{IMG}/{m['_region']}/{p['local']}"
                if os.path.exists(fp):
                    out.append(f"file://{fp}")
                if len(out) >= limit:
                    return out
    return out

def first_image(name):
    p = images_for(name, 1)
    return p[0] if p else None

def esc(s): return html.escape(str(s or ""))

CSS = """
* { box-sizing:border-box; margin:0; padding:0; }
body { background:#f2f4f7; font-family:-apple-system,'PingFang SC','Microsoft YaHei',sans-serif; width:375px; }
.container { padding-bottom:20px; }
.hero { position:relative; width:100%; height:190px; overflow:hidden; background:#20457c; }
.hero-img { width:100%; height:100%; object-fit:cover; }
.hero-mask { position:absolute; left:0; right:0; bottom:0; height:60%; background:linear-gradient(to top,rgba(0,0,0,.6),rgba(0,0,0,0)); }
.hero-ttl { position:absolute; left:16px; bottom:14px; color:#fff; }
.hero-name { font-size:24px; font-weight:700; letter-spacing:1px; }
.hero-sub { font-size:13px; opacity:.9; margin-top:3px; }
.lead { font-size:13.5px; color:#555; line-height:1.7; background:#fff; margin:0 10px 10px; padding:12px; border-radius:8px; border-left:4px solid #0099cc; }
.facts { display:flex; flex-wrap:wrap; background:#fff; margin:0 10px 10px; padding:6px; border-radius:8px; }
.fact { flex:0 0 50%; padding:7px 10px; }
.fact-k { font-size:11.5px; color:#888; }
.fact-v { font-size:13px; color:#222; font-weight:600; margin-top:2px; }
.fact-sub { font-size:11px; color:#aaa; font-weight:400; }
.price { background:#fff7e6; color:#d48806; font-size:14px; font-weight:600; margin:0 10px 10px; padding:11px 13px; border-radius:8px; }
.sec { background:#fff; margin:0 10px 10px; padding:13px; border-radius:8px; }
.sec-h { display:flex; align-items:center; font-size:16px; font-weight:700; color:#20457c; margin-bottom:10px; }
.sec-h .bar { width:4px; height:16px; background:#0099cc; border-radius:2px; margin-right:7px; }
.sec-body { font-size:13.5px; color:#444; line-height:1.75; white-space:pre-wrap; }
.chips { margin:0 10px 10px; }
.chip-h { font-size:15px; font-weight:700; color:#20457c; margin:4px 0 9px; }
.acts { display:flex; flex-wrap:wrap; gap:7px; }
.act { background:#e8f4fa; color:#0a6e91; font-size:12.5px; padding:6px 11px; border-radius:14px; }
.tips { background:#fff; margin:0 10px 10px; padding:13px; border-radius:8px; }
.tip { font-size:13px; color:#555; line-height:1.7; padding-left:16px; position:relative; margin-bottom:5px; }
.tip:before { content:"•"; position:absolute; left:3px; color:#0099cc; }
.gal { display:flex; gap:6px; overflow-x:auto; margin:0 10px 10px; }
.gal img { height:110px; border-radius:7px; }
.grid { display:flex; flex-wrap:wrap; margin:0 6px; }
.card { flex:0 0 50%; padding:4px; }
.card-in { background:#fff; border-radius:8px; overflow:hidden; }
.card-img { width:100%; height:90px; object-fit:cover; background:#dde; }
.card-b { padding:7px 9px; }
.card-n { font-size:13.5px; font-weight:600; color:#222; }
.card-d { font-size:11px; color:#888; margin-top:3px; line-height:1.4; }
.card-go { font-size:11px; color:#0099cc; margin-top:4px; }
"""

def render_attraction(d):
    name = d.get("name", "")
    h = ['<div class="container">']
    hero = first_image(name)
    h.append('<div class="hero">')
    if hero: h.append(f'<img class="hero-img" src="{hero}">')
    h.append(f'<div class="hero-mask"></div><div class="hero-ttl"><div class="hero-name">{esc(name)}</div>')
    if d.get("city"): h.append(f'<div class="hero-sub">{esc(d.get("city"))} · {esc(d.get("country"))}</div>')
    h.append('</div></div>')
    if d.get("summary"): h.append(f'<div class="lead">{esc(d["summary"])}</div>')
    # facts (list格式)
    facts = d.get("facts", [])
    if isinstance(facts, list) and facts:
        fb = []
        for f in facts:
            sub = f' <span class="fact-sub">{esc(f.get("sub"))}</span>' if f.get("sub") else ""
            fb.append(f'<div class="fact"><div class="fact-k">{esc(f.get("k"))}</div><div class="fact-v">{esc(f.get("v"))}{sub}</div></div>')
        h.append(f'<div class="facts">{"".join(fb)}</div>')
    elif isinstance(facts, dict) and facts:
        h.append('<div class="facts" style="border:2px solid red;">')
        h.append('<div class="fact" style="color:red;">⚠️dict格式facts前端不渲染</div>')
        h.append('</div>')
    if d.get("price"): pass  # 票价卡已移除(对齐前端)，价格信息在facts里
    # gallery
    gal = images_for(name, 6)
    if len(gal) > 1:
        h.append('<div class="gal">' + "".join(f'<img src="{g}">' for g in gal[1:]) + '</div>')
    # activities (dict格式: name/price/detail, 对齐前端)
    acts = d.get("activities", [])
    if acts:
        h.append('<div class="sec"><div class="sec-h"><span class="bar"></span>玩什么</div>')
        for a in acts:
            if isinstance(a, dict):
                pr = f' <span class="act-pr" style="color:#d48806;font-size:12px;">{esc(a.get("price"))}</span>' if a.get("price") else ""
                h.append(f'<div style="margin-bottom:9px;"><div style="font-size:14px;font-weight:600;color:#20457c;">{esc(a.get("name"))}{pr}</div>')
                h.append(f'<div style="font-size:12.5px;color:#555;line-height:1.6;margin-top:3px;">{esc(a.get("detail"))}</div></div>')
            else:
                h.append(f'<div class="act">{esc(a)}</div>')
        h.append('</div>')
    # sections
    for s in d.get("sections", []):
        h.append(f'<div class="sec"><div class="sec-h"><span class="bar"></span>{esc(s.get("title"))}</div>')
        h.append(f'<div class="sec-body">{esc(s.get("content"))}</div></div>')
    # tips
    tips = d.get("tips", [])
    if tips:
        h.append('<div class="tips"><div class="sec-h"><span class="bar"></span>实用贴士</div>')
        h.append("".join(f'<div class="tip">{esc(t)}</div>' for t in tips))
        h.append('</div>')
    h.append('</div>')
    return "".join(h)

def render_city(d):
    name = d.get("name", "")
    h = ['<div class="container">']
    # hero: 城市同名图 -> 第一个有图景点(用image_alias兜底,对齐后端)
    hero = first_image(name)
    if not hero:
        for a in d.get("attractions", []):
            hero = first_image(a.get("image_alias") or a["name"])
            if hero: break
    h.append('<div class="hero">')
    if hero: h.append(f'<img class="hero-img" src="{hero}">')
    h.append(f'<div class="hero-mask"></div><div class="hero-ttl"><div class="hero-name">{esc(name)}</div>')
    h.append(f'<div class="hero-sub">{esc(d.get("country"))}</div></div></div>')
    if d.get("summary"): h.append(f'<div class="lead">{esc(d["summary"])}</div>')
    # 景点网格
    h.append('<div class="grid">')
    for a in d.get("attractions", []):
        img = first_image(a.get("image_alias") or a["name"])
        imgtag = f'<img class="card-img" src="{img}">' if img else '<div class="card-img"></div>'
        go = '<div class="card-go">查看详情 ›</div>' if a.get("has_detail") else ""
        desc = a.get("desc") or a.get("tagline") or ""
        h.append(f'<div class="card"><div class="card-in">{imgtag}<div class="card-b"><div class="card-n">{esc(a["name"])}</div><div class="card-d">{esc(desc)[:36]}</div>{go}</div></div></div>')
    h.append('</div>')
    # sections
    for s in d.get("sections", []):
        h.append(f'<div class="sec"><div class="sec-h"><span class="bar"></span>{esc(s.get("title"))}</div>')
        h.append(f'<div class="sec-body">{esc(s.get("content"))}</div></div>')
    h.append('</div>')
    return "".join(h)

def render_file(relpath):
    d = json.load(open(f"{PB}/{relpath}", encoding="utf-8"))
    body = render_city(d) if d.get("type") == "city" else render_attraction(d)
    page = f'<!DOCTYPE html><html><head><meta charset="utf-8"><style>{CSS}</style></head><body>{body}</body></html>'
    out = f"{OUT}/{relpath.replace('/','_').replace('.json','')}.html"
    open(out, "w", encoding="utf-8").write(page)
    return out

if __name__ == "__main__":
    targets = sys.argv[1:] or [
        "意大利/斗兽场.json", "法国/凡尔赛宫.json", "德国/国王湖.json",
        "土耳其/蓝色清真寺.json", "意大利/罗马城市攻略.json",
    ]
    for t in targets:
        print(render_file(t))

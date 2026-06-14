#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""为因特拉肯补 蓝湖自然公园 / 哈德库尔姆观景台 抓 Pexels 真实图，写入图库+manifest。"""
import os, json, requests, time

ROOT = "/home/ubuntu/tools/travel_APP/travel_guide/data"
IMGDIR = f"{ROOT}/images/瑞士/因特拉肯"
MANIFEST = f"{ROOT}/images/瑞士/manifest.json"
KEY = None
for line in open("/home/ubuntu/tools/travel_APP/.env"):
    if line.startswith("PEXELS_KEY="):
        KEY = line.split("=", 1)[1].strip()
assert KEY, "no PEXELS_KEY"
os.makedirs(IMGDIR, exist_ok=True)

# 景点 → 搜索词（用具体地名提高命中率）
JOBS = {
    "蓝湖自然公园": "Blausee lake Kandersteg Switzerland turquoise",
    "哈德库尔姆观景台": "Harder Kulm Interlaken viewpoint two lakes panorama",
}

def search(q, n=3):
    r = requests.get("https://api.pexels.com/v1/search",
                     headers={"Authorization": KEY},
                     params={"query": q, "per_page": n, "orientation": "landscape"},
                     timeout=30)
    r.raise_for_status()
    return r.json().get("photos", [])

def dl(url, path):
    r = requests.get(url, timeout=60); r.raise_for_status()
    with open(path, "wb") as f: f.write(r.content)
    return len(r.content)

manifest = json.load(open(MANIFEST, encoding="utf-8"))
existing = {(m["city"], m["attraction"]) for m in manifest}

for attr, q in JOBS.items():
    if ("因特拉肯", attr) in existing:
        print(f"SKIP {attr} (已在manifest)"); continue
    photos = search(q, 3)
    print(f"\n{attr}: 搜到 {len(photos)} 张  q={q!r}")
    if not photos:
        print("  ⚠ 无结果"); continue
    saved = []
    for i, p in enumerate(photos, 1):
        fn = f"{attr}_{i}.jpg"
        sz = dl(p["src"]["large"], f"{IMGDIR}/{fn}")
        saved.append({"local": f"因特拉肯/{fn}", "license": "Pexels",
                      "artist": p.get("photographer", ""),
                      "commons_file": f"pexels:{p['id']}", "source": f"pexels:{q}"})
        print(f"  ✓ {fn}  {sz//1024}KB  by {p.get('photographer')}")
        time.sleep(0.5)
    entry = {"city": "因特拉肯", "attraction": attr, "status": "ok", **saved[0],
             "extras": saved[1:]}
    manifest.append(entry)

json.dump(manifest, open(MANIFEST, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"\n✅ manifest 更新，共 {len(manifest)} 条")

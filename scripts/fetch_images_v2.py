#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""强化版补图 pipeline：Pexels 抓候选 -> 黑白自动过滤 -> 生成候选拼图供用户肉眼挑选。

针对两个历史坑：
1. 黑白图混入（悉尼歌剧院黑白照被用户怒斥）-> 每张候选用 PIL 算 RGB 通道差，灰度图直接丢弃。
2. 配错图 -> 候选不自动落库，先抓 N 张彩色候选生成拼图，发用户肉眼挑选确认才落库。

用法:
    抓候选:  python3 fetch_images_v2.py fetch <queries.json> <候选输出目录>
    queries.json: [{"city","attraction","query"}, ...]  query=核准过的英文搜索词

输出: <候选目录>/<attraction>/cand_1.jpg ... + candidates.json（记录每张的灰度分/Pexels元数据）
只下载彩色候选（灰度分>=阈值）。每景点抓到 N_KEEP 张彩色为止。
"""
import json, os, re, sys, time, urllib.request, urllib.parse, urllib.error, statistics, io
from PIL import Image

KEY = ""
for _l in open(os.path.join(os.path.dirname(__file__), "..", ".env")):
    if _l.startswith("PEXELS_KEY="):
        KEY = _l.split("=", 1)[1].strip().strip('"')
HEADERS = {"Authorization": KEY, "User-Agent": "TravelGuideBot/2.0"}
GRAY_THRESH = 14      # 灰度分 < 此值判黑白丢弃（彩色图通常 >20）
N_FETCH = 8           # 每景点拉几张候选来筛
N_KEEP = 4            # 每景点保留几张彩色候选供挑选
DELAY = 0.8


def gray_score(data):
    im = Image.open(io.BytesIO(data)).convert("RGB").resize((80, 80))
    px = list(im.getdata())
    return statistics.mean([max(r, g, b) - min(r, g, b) for r, g, b in px])


def api_get(url):
    while True:
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code == 429:
                print("\n[限速] 等60分钟...", flush=True); time.sleep(3600); continue
            raise


def search(query, n):
    q = urllib.parse.quote(query)
    data = api_get(f"https://api.pexels.com/v1/search?query={q}&per_page={n}&orientation=landscape")
    return data.get("photos", [])


def dl(url):
    req = urllib.request.Request(url, headers={"User-Agent": "TravelGuideBot/2.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def safe(s):
    return re.sub(r'[\\/:*?"<>|（）()]', "_", s)


def fetch(queries_path, out_dir):
    rows = json.load(open(queries_path, encoding="utf-8"))
    os.makedirs(out_dir, exist_ok=True)
    allcand = []
    for i, row in enumerate(rows):
        city, att, query = row["city"], row["attraction"], row["query"]
        adir = os.path.join(out_dir, safe(att))
        os.makedirs(adir, exist_ok=True)
        print(f"[{i+1}/{len(rows)}] {att} «{query}» ...", end=" ", flush=True)
        try:
            photos = search(query, N_FETCH)
        except Exception as e:
            print(f"ERR {e}"); continue
        kept = []
        for p in photos:
            if len(kept) >= N_KEEP:
                break
            try:
                data = dl(p["src"]["large"])
                g = gray_score(data)
            except Exception as e:
                print(f"(dl err)", end=""); continue
            if g < GRAY_THRESH:
                print(f"(丢黑白{g:.0f})", end=""); continue
            n = len(kept) + 1
            fp = os.path.join(adir, f"cand_{n}.jpg")
            open(fp, "wb").write(data)
            kept.append({"city": city, "attraction": att, "query": query,
                         "cand": n, "local": os.path.relpath(fp, out_dir),
                         "gray": round(g, 1), "pexels_id": p["id"],
                         "artist": p.get("photographer", ""), "alt": p.get("alt", ""),
                         "url_large": p["src"]["large"]})
            time.sleep(DELAY)
        allcand.extend(kept)
        print(f"保留{len(kept)}张彩色")
        time.sleep(DELAY)
    json.dump(allcand, open(os.path.join(out_dir, "candidates.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(f"\n候选写入 {out_dir}/candidates.json，共 {len(allcand)} 张")


if __name__ == "__main__":
    if sys.argv[1] == "fetch":
        fetch(sys.argv[2], sys.argv[3])

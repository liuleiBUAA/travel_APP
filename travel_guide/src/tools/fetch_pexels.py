"""用 Pexels 给景点抓专业摄影图（经典机位）。

Pexels 许可证允许下载、自托管、商用、无需署名——适合存进自己服务器的图库
（Unsplash 要求热链接+署名，不适合自托管，故不用）。

搜索词必须人工核准（queries.json 对照表），不让脚本按中文名瞎猜——
中文名歧义会配错图（"天空之城"搜成动画、"米开朗基罗广场"搜成人物肖像）。

用法:
    PEXELS_KEY=xxx python3 fetch_pexels.py <queries.json> <国家> <输出目录>

queries.json: [{"city","attraction","query"}, ...]，query 是核准过的英文搜索词。
每个景点抓前 N 张（主图 + extras），写入 <输出目录>/manifest.json，格式与
fetch_attraction_images.py 一致（city/attraction/status/local/license/artist/
commons_file/source/extras），下游 ImageIndex 无需改动。断点续跑。
"""
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

API = "https://api.pexels.com/v1"
KEY = os.environ.get("PEXELS_KEY", "")
PER_ATTRACTION = 3  # 每景点抓几张（1主图 + 2 extras）
DELAY = 1.0

if not KEY:
    sys.exit("缺 PEXELS_KEY 环境变量")

HEADERS = {"Authorization": KEY, "User-Agent": "TravelGuideBot/1.0"}


def api_get(url):
    """免费 key 限速 200次/小时；撞限速（429）就等到下个整点再继续。"""
    while True:
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code == 429:  # Rate Limit Exceeded
                print("\n[限速] 等 60 分钟到额度重置 ... ", flush=True)
                time.sleep(3600)
                continue
            raise


def search(query, n):
    """返回前 n 张候选 [{id, url, artist, desc}]，横图优先。"""
    q = urllib.parse.quote(query)
    data = api_get(f"{API}/search?query={q}&per_page={n}&orientation=landscape")
    out = []
    for p in data.get("photos", []):
        out.append({
            "id": p["id"],
            # large = 长边约1880px，配图够用且体积可控
            "url": p["src"]["large"],
            "artist": p.get("photographer", ""),
            "desc": p.get("alt", ""),
        })
    return out


def download(url, path):
    req = urllib.request.Request(url, headers={"User-Agent": "TravelGuideBot/1.0"})
    with urllib.request.urlopen(req, timeout=60) as r, open(path, "wb") as f:
        f.write(r.read())


def safe_name(s):
    return re.sub(r'[\\/:*?"<>|（）()]', "_", s)


def main(queries_path, country, out_dir):
    rows = json.load(open(queries_path, encoding="utf-8"))
    # 断点续跑：沿用上次 manifest 里已成功的条目
    done = {}
    manifest_path = os.path.join(out_dir, "manifest.json")
    if os.path.exists(manifest_path):
        for m in json.load(open(manifest_path, encoding="utf-8")):
            if m.get("status") == "ok":
                done[(m["city"], m["attraction"])] = m
    manifest = []
    hit = 0
    for i, row in enumerate(rows):
        city, attraction, query = row["city"], row["attraction"], row["query"]
        if (city, attraction) in done:
            manifest.append(done[(city, attraction)])
            hit += 1
            print(f"[{i+1}/{len(rows)}] {city} / {attraction}  已有，跳过")
            continue
        print(f"[{i+1}/{len(rows)}] {city} / {attraction}  «{query}» ... ", end="", flush=True)
        try:
            cands = search(query, PER_ATTRACTION)
        except Exception as e:
            print(f"ERROR {e}")
            manifest.append({"city": city, "attraction": attraction, "status": "error", "error": str(e)})
            time.sleep(DELAY)
            continue
        if not cands:
            print("无结果")
            manifest.append({"city": city, "attraction": attraction, "status": "miss"})
            time.sleep(DELAY)
            continue
        city_dir = os.path.join(out_dir, safe_name(city))
        os.makedirs(city_dir, exist_ok=True)
        saved = []
        for n, c in enumerate(cands):
            local = os.path.join(city_dir, safe_name(attraction) + f"_{n+1}.jpg")
            try:
                download(c["url"], local)
            except Exception as e:
                print(f"(第{n+1}张下载失败{e})", end="")
                continue
            saved.append({
                "local": os.path.relpath(local, out_dir),
                "license": "Pexels",
                "artist": c["artist"][:80],
                "commons_file": f"pexels:{c['id']}",
                "source": f"pexels:{query}",
            })
            time.sleep(DELAY)
        if not saved:
            print("全部下载失败")
            manifest.append({"city": city, "attraction": attraction, "status": "error"})
            continue
        main_img = saved[0]
        entry = {"city": city, "attraction": attraction, "status": "ok",
                 "local": main_img["local"], "license": main_img["license"],
                 "artist": main_img["artist"], "commons_file": main_img["commons_file"],
                 "source": main_img["source"]}
        if saved[1:]:
            entry["extras"] = saved[1:]
        manifest.append(entry)
        hit += 1
        print(f"OK ({len(saved)}张)")
        time.sleep(DELAY)

    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1)
    print(f"\n命中 {hit}/{len(rows)}，manifest 写入 {manifest_path}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3])

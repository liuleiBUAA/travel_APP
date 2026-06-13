#!/usr/bin/env python3
"""给景点查经纬度，建坐标缓存。

英文名来自 image_queries/queries_<国家>.json（抓图时已有），
geocoder 用 Photon（komoot 公共服务，认英文名，不限本机 IP）。
中文名查不准，所以一律用英文 query。

输出: travel_guide/data/geo/<国家>_coords.json
  { "卢浮宫": {"lat":..., "lon":..., "query":"Louvre Museum Paris"}, ... }
查一次存一次，已存在的不重复请求（幂等，可断点续跑）。
"""
import json
import sys
import time
import urllib.request
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]  # travel_guide/
QUERIES_DIR = ROOT / "data" / "image_queries"
GEO_DIR = ROOT / "data" / "geo"


def photon(query, tries=3):
    url = "https://photon.komoot.io/api/?" + urllib.parse.urlencode({"q": query, "limit": 1})
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "travel-app-geocoder/1.0"})
            r = json.load(urllib.request.urlopen(req, timeout=25))
            feats = r.get("features", [])
            if feats:
                lon, lat = feats[0]["geometry"]["coordinates"]
                return round(lat, 6), round(lon, 6)
            return None  # 查到了但无结果，不重试
        except Exception as e:
            print(f"    retry {i}: {e}", flush=True)
            time.sleep(3)
    return None


def main(country):
    qfile = QUERIES_DIR / f"queries_{country}.json"
    if not qfile.exists():
        sys.exit(f"找不到 {qfile}")
    queries = json.load(open(qfile, encoding="utf-8"))

    GEO_DIR.mkdir(parents=True, exist_ok=True)
    out_file = GEO_DIR / f"{country}_coords.json"
    coords = json.load(open(out_file, encoding="utf-8")) if out_file.exists() else {}

    todo = [item for item in queries if item["attraction"] not in coords]
    print(f"{country}: 查询表 {len(queries)} 个，已有坐标 {len(coords)} 个，待查 {len(todo)} 个", flush=True)

    for n, item in enumerate(todo, 1):
        attr, q = item["attraction"], item["query"]
        g = photon(q)
        if g:
            coords[attr] = {"lat": g[0], "lon": g[1], "query": q, "city": item.get("city", "")}
            print(f"  [{n}/{len(todo)}] {attr} ({item.get('city','')}) -> {g[0]},{g[1]}", flush=True)
        else:
            print(f"  [{n}/{len(todo)}] {attr} -> 查不到，跳过", flush=True)
        # 每查 5 个存一次盘，避免中断丢进度
        if n % 5 == 0:
            json.dump(coords, open(out_file, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        time.sleep(1.2)  # 礼貌限速

    json.dump(coords, open(out_file, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"完成: {len(coords)} 个坐标 -> {out_file}", flush=True)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "法国")

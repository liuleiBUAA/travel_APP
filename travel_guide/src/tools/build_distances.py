#!/usr/bin/env python3
"""预计算每条行程相邻景点的步行距离，存盘供后端直接读（不让用户实时等 OSRM）。

输入: data/geo/<国家>_coords.json + data/<区域>/guides/<国家>_destinations.json
输出: data/geo/<国家>_distances.json
  { "卢浮宫|香榭丽舍大街": {"km":3.5,"min":42}, ... }
按"景点对"存（无序，键名两景点排序后用|连接），后端按当天 activity 里
相邻景点实时查表 —— 不依赖 day 编号（规划器会插入到达/离开日，编号会偏移）。

时间按 5km/h 步速算（OSRM 公共服务的 duration 不可信，按骑车速度返回）。
线性/区域地点（河流、大街、海滩等）点对点距离无意义，跳过。
"""
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GEO_DIR = ROOT / "data" / "geo"
GUIDES = list((ROOT / "data").glob("*/guides"))

# 线性/区域地点：点对点距离无意义，不纳入距离条
SKIP_SUFFIX = ("河", "大街", "海滩", "海岸", "湖", "山区", "森林", "沙丘")
SKIP_KEYWORD = ("漫步", "之旅", "美食", "日落", "日出", "返回", "城堡游")


def is_skippable(name):
    if any(k in name for k in SKIP_KEYWORD):
        return True
    if name.endswith(SKIP_SUFFIX):
        return True
    return False


def osrm_km(a, b, tries=2):
    url = f"https://router.project-osrm.org/route/v1/foot/{a['lon']},{a['lat']};{b['lon']},{b['lat']}?overview=false"
    for _ in range(tries):
        try:
            r = json.load(urllib.request.urlopen(
                urllib.request.Request(url, headers={"User-Agent": "travel-app/1.0"}), timeout=20))
            if r.get("code") == "Ok":
                return r["routes"][0]["distance"] / 1000
        except Exception:
            time.sleep(2)
    return None


def find_dest_file(country):
    for g in GUIDES:
        f = g / f"{country}_destinations.json"
        if f.exists():
            return f
    return None


def main(country):
    coords = json.load(open(GEO_DIR / f"{country}_coords.json", encoding="utf-8"))
    dest = json.load(open(find_dest_file(country), encoding="utf-8"))

    out = {}
    for city, info in dest.items():
        for day in info.get("itinerary", []):
            attrs = [a.strip() for a in re.split(r"[、,，]", day["activity"]) if a.strip()]
            # 去重保序 + 必须有坐标 + 非线性/区域地点
            seen, usable = set(), []
            for a in attrs:
                if a in coords and not is_skippable(a) and a not in seen:
                    seen.add(a)
                    usable.append(a)
            for i in range(len(usable) - 1):
                a, b = usable[i], usable[i + 1]
                key = "|".join(sorted([a, b]))
                if key in out:
                    continue
                km = osrm_km(coords[a], coords[b])
                if km is not None:
                    out[key] = {"km": round(km, 1), "min": round(km / 5 * 60)}
                time.sleep(0.5)
    print(f"  共 {len(out)} 个景点对", flush=True)

    out_file = GEO_DIR / f"{country}_distances.json"
    json.dump(out, open(out_file, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"完成 -> {out_file}", flush=True)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "法国")

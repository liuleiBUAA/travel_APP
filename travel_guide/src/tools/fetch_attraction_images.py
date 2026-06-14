"""为景点清单批量抓图（Wikimedia）。

用法:
    python3 fetch_attraction_images.py <attractions.json> <输出目录> [bbox]

    bbox: 可选地理围栏 "lat_min,lat_max,lon_min,lon_max"（如法国 "41,51.5,-5.6,9.8"），
          词条带坐标但落在围栏外的直接判为配错，丢弃。

策略: 中文维基精确查词条（信任重定向）→ 全文搜索（景点+城市，严格校验标题）
      → 取词条主图。都没有则留空——配错比留空伤害大。

每张图记录许可证和作者（extmetadata），写入 <输出目录>/manifest.json。
"""
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

import warnings
warnings.filterwarnings("ignore")  # zhconv 的 pkg_resources 弃用警告
from zhconv import convert as zh_convert

UA = {"User-Agent": "TravelGuideBot/1.0 (attraction image fetcher; contact: admin@awesometravelpartner.cn)"}
DELAY = 1.5  # 礼貌限速

# 重点景点补图：景点名 → 额外的 Commons 搜索词（英文命中率高）。
# 每个查询词下载一张，文件名接在主图后面（_2、_3…）。
EXTRA_QUERIES = {
    "凡尔赛宫": ["Hall of Mirrors Versailles", "Palace of Versailles gardens"],
}

# 行程里的叫法 → 维基词条名。自动匹配不上时人工补这张表（跑完看 manifest 里的 miss）。
# 跨国重名/泛称用 "城市/景点" 限定（如老桥在海德堡和佛罗伦萨都有）。
ALIASES = {
    "教皇宫": "亚维农教皇宫",
    "断桥": "圣贝内泽桥",
    "泉水城": "沃克吕兹泉",
    "石头城": "戈尔德",
    "红土城": "鲁西永 (沃克吕兹省)",
    "瓦伦索勒薰衣草": "瓦朗索勒",
    "守护圣母教堂": "山上圣母堂 (马赛)",
    "卡朗格峡湾": "卡朗克山",
    "象鼻山悬崖": "埃特勒塔",
    "安纳西湖": "阿讷西湖",
    "昂布瓦兹": "昂布瓦斯",
    "圣马洛古城墙": "圣马洛",
    "小威尼斯": "科尔马",
    # 意大利
    "许愿池": "特雷维喷泉",
    "佛罗伦萨/老桥": "老桥",
    "总督宫": "威尼斯总督府",
    "彩色岛": "布拉诺岛",
    "阿马尔菲镇": "阿马尔菲",
    "休斯山": "赛瑟阿尔姆",
    "彩色村庄徒步": "五渔村",
    "托斯卡纳/田园风光": "奥尔恰谷",
}

# 词条没有或主图不行（玻璃岛词条主图是地图）→ 直接用确认过的 Commons 搜索词取图。
COMMONS_QUERIES = {
    "玻璃岛": "Grand Canal of Murano Venice",
    "刀锋山": "The Dolomites from Seceda",
    "富纳斯山谷": "Val di Funes Dolomites",
    # 澳洲悉尼补图
    "QVB": "Queen Victoria Building Sydney interior",
    "达令港": "Darling Harbour Sydney",
    "悉尼鱼市场": "Sydney Fish Market",
    "悉尼皇家植物园": "Royal Botanic Garden Sydney",
    "悉尼塔": "Sydney Tower",
    "新南威尔士美术馆": "Art Gallery of New South Wales",
    "悉尼大学": "University of Sydney quadrangle",
    "曼利海滩": "Manly Beach Australia",
    # 瑞士补图
    "花钟": "Horloge fleurie Geneva",
    "万国宫": "Palace of Nations Geneva",
    "断腿椅子": "Broken Chair Geneva",
    "冰川天堂线": "Matterhorn Glacier Paradise",
    "苏内加线": "Sunnegga Zermatt Matterhorn",
    "ETH观景台": "ETH Zurich Polyterrasse view",
    "苏黎世美术馆": "Kunsthaus Zurich",
    "瑞士国家博物馆": "Landesmuseum Zurich",
    "班霍夫大街": "Bahnhofstrasse Zurich",
    "玉特利山": "Uetliberg Zurich view",
    "瑞士交通博物馆": "Swiss Museum of Transport Lucerne",
    "石丹峰": "Stanserhorn summit panorama",
    "铁力士山": "Mount Titlis",
    "沃韦小镇": "Vevey Lake Geneva",
    "拉沃葡萄园": "Lavaux vineyard terraces",
    "蒙特勒市区": "Montreux waterfront Lake Geneva",
    # 其他
    "塞切尼温泉": "Szechenyi Thermal Bath Budapest",
    "最后的晚餐": "Santa Maria delle Grazie Milan",
    "苏格兰高地": "Scottish Highlands Glencoe",
    "天空岛": "Isle of Skye Old Man of Storr",
    "羊角村": "Giethoorn",
    "杜布罗夫尼克": "Dubrovnik old town city walls",
    "五渔村": "Vernazza Cinque Terre",
    "圣诞老人村": "Santa Claus Village Rovaniemi",
}


def _open_with_retry(url, timeout):
    """429 时按 15/45/90 秒退避重试。"""
    for i, wait in enumerate([15, 45, 90, None]):
        try:
            req = urllib.request.Request(url, headers=UA)
            return urllib.request.urlopen(req, timeout=timeout)
        except urllib.error.HTTPError as e:
            if e.code != 429 or wait is None:
                raise
            print(f"(429,等{wait}s)", end="", flush=True)
            time.sleep(wait)


def api(url):
    with _open_with_retry(url, timeout=30) as r:
        return json.loads(r.read())


PROPS = "&prop=pageimages|langlinks|coordinates&piprop=name&lllang=en&colimit=1"


def _parse_page(page):
    """返回 {title, image, en, coords}，image 为主图文件名（SVG 视为无图）。"""
    image = page.get("pageimage")
    # SVG 主图基本都是 logo/地图，不是景点照片
    if image and image.lower().endswith(".svg"):
        image = None
    en = None
    for ll in page.get("langlinks", []):
        if ll.get("lang") == "en":
            en = ll.get("*")
    coords = None
    for c in page.get("coordinates", []):
        coords = (c["lat"], c["lon"])
    return {"title": page.get("title"), "image": image, "en": en, "coords": coords}


def zh_wiki_exact(title):
    """精确标题查词条（带重定向+繁简转换）。返回 page dict 或 None。"""
    q = urllib.parse.quote(title)
    data = api(f"https://zh.wikipedia.org/w/api.php?action=query&format=json"
               f"&titles={q}&redirects=1&converttitles=1{PROPS}")
    pages = data.get("query", {}).get("pages", {})
    for pid, page in pages.items():
        if int(pid) > 0 and "missing" not in page:
            return _parse_page(page)
    return None


def zh_wiki_lookup(query):
    """中文维基全文搜索，返回 page dict 或 None。"""
    q = urllib.parse.quote(query)
    data = api(f"https://zh.wikipedia.org/w/api.php?action=query&format=json"
               f"&generator=search&gsrsearch={q}&gsrlimit=1{PROPS}")
    pages = data.get("query", {}).get("pages", {})
    if not pages:
        return None
    return _parse_page(next(iter(pages.values())))


def commons_search(query):
    """Commons 全文搜图，返回文件名（带 File: 前缀去掉）或 None。只要位图。"""
    q = urllib.parse.quote(query)
    data = api(f"https://commons.wikimedia.org/w/api.php?action=query&format=json"
               f"&list=search&srsearch={q}%20filetype:bitmap&srnamespace=6&srlimit=5")
    for hit in data.get("query", {}).get("search", []):
        title = hit["title"]
        if title.lower().endswith((".jpg", ".jpeg", ".png")):
            return title.replace("File:", "")
    return None


def commons_imageinfo(filename):
    """取图片下载 URL + 许可证 + 作者。返回 dict 或 None。"""
    q = urllib.parse.quote("File:" + filename)
    data = api(f"https://commons.wikimedia.org/w/api.php?action=query&format=json"
               f"&titles={q}&prop=imageinfo"
               f"&iiprop=url|extmetadata&iiurlwidth=1024")
    pages = data.get("query", {}).get("pages", {})
    for page in pages.values():
        for info in page.get("imageinfo", []):
            meta = info.get("extmetadata", {})
            def field(k):
                v = meta.get(k, {}).get("value", "")
                return re.sub(r"<[^>]+>", "", str(v)).strip()
            return {
                "url": info.get("thumburl") or info.get("url"),
                "license": field("LicenseShortName"),
                "artist": field("Artist")[:80],
                "file": filename,
            }
    return None


def download(url, path):
    with _open_with_retry(url, timeout=60) as r, open(path, "wb") as f:
        f.write(r.read())


def safe_name(s):
    return re.sub(r'[\\/:*?"<>|（）()]', "_", s)


def title_matches(attraction, title):
    """词条标题（可能是繁体/别名）是否和景点名对得上：繁简归一后互相包含。"""
    if not title:
        return False
    t = zh_convert(re.sub(r"[（(].*?[)）]", "", title).strip(), "zh-cn")
    a = zh_convert(attraction, "zh-cn")
    return a in t or t in a


def in_bbox(page, bbox):
    if not (bbox and page["coords"]):
        return None  # 无法判断
    lat, lon = page["coords"]
    lat_min, lat_max, lon_min, lon_max = bbox
    return lat_min <= lat <= lat_max and lon_min <= lon <= lon_max


def page_trusted(attraction, page, bbox, trusted_redirect):
    """词条是否可信。地理校验优先：有坐标必须落在 bbox 内；
    精确查询（维基自己的重定向，如"安纳西"→"阿讷西"）坐标对了就信，
    全文搜索结果还要求标题和景点名对得上（防"断桥"搜出不相干词条）。"""
    if page is None:
        return False
    geo = in_bbox(page, bbox)
    if geo is False:
        return False
    if geo is True and trusted_redirect:
        return True
    return title_matches(attraction, page["title"])


def fetch_one(city, attraction, bbox=None):
    """返回 manifest 条目 dict（含 source 说明命中方式）或 None。配错比留空伤害大。"""
    # 人工确认过的 Commons 搜索词直取（词条无图或主图是地图时用）
    cq = COMMONS_QUERIES.get(f"{city}/{attraction}") or COMMONS_QUERIES.get(attraction)
    if cq:
        f = commons_search(cq)
        time.sleep(DELAY)
        info = commons_imageinfo(f) if f else None
        if info:
            info["source"] = f"commons-search:{cq}"
            return info
        return None
    # 人工别名直查，不做标题校验（别名本身就是确认过的词条名）
    alias = ALIASES.get(f"{city}/{attraction}") or ALIASES.get(attraction)
    if alias:
        page = zh_wiki_exact(alias)
        time.sleep(DELAY)
        if page and in_bbox(page, bbox) is not False and page["image"]:
            info = commons_imageinfo(page["image"])
            if info:
                info["source"] = f"zhwiki-alias:{page['title']}"
                return info
        return None
    # 候选词条：先精确标题查询（重定向可信；两字泛称跳过，"断桥"会撞到杭州西湖断桥），
    # 再按上下文全文搜索——城市主名 + 括号里的每个地名，
    # 如 "普罗旺斯（阿维尼翁/马赛）" → ["普罗旺斯", "阿维尼翁", "马赛"]
    page = None
    if len(attraction) >= 3:
        cand = zh_wiki_exact(attraction)
        time.sleep(DELAY)
        if page_trusted(attraction, cand, bbox, trusted_redirect=True):
            page = cand
    if page is None or not page["image"]:
        contexts = [re.sub(r"[（(].*?[)）]", "", city).strip()]
        for paren in re.findall(r"[（(](.*?)[)）]", city):
            contexts += [p.strip() for p in paren.split("/") if p.strip()]
        for ctx in contexts:
            cand = zh_wiki_lookup(f"{attraction} {ctx}")
            time.sleep(DELAY)
            if page_trusted(attraction, cand, bbox, trusted_redirect=False):
                if cand["image"] or page is None:
                    page = cand
                if page["image"]:
                    break
    if page and page["image"]:
        info = commons_imageinfo(page["image"])
        if info:
            info["source"] = f"zhwiki:{page['title']}"
            return info
    # 可信词条但无主图（或主图是 SVG）：用英文名搜 Commons 兜底
    if page and page["en"]:
        time.sleep(DELAY)
        f = commons_search(page["en"])
        if f:
            info = commons_imageinfo(f)
            if info:
                info["source"] = f"commons-search:{page['en']}"
                return info
    return None


def fetch_extras(attraction, city_dir, out_dir, start_idx=2):
    """按 EXTRA_QUERIES 给重点景点补图，返回 manifest extras 列表。"""
    extras = []
    for n, query in enumerate(EXTRA_QUERIES.get(attraction, [])):
        print(f"  补图 [{query}] ... ", end="", flush=True)
        try:
            f = commons_search(query)
            time.sleep(DELAY)
            info = commons_imageinfo(f) if f else None
            if not info:
                print("未命中")
                continue
            ext = os.path.splitext(info["file"])[1] or ".jpg"
            local = os.path.join(city_dir, safe_name(attraction) + f"_{start_idx + n}" + ext.lower())
            download(info["url"], local)
            print(f"OK ({info['license']})")
            extras.append({"local": os.path.relpath(local, out_dir),
                           "license": info["license"], "artist": info["artist"],
                           "commons_file": info["file"], "source": f"commons-search:{query}"})
        except Exception as e:
            print(f"ERROR {e}")
        time.sleep(DELAY)
    return extras


def main(attractions_path, out_dir, bbox=None):
    rows = json.load(open(attractions_path, encoding="utf-8"))
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
        city, attraction = row["city"], row["attraction"]
        if (city, attraction) in done:
            entry = done[(city, attraction)]
            # 已有主图但 EXTRA_QUERIES 新加了补图查询：只补缺的部分
            if EXTRA_QUERIES.get(attraction) and not entry.get("extras"):
                print(f"[{i+1}/{len(rows)}] {city} / {attraction} 主图已有，补图:")
                city_dir = os.path.join(out_dir, safe_name(city))
                entry = {**entry, "extras": fetch_extras(attraction, city_dir, out_dir)}
            manifest.append(entry)
            hit += 1
            continue
        print(f"[{i+1}/{len(rows)}] {city} / {attraction} ... ", end="", flush=True)
        try:
            info = fetch_one(city, attraction, bbox)
        except Exception as e:
            print(f"ERROR {e}")
            manifest.append({**row, "status": "error", "error": str(e)})
            time.sleep(DELAY)
            continue
        if not info:
            print("未命中")
            manifest.append({**row, "status": "miss"})
            time.sleep(DELAY)
            continue
        city_dir = os.path.join(out_dir, safe_name(city))
        os.makedirs(city_dir, exist_ok=True)
        ext = os.path.splitext(info["file"])[1] or ".jpg"
        local = os.path.join(city_dir, safe_name(attraction) + "_1" + ext.lower())
        try:
            download(info["url"], local)
        except Exception as e:
            print(f"下载失败 {e}")
            manifest.append({**row, "status": "error", "error": str(e)})
            time.sleep(DELAY)
            continue
        hit += 1
        print(f"OK ({info['source']}, {info['license']})")
        entry = {**row, "status": "ok", "local": os.path.relpath(local, out_dir),
                 "license": info["license"], "artist": info["artist"],
                 "commons_file": info["file"], "source": info["source"]}
        if EXTRA_QUERIES.get(attraction):
            entry["extras"] = fetch_extras(attraction, city_dir, out_dir)
        manifest.append(entry)
        time.sleep(DELAY)

    os.makedirs(out_dir, exist_ok=True)
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1)
    print(f"\n命中 {hit}/{len(rows)}，manifest 写入 {manifest_path}")


if __name__ == "__main__":
    bbox = tuple(float(x) for x in sys.argv[3].split(",")) if len(sys.argv) > 3 else None
    main(sys.argv[1], sys.argv[2], bbox)

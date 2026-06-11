"""为景点清单批量抓图（Wikimedia）。

用法:
    python3 fetch_attraction_images.py <attractions.json> <输出目录>

策略（按命中质量排序）:
1. 中文维基百科搜词条 → 取词条主图（匹配度最高）
2. 词条无主图时，用词条的英文名搜 Wikimedia Commons
3. 都没有则留空

每张图记录许可证和作者（extmetadata），写入 <输出目录>/manifest.json。
"""
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

UA = {"User-Agent": "TravelGuideBot/1.0 (attraction image fetcher; contact: admin@awesometravelpartner.cn)"}
DELAY = 0.5  # 礼貌限速


def api(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def zh_wiki_lookup(query):
    """中文维基搜索，返回 (页面标题, 主图文件名, 英文标题) 任意项可为 None。"""
    q = urllib.parse.quote(query)
    data = api(f"https://zh.wikipedia.org/w/api.php?action=query&format=json"
               f"&generator=search&gsrsearch={q}&gsrlimit=1"
               f"&prop=pageimages|langlinks&piprop=name&lllang=en")
    pages = data.get("query", {}).get("pages", {})
    if not pages:
        return None, None, None
    page = next(iter(pages.values()))
    title = page.get("title")
    image = page.get("pageimage")  # 文件名，不带 File: 前缀
    en = None
    for ll in page.get("langlinks", []):
        if ll.get("lang") == "en":
            en = ll.get("*")
    return title, image, en


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
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as r, open(path, "wb") as f:
        f.write(r.read())


def safe_name(s):
    return re.sub(r'[\\/:*?"<>|（）()]', "_", s)


def fetch_one(city, attraction):
    """返回 manifest 条目 dict（含 source 说明命中方式）或 None。"""
    # 城市名去掉括号注释做搜索上下文，如 "蔚蓝海岸（尼斯/摩纳哥/戛纳）" → "蔚蓝海岸"
    city_ctx = re.sub(r"[（(].*?[)）]", "", city)
    title, image, en = zh_wiki_lookup(f"{attraction} {city_ctx}")
    if not image:
        time.sleep(DELAY)
        title, image, en = zh_wiki_lookup(attraction)
    if image:
        info = commons_imageinfo(image)
        if info:
            info["source"] = f"zhwiki:{title}"
            return info
    if en:
        time.sleep(DELAY)
        f = commons_search(en)
        if f:
            info = commons_imageinfo(f)
            if info:
                info["source"] = f"commons-search:{en}"
                return info
    return None


def main(attractions_path, out_dir):
    rows = json.load(open(attractions_path, encoding="utf-8"))
    manifest = []
    hit = 0
    for i, row in enumerate(rows):
        city, attraction = row["city"], row["attraction"]
        print(f"[{i+1}/{len(rows)}] {city} / {attraction} ... ", end="", flush=True)
        try:
            info = fetch_one(city, attraction)
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
        manifest.append({**row, "status": "ok", "local": os.path.relpath(local, out_dir),
                         "license": info["license"], "artist": info["artist"],
                         "commons_file": info["file"], "source": info["source"]})
        time.sleep(DELAY)

    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1)
    print(f"\n命中 {hit}/{len(rows)}，manifest 写入 {out_dir}/manifest.json")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])

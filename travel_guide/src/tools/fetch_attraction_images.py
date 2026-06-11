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
import urllib.error
import urllib.parse
import urllib.request

import warnings
warnings.filterwarnings("ignore")  # zhconv 的 pkg_resources 弃用警告
from zhconv import convert as zh_convert

UA = {"User-Agent": "TravelGuideBot/1.0 (attraction image fetcher; contact: admin@awesometravelpartner.cn)"}
DELAY = 1.5  # 礼貌限速


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


def _parse_page(page):
    title = page.get("title")
    image = page.get("pageimage")  # 文件名，不带 File: 前缀
    # SVG 主图基本都是 logo/地图，不是景点照片
    if image and image.lower().endswith(".svg"):
        image = None
    en = None
    for ll in page.get("langlinks", []):
        if ll.get("lang") == "en":
            en = ll.get("*")
    return title, image, en


def zh_wiki_exact(title):
    """精确标题查词条（带重定向+繁简转换）。返回 (标题, 主图, 英文名)。"""
    q = urllib.parse.quote(title)
    data = api(f"https://zh.wikipedia.org/w/api.php?action=query&format=json"
               f"&titles={q}&redirects=1&converttitles=1"
               f"&prop=pageimages|langlinks&piprop=name&lllang=en")
    pages = data.get("query", {}).get("pages", {})
    for pid, page in pages.items():
        if int(pid) > 0 and "missing" not in page:
            return _parse_page(page)
    return None, None, None


def zh_wiki_lookup(query):
    """中文维基全文搜索，返回 (页面标题, 主图文件名, 英文标题)。"""
    q = urllib.parse.quote(query)
    data = api(f"https://zh.wikipedia.org/w/api.php?action=query&format=json"
               f"&generator=search&gsrsearch={q}&gsrlimit=1"
               f"&prop=pageimages|langlinks&piprop=name&lllang=en")
    pages = data.get("query", {}).get("pages", {})
    if not pages:
        return None, None, None
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


def fetch_one(city, attraction):
    """返回 manifest 条目 dict（含 source 说明命中方式）或 None。

    先用 "景点+城市" 全文搜索并严格校验标题——城市上下文能消歧
    （"教皇宫"直接精确查会被重定向到梵蒂冈宗座宫，带上"普罗旺斯"才搜到阿维尼翁教皇宫）；
    搜索跑题时（"安纳西"搜出"安纳托利亚"）校验会拦下。
    无果再做精确标题查询，信任维基自己的重定向/繁简转换（"霞慕尼"→"沙莫尼蒙勃朗"）。
    最后回退 Commons 英文搜索。配错比留空伤害大。
    """
    # 搜索上下文：城市主名 + 括号里的每个地名，如 "普罗旺斯（阿维尼翁/马赛）"
    # → ["普罗旺斯", "阿维尼翁", "马赛"]。括号里的往往才是真正的消歧词。
    contexts = [re.sub(r"[（(].*?[)）]", "", city).strip()]
    for paren in re.findall(r"[（(](.*?)[)）]", city):
        contexts += [p.strip() for p in paren.split("/") if p.strip()]
    title = image = en = None
    for ctx in contexts:
        title, image, en = zh_wiki_lookup(f"{attraction} {ctx}")
        if title_matches(attraction, title) and image:
            break
        image = en = None
        time.sleep(DELAY)
    # 精确查询的重定向也会跑题（"教皇宫"被重定向到梵蒂冈宗座宫），同样要校验；
    # 两字泛称连查都不查（"断桥"会撞到杭州西湖断桥）
    if not image and len(attraction) >= 3:
        title, image, en = zh_wiki_exact(attraction)
        if not title_matches(attraction, title):
            image = en = None
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
            manifest.append(done[(city, attraction)])
            hit += 1
            continue
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
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1)
    print(f"\n命中 {hit}/{len(rows)}，manifest 写入 {manifest_path}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])

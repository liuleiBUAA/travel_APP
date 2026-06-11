"""为已有景点补充额外图片（每个景点补到3-4张）。

用法:
    python3 supplement_images.py [区域名]

    不传参数则处理所有区域。传区域名（如"法国"）则只处理该区域。

策略:
    对每个已有1张主图的景点，用英文名/中文名在 Wikimedia Commons 搜索额外图片。
    每个景点补2-3张（总共3-4张），跳过已有多张图的。
    下载后更新 manifest.json 的 extras 字段。
"""
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

UA = {"User-Agent": "TravelGuideBot/1.0 (supplement images; contact: admin@awesometravelpartner.cn)"}
DELAY = 1.5  # 礼貌限速
TARGET_TOTAL = 4  # 每个景点目标图片数

IMAGES_DIR = os.path.dirname(os.path.abspath(__file__))
IMAGES_DIR = os.path.join(os.path.dirname(os.path.dirname(IMAGES_DIR)), "data", "images")


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


def commons_search_multi(query, existing_files, limit=5):
    """在 Commons 搜索多张图片，排除已有的。返回文件名列表。"""
    q = urllib.parse.quote(query)
    data = api(f"https://commons.wikimedia.org/w/api.php?action=query&format=json"
               f"&list=search&srsearch={q}%20filetype:bitmap&srnamespace=6&srlimit={limit}")
    results = []
    for hit in data.get("query", {}).get("search", []):
        title = hit["title"]
        fname = title.replace("File:", "")
        if fname.lower().endswith((".jpg", ".jpeg", ".png")):
            if fname not in existing_files:
                results.append(fname)
    return results


def commons_imageinfo(filename):
    """取图片下载 URL + 许可证 + 作者。"""
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


def get_search_queries(attraction, city, country):
    """生成多个搜索词，提高命中率。"""
    queries = []
    # 英文搜索（通常命中率更高）
    # 先尝试 attraction + city 的英文组合
    queries.append(f"{attraction} {city}")
    queries.append(f"{attraction} {country}")
    # 只用景点名
    queries.append(attraction)
    return queries


def get_english_name(attraction):
    """尝试从中文维基获取英文名。"""
    q = urllib.parse.quote(attraction)
    try:
        data = api(f"https://zh.wikipedia.org/w/api.php?action=query&format=json"
                   f"&titles={q}&redirects=1&converttitles=1"
                   f"&prop=langlinks&lllang=en")
        pages = data.get("query", {}).get("pages", {})
        for pid, page in pages.items():
            if int(pid) > 0:
                for ll in page.get("langlinks", []):
                    if ll.get("lang") == "en":
                        return ll.get("*")
    except Exception:
        pass
    return None


def supplement_region(region_dir):
    """给一个区域的所有景点补图。"""
    manifest_path = os.path.join(region_dir, "manifest.json")
    if not os.path.exists(manifest_path):
        print(f"⚠️  {region_dir} 没有 manifest.json，跳过")
        return

    manifest = json.load(open(manifest_path, encoding="utf-8"))
    region_name = os.path.basename(region_dir)
    
    updated = 0
    skipped = 0
    
    for i, entry in enumerate(manifest):
        if entry.get("status") != "ok":
            continue
        
        existing_extras = entry.get("extras", [])
        current_count = 1 + len(existing_extras)
        
        if current_count >= TARGET_TOTAL:
            skipped += 1
            continue
        
        need = TARGET_TOTAL - current_count
        attraction = entry["attraction"]
        city = entry.get("city", "")
        
        print(f"[{region_name}] {attraction} (现有{current_count}张，补{need}张) ... ", end="", flush=True)
        
        # 收集已有的 commons 文件名，避免重复
        existing_files = set()
        if entry.get("commons_file"):
            existing_files.add(entry["commons_file"])
        for ext in existing_extras:
            if ext.get("commons_file"):
                existing_files.add(ext["commons_file"])
        
        # 获取英文名用于搜索
        en_name = get_english_name(attraction)
        time.sleep(DELAY)
        
        # 构建搜索词列表
        search_queries = []
        if en_name:
            search_queries.append(en_name)
            search_queries.append(f"{en_name} landmark")
        search_queries.append(f"{attraction} {city}")
        search_queries.append(attraction)
        
        # 搜索并下载
        new_extras = []
        city_dir = os.path.join(region_dir, safe_name(entry.get("city", attraction)))
        os.makedirs(city_dir, exist_ok=True)
        
        for query in search_queries:
            if len(new_extras) >= need:
                break
            try:
                candidates = commons_search_multi(query, existing_files, limit=8)
                time.sleep(DELAY)
            except Exception as e:
                print(f"搜索失败({e}) ", end="", flush=True)
                time.sleep(DELAY)
                continue
            
            for fname in candidates:
                if len(new_extras) >= need:
                    break
                if fname in existing_files:
                    continue
                try:
                    info = commons_imageinfo(fname)
                    time.sleep(DELAY)
                    if not info or not info.get("url"):
                        continue
                    
                    idx = current_count + len(new_extras) + 1
                    ext = os.path.splitext(fname)[1] or ".jpg"
                    local_path = os.path.join(city_dir, f"{safe_name(attraction)}_{idx}{ext.lower()}")
                    download(info["url"], local_path)
                    
                    existing_files.add(fname)
                    new_extras.append({
                        "local": os.path.relpath(local_path, region_dir),
                        "license": info["license"],
                        "artist": info["artist"],
                        "commons_file": fname,
                        "source": f"commons-supplement:{query}",
                    })
                    print(f"✓", end="", flush=True)
                    time.sleep(DELAY)
                except Exception as e:
                    print(f"✗", end="", flush=True)
                    time.sleep(DELAY)
                    continue
        
        if new_extras:
            if "extras" not in entry:
                entry["extras"] = []
            entry["extras"].extend(new_extras)
            updated += 1
            print(f" +{len(new_extras)}张")
        else:
            print(" 未找到额外图片")
        
        # 每处理完一个景点就保存（断点续跑）
        if new_extras:
            with open(manifest_path, "w", encoding="utf-8") as f:
                json.dump(manifest, f, ensure_ascii=False, indent=1)
    
    print(f"\n{'='*40}")
    print(f"[{region_name}] 完成: 补图{updated}个景点，跳过{skipped}个已够数")
    print(f"{'='*40}\n")


def main():
    target_region = sys.argv[1] if len(sys.argv) > 1 else None
    
    if target_region:
        region_path = os.path.join(IMAGES_DIR, target_region)
        if not os.path.isdir(region_path):
            print(f"❌ 区域目录不存在: {region_path}")
            sys.exit(1)
        supplement_region(region_path)
    else:
        # 处理所有区域
        for name in sorted(os.listdir(IMAGES_DIR)):
            region_path = os.path.join(IMAGES_DIR, name)
            if os.path.isdir(region_path) and os.path.exists(os.path.join(region_path, "manifest.json")):
                supplement_region(region_path)


if __name__ == "__main__":
    main()

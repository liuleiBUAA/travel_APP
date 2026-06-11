"""景点图片匹配：行程生成时按 activity 文本挂图。

图片来自 travel_guide/data/images/<国家>/manifest.json（Wikimedia 抓图，含许可证）。
启动时把所有 manifest 读进内存，生成行程时对每天的 activity 字符串做子串匹配。
"""

import json
from pathlib import Path
from typing import Dict, List

IMAGES_DIR = Path(__file__).parent.parent.parent / "travel_guide" / "data" / "images"
# 挂在 /api/ 下复用 nginx 的代理；返回相对路径，前端拼上域名
URL_PREFIX = "/api/static/attractions"


class ImageIndex:
    def __init__(self):
        # [(景点名, {name, url, credit}), ...] 长景点名在前，避免"圣马洛"抢了"圣马洛古城墙"
        self._entries: List[tuple] = []
        if not IMAGES_DIR.exists():
            print("⚠️  [ImageIndex] 图片目录不存在，行程不挂图")
            return
        for manifest_path in IMAGES_DIR.glob("*/manifest.json"):
            country = manifest_path.parent.name
            for m in json.load(open(manifest_path, encoding="utf-8")):
                if m.get("status") != "ok":
                    continue
                pics = [m] + m.get("extras", [])
                for p in pics:
                    self._entries.append((m["attraction"], {
                        "name": m["attraction"],
                        "url": f"{URL_PREFIX}/{country}/{p['local']}",
                        "credit": f"{p.get('license', '')} {p.get('artist', '')}".strip(),
                        # 同一张源图可能因别名存了两份（圣马洛/圣马洛古城墙），匹配时按它去重
                        "_src": p.get("commons_file", p["local"]),
                    }))
        self._entries.sort(key=lambda e: -len(e[0]))
        print(f"✅ [ImageIndex] 已加载 {len(self._entries)} 张景点图片")

    def match(self, activity: str, limit: int = 3, seen: set = None) -> List[Dict]:
        """返回 activity 文本中出现的景点的图片，最多 limit 张。

        seen: 调用方传入并跨多次调用复用时，可实现跨天去重（同一张图整个行程只出现一次）。
        """
        if not activity:
            return []
        if seen is None:
            seen = set()
        result = []
        for attraction, pic in self._entries:
            if attraction in activity and pic["_src"] not in seen:
                seen.add(pic["_src"])
                result.append({k: v for k, v in pic.items() if k != "_src"})
                if len(result) >= limit:
                    break
        return result


_index = None


def get_image_index() -> ImageIndex:
    global _index
    if _index is None:
        _index = ImageIndex()
    return _index

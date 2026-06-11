"""景点玩法 + 城市攻略：行程生成时挂入口，详情页按名称取全文。

内容存 travel_guide/data/playbooks/<国家>/<名称>.json，
结构: {name, aliases, city, country, summary, sections[{title,content}], duration, best_time}
带 "type": "city" 的是城市攻略——不参与 activity 文本匹配（城市名出现在交通段会误挂），
由 route_service 按每天的 stay 字段挂到该城市的第一天。
"""

import json
from pathlib import Path
from typing import Dict, List, Optional

PLAYBOOKS_DIR = Path(__file__).parent.parent.parent / "travel_guide" / "data" / "playbooks"


class PlaybookIndex:
    def __init__(self):
        # 别名（含本名）→ 玩法全文；匹配用 [(别名, 本名), ...] 长名在前
        self._by_name: Dict[str, Dict] = {}
        self._entries: List[tuple] = []
        self._city_alias: Dict[str, str] = {}  # 城市攻略：别名/本名 → 本名
        if not PLAYBOOKS_DIR.exists():
            print("⚠️  [PlaybookIndex] 玩法目录不存在")
            return
        for path in PLAYBOOKS_DIR.glob("*/*.json"):
            try:
                data = json.load(open(path, encoding="utf-8"))
            except Exception as e:
                print(f"⚠️  [PlaybookIndex] 读取失败 {path}: {e}")
                continue
            name = data.get("name")
            if not name:
                continue
            self._by_name[name] = data
            if data.get("type") == "city":
                for alias in [name] + data.get("aliases", []):
                    self._city_alias[alias] = name
            else:
                for alias in [name] + data.get("aliases", []):
                    self._entries.append((alias, name))
        self._entries.sort(key=lambda e: -len(e[0]))
        n_city = len(set(self._city_alias.values()))
        print(f"✅ [PlaybookIndex] 已加载 {len(self._by_name) - n_city} 篇景点玩法 + {n_city} 篇城市攻略")

    def get(self, name: str) -> Optional[Dict]:
        """按本名或别名取玩法全文"""
        if name in self._by_name:
            return self._by_name[name]
        if name in self._city_alias:
            return self._by_name[self._city_alias[name]]
        for alias, real_name in self._entries:
            if alias == name:
                return self._by_name[real_name]
        return None

    def get_city(self, stay: str) -> Optional[Dict]:
        """按行程 stay 字段（城市名）取城市攻略，别名也认"""
        name = self._city_alias.get(stay)
        return self._by_name.get(name) if name else None

    def match(self, activity: str) -> List[Dict]:
        """返回 activity 文本中出现的景点的玩法入口（轻量，只带名字和一句话）"""
        if not activity:
            return []
        result, seen = [], set()
        for alias, real_name in self._entries:
            if alias in activity and real_name not in seen:
                seen.add(real_name)
                pb = self._by_name[real_name]
                result.append({"name": real_name, "summary": pb.get("summary", "")})
        return result


_index = None


def get_playbook_index() -> PlaybookIndex:
    global _index
    if _index is None:
        _index = PlaybookIndex()
    return _index

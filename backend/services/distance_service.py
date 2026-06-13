"""景点步行距离服务。

距离来自 travel_guide/data/geo/<国家>_distances.json（build_distances.py 预计算，
相邻景点的 OSRM 真实步行距离 + 5km/h 步速时间）。
按"景点对"存（键 = 两景点排序后用 | 连接），后端按当天 activity 文本
实时拆景点查表，不依赖 day 编号（规划器会插入到达/离开日导致编号偏移）。
"""
import json
import re
from pathlib import Path

GEO_DIR = Path(__file__).parent.parent.parent / "travel_guide" / "data" / "geo"


class DistanceIndex:
    def __init__(self):
        self.pairs = {}  # "A|B"(已排序) -> {km, min}
        if GEO_DIR.exists():
            for f in GEO_DIR.glob("*_distances.json"):
                self.pairs.update(json.load(open(f, encoding="utf-8")))

    def legs_for_activity(self, activity):
        """把 activity 文本拆成景点序列，相邻两两查表，返回命中的距离条。
        [{from, to, km, min}]，没有任何命中则空列表。"""
        attrs = [a.strip() for a in re.split(r"[、,，]", activity or "") if a.strip()]
        # 去重保序
        seq, seen = [], set()
        for a in attrs:
            if a not in seen:
                seen.add(a)
                seq.append(a)
        legs = []
        for i in range(len(seq) - 1):
            a, b = seq[i], seq[i + 1]
            info = self.pairs.get("|".join(sorted([a, b])))
            if info:
                legs.append({"from": a, "to": b, "km": info["km"], "min": info["min"]})
        return legs


_index = None


def get_distance_index():
    global _index
    if _index is None:
        _index = DistanceIndex()
    return _index

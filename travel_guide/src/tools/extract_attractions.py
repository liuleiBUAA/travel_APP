"""从 destinations.json 提取景点清单。

用法:
    python3 extract_attractions.py <destinations.json路径> [更多路径...]

输出 JSON 到 stdout: [{"city": "巴黎", "attraction": "卢浮宫"}, ...]
"""
import json
import re
import sys

# activity 里出现但不是景点的词，跳过
SKIP_WORDS = {
    "自由活动", "购物", "休整", "返程", "回程", "抵达", "出发", "离开",
    "机场", "转机", "退房", "入住", "午餐", "晚餐", "美食", "返回",
}

# 单独出现时太泛、搜图必错的词（出现在组合词里如"圣马洛古城墙"则保留）
GENERIC_ALONE = {
    "老城", "古城", "海滩", "森林", "日落", "日出", "夜景", "城堡游",
    "老城漫步", "市区", "市中心", "漫步", "湖", "山",
}

SEPARATORS = re.compile(r"[、，,;；/]|\s+或\s+")
ARROW = re.compile(r"[→\-]>?|至|前往")


def extract(paths):
    seen = set()
    rows = []
    for path in paths:
        data = json.load(open(path, encoding="utf-8"))
        for city, info in data.items():
            for day in info.get("itinerary", []):
                activity = day.get("activity", "")
                for part in SEPARATORS.split(activity):
                    name = part.strip()
                    # 去掉括号注释，如 "凡尔赛宫（半日）"
                    name = re.sub(r"[（(].*?[)）]", "", name).strip()
                    # "巴黎→卢瓦尔河谷" 这种交通段：取箭头后的目的地
                    if ARROW.search(name):
                        name = ARROW.split(name)[-1].strip()
                    # "阿维尼翁：教皇宫" 这种前缀：取冒号后的景点
                    if "：" in name or ":" in name:
                        name = re.split(r"[：:]", name)[-1].strip()
                    if not name or len(name) < 2:
                        continue
                    if any(w in name for w in SKIP_WORDS):
                        continue
                    if name in GENERIC_ALONE:
                        continue
                    key = (city, name)
                    if key in seen:
                        continue
                    seen.add(key)
                    rows.append({"city": city, "attraction": name})
    return rows


if __name__ == "__main__":
    rows = extract(sys.argv[1:])
    print(json.dumps(rows, ensure_ascii=False, indent=1))

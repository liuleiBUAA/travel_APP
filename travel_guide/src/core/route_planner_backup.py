import json
import os
import itertools
import math
import re
import argparse
import sys

# ============================================================
# 联网查航班时刻开关（频次1-4次/天时启用）
# True = 用 Playwright 查 Google Flights 确认是否有晚班
# False = 给出两种方案（乐观/保守）
CHECK_LOW_FREQ_FLIGHTS = False
# ============================================================

def check_evening_flight(from_city_en, to_city_en):
    """联网查是否有18:00后的航班，返回 True/False/None(查询失败)"""
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            url = f"https://www.google.com/travel/flights?q=Flights%20from%20{from_city_en}%20to%20{to_city_en}&hl=en"
            page.goto(url, wait_until='domcontentloaded', timeout=20000)
            page.wait_for_timeout(5000)
            labels = page.evaluate("""() => {
                const cards = document.querySelectorAll('div.JMc5Xc');
                return Array.from(cards).map(c => c.getAttribute('aria-label')).filter(Boolean);
            }""")
            browser.close()
            nonstop = [l for l in labels if 'Nonstop' in l]
            for l in nonstop:
                m = re.search(r'Leaves .+ at (\d+):(\d+) (AM|PM)', l)
                if m:
                    hour = int(m.group(1))
                    period = m.group(3)
                    if period == 'PM' and hour != 12:
                        hour += 12
                    if hour >= 18:
                        return True
            return False
    except:
        return None

def load_json(path):
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def load_config(base_dir):
    """加载 config.json，不存在则返回默认值"""
    defaults = {
        "same_day_max_hours": 4.0,
        "check_low_freq_flights": False,
        "options_display_mode": "detailed",  # "detailed" 或 "compact"
        "force_gateway_departure": False,  # 是否强制从国际门户城市离开
        "transport_preference": "train",  # 交通偏好：auto/train/drive
    }
    cfg_path = os.path.join(base_dir, "config/config.json")
    if os.path.exists(cfg_path):
        with open(cfg_path, "r", encoding="utf-8") as f:
            user_cfg = json.load(f)
        defaults.update(user_cfg)
    return defaults

class TravelEngine:
    def __init__(self, base_dir, same_day_max_hours=None):
        self.base_dir = base_dir
        cfg = load_config(base_dir)
        # 优先用显式传入的参数，否则读 config.json
        self.same_day_max_hours = same_day_max_hours if same_day_max_hours is not None else cfg["same_day_max_hours"]
        self.options_display_mode = cfg["options_display_mode"]  # Options显示模式
        self.force_gateway_departure = cfg["force_gateway_departure"]  # 是否强制从门户城市离开
        self.transport_preference = cfg["transport_preference"]  # 交通偏好
        global CHECK_LOW_FREQ_FLIGHTS
        CHECK_LOW_FREQ_FLIGHTS = cfg["check_low_freq_flights"]
        # 加载坐标：先根目录，再各区域合并
        self.coords = load_json(os.path.join(base_dir, "city_coordinates.json"))
        for region in ["Europe", "North_America", "Oceania", "Asia"]:
            region_coords = load_json(os.path.join(base_dir, "data", region, "city_coordinates.json"))
            self.coords.update(region_coords)

        # 加载城市→区域映射（用于快速判断城市属于哪个区域）
        self.city_to_region = load_json(os.path.join(base_dir, "config/city_to_region.json"))

        # 先加载根目录 mapping，再用各区域的覆盖（区域优先）
        self.mapping = load_json(os.path.join(base_dir, "city_mapping.json"))
        for region in ["Europe", "North_America", "Oceania", "Asia"]:
            region_mapping = load_json(os.path.join(base_dir, "data", region, "city_mapping.json"))
            self.mapping.update(region_mapping)
        
        self.trans_db = {}
        # 优先加载 transport_routes.json（最新数据）
        for region in ["Europe", "North_America", "Oceania", "Asia"]:
            correct_p = os.path.join(base_dir, "data", region, "transport_routes.json")
            preset_p = os.path.join(base_dir, "data", region, "transport_preset.json")
            if os.path.exists(correct_p):
                data = load_json(correct_p)
                for k, v in data.items():
                    if "->" in k or "→" in k:
                        self.trans_db[k] = v
                    elif isinstance(v, dict):
                        # 处理嵌套结构（如"澳大利亚东海岸": {"悉尼->墨尔本": ...}）
                        for sub_k, sub_v in v.items():
                            if "->" in sub_k or "→" in sub_k:
                                self.trans_db[sub_k] = sub_v
            elif os.path.exists(preset_p):
                data = load_json(preset_p)
                for k, v in data.items():
                    if "->" in k or "→" in k:
                        self.trans_db[k] = v
                    elif isinstance(v, dict):
                        for sub_k, sub_v in v.items():
                            if "->" in sub_k or "→" in sub_k:
                                self.trans_db[sub_k] = sub_v

        # 加载依附关系（统一格式：三大洲都用"依附关系"key）
        self.dependencies = {}
        for region in ["Europe", "North_America", "Oceania", "Asia"]:
            dep_p = os.path.join(base_dir, "data", region, "city_dependencies.json")
            if os.path.exists(dep_p):
                data = load_json(dep_p)
                if "依附关系" in data:
                    self.dependencies.update(data["依附关系"])

        self.dest_db = {}
        for root, _, files in os.walk(base_dir):
            # 跳过备份文件夹
            if '备份' in root or '_backup' in root.lower():
                continue
            for file in files:
                if file.endswith("_destinations.json"):
                    data = load_json(os.path.join(root, file))
                    self.dest_db.update(data)

    def _lookup_edge(self, c1, c2):
        """直接查路线数据库，支持 -> 和 → 两种格式"""
        for k in [f"{c1}->{c2}", f"{c2}->{c1}", f"{c1}→{c2}", f"{c2}→{c1}"]:
            if k in self.trans_db:
                return self.trans_db[k]
        return None

    def _edge_min_time(self, edge):
        """取一条路线的最优交通时间（飞机含1h安检值机，无飞机时考虑交通偏好）"""
        train = edge.get("train_time_hours")
        drive = edge.get("drive_time_hours")
        flight = edge.get("flight_time_hours")
        # 有飞机时，直接比较所有方式
        if flight:
            times = [flight + 1.0]  # 飞机加1h安检值机
            if train: times.append(train)
            if drive: times.append(drive)
            return min(times)
        # 无飞机时，应用交通偏好
        if train and drive:
            pref = getattr(self, 'transport_preference', 'train')
            if pref == 'train' and train <= drive * 1.5:
                return train
            elif pref == 'drive' and drive <= train * 1.5:
                return drive
            return min(train, drive)
        if train: return train
        if drive: return drive
        return 99.0

    def _edge_score(self, edge, from_en=None, to_en=None):
        """综合评分：时间越短越好，航班频次越高越好（高频航班可选早晚班，不占白天）"""
        if not edge:
            return 99.0
        flight_t = edge.get("flight_time_hours")
        train_t = edge.get("train_time_hours")
        drive_t = edge.get("drive_time_hours")
        freq = edge.get("flight_frequency_per_day") or 0

        if flight_t:
            flight_t = flight_t + 1.0  # 加1h安检值机时间
            if freq >= 10:
                flight_score = flight_t * 0.3
            elif freq >= 5:
                flight_score = flight_t * 0.5
            elif 1 <= freq <= 4:
                # 低频航班：尝试联网查是否有晚班
                if CHECK_LOW_FREQ_FLIGHTS and from_en and to_en:
                    has_evening = check_evening_flight(from_en, to_en)
                    if has_evening is True:
                        flight_score = flight_t * 0.6   # 有晚班，较灵活
                        edge['_has_evening'] = True
                    elif has_evening is False:
                        flight_score = flight_t * 1.0   # 只有白天班，占游玩时间
                        edge['_has_evening'] = False
                    else:
                        # 查询失败，给出两种方案标记
                        edge['_uncertain'] = True
                        flight_score = flight_t * 0.8   # 中间值
                else:
                    # 未开启联网，标记为不确定
                    edge['_uncertain'] = True
                    flight_score = flight_t * 0.8
            else:
                flight_score = flight_t * 1.2
        else:
            flight_score = 99.0

        train_score = train_t if train_t else 99.0
        drive_score = drive_t if drive_t else 99.0

        # 根据 transport_preference 调整火车 vs 自驾的优先级（只在没有飞机时生效）
        if flight_score >= 99.0 and train_score < 99.0 and drive_score < 99.0:
            pref = getattr(self, 'transport_preference', 'train')  # 默认优先火车
            if pref == 'train':
                drive_score = drive_score * 1.5  # 给自驾加惩罚
            elif pref == 'drive':
                train_score = train_score * 1.5  # 给火车加惩罚
            # pref == 'auto' 则不做调整

        return min(flight_score, train_score, drive_score)

    def get_transport(self, raw_c1, raw_c2, orig_c1=None):
        """orig_c1: 原始目的地名（当 raw_c1 是 stay 字段时，传入目的地名用于查依附关系）"""
        c1 = self.mapping.get(raw_c1, raw_c1)
        c2 = self.mapping.get(raw_c2, raw_c2)

        # 1. 先查直接路线
        edge = self._lookup_edge(c1, c2)
        direct_result = None
        direct_min_t = 99.0
        if edge:
            direct_min_t = self._edge_min_time(edge)
            direct_result = {"train": edge.get("train_time_hours"),
                    "drive": edge.get("drive_time_hours"),
                    "flight": edge.get("flight_time_hours"),
                    "note": edge.get("note", "")}
            # 直达时间短，直接返回不需要找中转
            if direct_min_t <= self.same_day_max_hours:
                return direct_result

        # 2. c2 有依附关系（目的地有hub）
        hubs2 = self.dependencies.get(raw_c2, self.dependencies.get(c2, []))

        # 2.5 c1直达c2的枢纽城市
        if hubs2:
            best_total, best_result = 99.0, None
            for hub in hubs2:
                e1 = self._lookup_edge(c1, hub) or self._lookup_edge(raw_c1, hub)
                if not e1:
                    continue
                t1 = self._edge_min_time(e1)
                # 检查hub是"组成部分"还是"中转门户"
                e2 = self._lookup_edge(hub, c2) or self._lookup_edge(hub, raw_c2)
                t2 = self._edge_min_time(e2) if e2 else 0
                total = t1 + t2
                if total < best_total:
                    best_total = total
                    if e2:
                        # 中转门户：需要显示两段路线
                        mode1 = "飞机" if e1.get("flight_time_hours") and t1 == e1.get("flight_time_hours") + 1.0 else \
                                "火车" if e1.get("train_time_hours") and t1 == e1.get("train_time_hours") else "自驾"
                        mode2 = "飞机" if e2.get("flight_time_hours") and t2 == e2.get("flight_time_hours") + 1.0 else \
                                "火车" if e2.get("train_time_hours") and t2 == e2.get("train_time_hours") else "自驾"
                        t1_str = f"{e1.get('flight_time_hours') + 1.0:.2f}h飞机（{e1.get('flight_time_hours'):.2f}h飞行 + 1.0h安检）" if mode1 == "飞机" else f"{t1:.2f}h{mode1}"
                        t2_str = f"{e2.get('flight_time_hours') + 1.0:.2f}h飞机（{e2.get('flight_time_hours'):.2f}h飞行 + 1.0h安检）" if mode2 == "飞机" else f"{t2:.2f}h{mode2}"
                        detail = f"{raw_c1}→{hub}({t1_str}) → {hub}→{raw_c2}({t2_str})"
                        best_result = {"train": None, "drive": None, "flight": None,
                                       "_total": round(total, 2), "_detail": detail,
                                       "note": f"经{hub}"}
                    else:
                        # 组成部分：到达枢纽即到达目的地
                        best_result = {"train": e1.get("train_time_hours"),
                                       "drive": e1.get("drive_time_hours"),
                                       "flight": e1.get("flight_time_hours"),
                                       "note": f"到{hub}"}
            if best_result:
                if direct_result and direct_min_t <= best_total:
                    return direct_result
                return best_result

        # 3. c1 有依附关系，找各枢纽到下一个城市最近的
        # 同时查 orig_c1（原始目的地名）的依附关系，解决 stay 字段与目的地名不一致的问题
        hubs1 = (self.dependencies.get(c1, []) or self.dependencies.get(raw_c1, []) or
                 (self.dependencies.get(orig_c1, []) if orig_c1 else []))
        if hubs1:
            best_score, best_total, best_hub, best_leg1, best_leg2 = 99.0, 99.0, None, None, None
            for hub in hubs1:
                e1 = self._lookup_edge(c1, hub) or self._lookup_edge(raw_c1, hub)
                e2 = self._lookup_edge(hub, c2)
                if e2:
                    t1 = self._edge_min_time(e1) if e1 else 0
                    s2 = self._edge_score(e2)
                    score = t1 + s2
                    total = t1 + self._edge_min_time(e2)
                    if score < best_score:
                        best_score, best_total, best_hub, best_leg1, best_leg2 = score, total, hub, e1, e2
            if best_leg2:
                total_h = round(best_total, 2)
                t1 = self._edge_min_time(best_leg1) if best_leg1 else 0
                t2 = self._edge_min_time(best_leg2)
                mode1 = "飞机" if best_leg1 and best_leg1.get("flight_time_hours") and self._edge_min_time(best_leg1) == best_leg1.get("flight_time_hours") + 1.0 else                         "火车" if best_leg1 and best_leg1.get("train_time_hours") and self._edge_min_time(best_leg1) == best_leg1.get("train_time_hours") else "自驾"
                mode2 = "飞机" if best_leg2.get("flight_time_hours") and self._edge_min_time(best_leg2) == best_leg2.get("flight_time_hours") + 1.0 else                         "火车" if best_leg2.get("train_time_hours") and self._edge_min_time(best_leg2) == best_leg2.get("train_time_hours") else "自驾"
                t1_str = f"{best_leg1.get('flight_time_hours') + 1.0:.2f}h飞机（{best_leg1.get('flight_time_hours'):.2f}h飞行 + 1.0h安检）" if mode1 == "飞机" else f"{t1:.2f}h{mode1}"
                t2_str = f"{best_leg2.get('flight_time_hours') + 1.0:.2f}h飞机（{best_leg2.get('flight_time_hours'):.2f}h飞行 + 1.0h安检）" if mode2 == "飞机" else f"{t2:.2f}h{mode2}"
                detail = f"{raw_c1}→{best_hub}({t1_str}) → {best_hub}→{raw_c2}({t2_str})"
                if direct_result and direct_min_t <= total_h:
                    return direct_result
                return {"train": None, "drive": None, "flight": None,
                        "_total": total_h,
                        "_detail": detail,
                        "note": f"经{best_hub}"}

        # 4. 双枢纽中转：A的枢纽→B的枢纽
        if hubs1 and hubs2:
            best_score, best_total, best_hub1, best_hub2 = 99.0, 99.0, None, None
            for h1 in hubs1:
                for h2 in hubs2:
                    e_mid = self._lookup_edge(h1, h2)
                    if e_mid:
                        e1 = self._lookup_edge(c1, h1) or self._lookup_edge(raw_c1, h1)
                        e2 = self._lookup_edge(h2, c2)
                        t1 = self._edge_min_time(e1) if e1 else 0
                        s_mid = self._edge_score(e_mid)
                        t2 = self._edge_min_time(e2) if e2 else 0
                        score = t1 + s_mid + t2
                        total = t1 + self._edge_min_time(e_mid) + t2
                        if score < best_score:
                            best_score, best_total, best_hub1, best_hub2 = score, total, h1, h2
            if best_hub1:
                total_h = round(best_total, 2)
                # 这里需要重新查一次 best_legs
                e1 = self._lookup_edge(c1, best_hub1) or self._lookup_edge(raw_c1, best_hub1)
                e_mid = self._lookup_edge(best_hub1, best_hub2)
                e2 = self._lookup_edge(best_hub2, c2)
                t1 = self._edge_min_time(e1) if e1 else 0
                t_mid = self._edge_min_time(e_mid) if e_mid else 0
                t2 = self._edge_min_time(e2) if e2 else 0
                mode1 = "飞机" if e1 and e1.get("flight_time_hours") and self._edge_min_time(e1) == e1.get("flight_time_hours") + 1.0 else                         "火车" if e1 and e1.get("train_time_hours") and self._edge_min_time(e1) == e1.get("train_time_hours") else "自驾"
                mode_mid = "飞机" if e_mid and e_mid.get("flight_time_hours") and self._edge_min_time(e_mid) == e_mid.get("flight_time_hours") + 1.0 else                            "火车" if e_mid and e_mid.get("train_time_hours") and self._edge_min_time(e_mid) == e_mid.get("train_time_hours") else "自驾"
                mode2 = "飞机" if e2 and e2.get("flight_time_hours") and self._edge_min_time(e2) == e2.get("flight_time_hours") + 1.0 else                         "火车" if e2 and e2.get("train_time_hours") and self._edge_min_time(e2) == e2.get("train_time_hours") else "自驾"
                t1_str = f"{e1.get('flight_time_hours') + 1.0:.2f}h飞机（{e1.get('flight_time_hours'):.2f}h飞行 + 1.0h安检）" if mode1 == "飞机" else f"{t1:.2f}h{mode1}"
                mid_str = f"{e_mid.get('flight_time_hours') + 1.0:.2f}h飞机（{e_mid.get('flight_time_hours'):.2f}h飞行 + 1.0h安检）" if mode_mid == "飞机" else f"{t_mid:.2f}h{mode_mid}"
                t2_str = f"{e2.get('flight_time_hours') + 1.0:.2f}h飞机（{e2.get('flight_time_hours'):.2f}h飞行 + 1.0h安检）" if mode2 == "飞机" else f"{t2:.2f}h{mode2}"
                detail = f"{raw_c1}→{best_hub1}({t1_str}) → {best_hub1}→{best_hub2}({mid_str}) → {best_hub2}→{raw_c2}({t2_str})"
                if direct_result and direct_min_t <= total_h:
                    return direct_result
                return {"train": None, "drive": None, "flight": None,
                        "_total": total_h,
                        "_detail": detail,
                        "note": f"经{best_hub1}→{best_hub2}"}

        # 5. 智能中转：遍历所有可能的中转城市，找A→C→B最短路径
        # 从trans_db中提取所有唯一的城市作为候选中转点
        all_cities = set()
        for route_key in self.trans_db.keys():
            # route_key格式: "城市1->城市2" 或 "城市1→城市2"
            if "->" in route_key:
                cities = route_key.split("->")
            elif "→" in route_key:
                cities = route_key.split("→")
            else:
                continue
            if len(cities) == 2:
                all_cities.add(cities[0].strip())
                all_cities.add(cities[1].strip())

        # 尝试所有可能的中转城市
        best_transit_score = 99.0
        best_transit_total = 99.0
        best_transit_city = None
        best_transit_dest = None  # 实际到达的目的地城市（可能是c2本身或其枢纽）
        best_leg1 = None
        best_leg2 = None
        best_leg_last = None  # 枢纽→最终目的地的最后一段

        # 同时尝试到达枢纽城市和目的地本身
        target_cities = list(set((hubs2 or []) + [c2]))

        for transit_city in all_cities:
            # 跳过起点和终点本身
            if transit_city == c1 or transit_city == c2 or transit_city == raw_c1 or transit_city == raw_c2:
                continue

            # 查询 A→中转
            e1 = self._lookup_edge(c1, transit_city) or self._lookup_edge(raw_c1, transit_city)
            if not e1:
                continue

            # 尝试 中转→目标城市（可能是c2本身，也可能是其枢纽）
            for target_city in target_cities:
                if transit_city == target_city:  # 跳过中转城市本身
                    continue

                e2 = self._lookup_edge(transit_city, target_city)
                if e2:
                    # 计算总分数和总时间
                    s1 = self._edge_score(e1)
                    s2 = self._edge_score(e2)
                    score = s1 + s2
                    total = self._edge_min_time(e1) + self._edge_min_time(e2)

                    # 如果target是枢纽城市（不是最终目的地），加上枢纽→目的地的时间
                    e_last = None
                    if target_city != c2 and target_city != raw_c2:
                        if target_city in (hubs2 or []):
                            e_last = None  # 到达枢纽即到达目的地，无需last-mile
                        else:
                            e_last = self._lookup_edge(target_city, c2) or self._lookup_edge(target_city, raw_c2)
                            if e_last:
                                score += self._edge_score(e_last)
                                total += self._edge_min_time(e_last)
                            else:
                                continue  # 非枢纽且无路线，跳过

                    if score < best_transit_score:
                        best_transit_score = score
                        best_transit_total = total
                        best_transit_city = transit_city
                        best_transit_dest = target_city
                        best_leg1 = e1
                        best_leg2 = e2
                        best_leg_last = e_last

        if best_transit_city:
            total_h = round(best_transit_total, 2)
            t1 = self._edge_min_time(best_leg1)
            t2 = self._edge_min_time(best_leg2)
            mode1 = "飞机" if best_leg1.get("flight_time_hours") and self._edge_min_time(best_leg1) == best_leg1.get("flight_time_hours") + 1.0 else \
                    "火车" if best_leg1.get("train_time_hours") and self._edge_min_time(best_leg1) == best_leg1.get("train_time_hours") else "自驾"
            mode2 = "飞机" if best_leg2.get("flight_time_hours") and self._edge_min_time(best_leg2) == best_leg2.get("flight_time_hours") + 1.0 else \
                    "火车" if best_leg2.get("train_time_hours") and self._edge_min_time(best_leg2) == best_leg2.get("train_time_hours") else "自驾"
            t1_str = f"{best_leg1.get('flight_time_hours') + 1.0:.2f}h飞机（{best_leg1.get('flight_time_hours'):.2f}h飞行 + 1.0h安检）" if mode1 == "飞机" else f"{t1:.2f}h{mode1}"
            t2_str = f"{best_leg2.get('flight_time_hours') + 1.0:.2f}h飞机（{best_leg2.get('flight_time_hours'):.2f}h飞行 + 1.0h安检）" if mode2 == "飞机" else f"{t2:.2f}h{mode2}"
            if best_leg_last:
                # 经枢纽到达目的地：显示三段路线
                t3 = self._edge_min_time(best_leg_last)
                mode3 = "飞机" if best_leg_last.get("flight_time_hours") and self._edge_min_time(best_leg_last) == best_leg_last.get("flight_time_hours") + 1.0 else \
                        "火车" if best_leg_last.get("train_time_hours") and self._edge_min_time(best_leg_last) == best_leg_last.get("train_time_hours") else "自驾"
                t3_str = f"{best_leg_last.get('flight_time_hours') + 1.0:.2f}h飞机（{best_leg_last.get('flight_time_hours'):.2f}h飞行 + 1.0h安检）" if mode3 == "飞机" else f"{t3:.2f}h{mode3}"
                detail = f"{raw_c1}→{best_transit_city}({t1_str}) → {best_transit_city}→{best_transit_dest}({t2_str}) → {best_transit_dest}→{raw_c2}({t3_str})"
                if direct_result and direct_min_t <= total_h:
                    return direct_result
                return {"train": None, "drive": None, "flight": None,
                        "_total": total_h,
                        "_detail": detail,
                        "note": f"经{best_transit_city}→{best_transit_dest}"}
            else:
                # 直接到达目的地
                detail = f"{raw_c1}→{best_transit_city}({t1_str}) → {best_transit_city}→{raw_c2}({t2_str})"
                if direct_result and direct_min_t <= total_h:
                    return direct_result
                return {"train": None, "drive": None, "flight": None,
                        "_total": total_h,
                        "_detail": detail,
                        "note": f"经{best_transit_city}"}

        # 没找到更优的中转路线，返回直达（如果有）
        if direct_result:
            return direct_result
        return {"train": None, "drive": None, "flight": None, "note": ""}

    def haversine(self, coord1, coord2):
        R = 6371
        lat1, lon1 = math.radians(coord1[0]), math.radians(coord1[1])
        lat2, lon2 = math.radians(coord2[0]), math.radians(coord2[1])
        a = math.sin((lat2-lat1)/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin((dlon:=math.radians(coord2[1]-coord1[1]))/2)**2
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

    def get_region_for_city(self, city_name):
        """
        根据城市名快速判断属于哪个区域

        Args:
            city_name: 城市名（可以是别名）

        Returns:
            str: 区域名（"Europe"/"North_America"/"Oceania"/"Asia"），未找到返回None
        """
        # 1. 直接查询映射表
        if city_name in self.city_to_region:
            return self.city_to_region[city_name]

        # 2. 尝试mapping后再查询
        mapped_name = self.mapping.get(city_name, city_name)
        if mapped_name in self.city_to_region:
            return self.city_to_region[mapped_name]

        # 3. Fallback：遍历destinations（兼容映射表未更新的情况）
        for region in ["Europe", "North_America", "Oceania", "Asia"]:
            if city_name in self.dest_db or mapped_name in self.dest_db:
                # 通过dest_db反向查找区域
                for k in self.dest_db.keys():
                    if city_name in k or mapped_name in k:
                        # 简单启发：检查k是否在该区域的destinations中
                        region_path = os.path.join(self.base_dir, "data", region, "guides")
                        if os.path.exists(region_path):
                            return region

        return None

    def get_best_cost(self, c1, c2):
        t = self.get_transport(c1, c2)

        # 如果有 _total 字段（多跳路线），直接返回
        if "_total" in t and t["_total"] is not None:
            return float(t["_total"])

        train_t = float(t["train"] or 99)
        drive_t = float(t["drive"] or 99)
        flight_t = float(t["flight"] or 99)
        flight_actual = flight_t + 1.0 if flight_t < 99 else 99.0  # 飞机加1h安检

        # 应用 transport_preference（与 _edge_score 逻辑一致）
        train_score, flight_score, drive_score = train_t, flight_actual, drive_t
        if flight_score >= 99.0 and train_score < 99.0 and drive_score < 99.0:
            pref = self.transport_preference
            if pref == 'train':
                drive_score = drive_score * 1.5
            elif pref == 'drive':
                train_score = train_score * 1.5

        return min(train_score, drive_score, flight_score)

    def detect_backtrack(self, route):
        """检测路线是否走回头路，返回回头次数"""
        if len(route) < 3:
            return 0
        
        backtrack_count = 0
        for i in range(len(route) - 2):
            # 计算三个连续城市的距离
            d_ab = self.get_best_cost(route[i], route[i+1])
            d_bc = self.get_best_cost(route[i+1], route[i+2])
            d_ac = self.get_best_cost(route[i], route[i+2])
            
            # 如果 A→B→C 的距离 > A→C 的距离 * 1.3，说明走了回头路
            if d_ab + d_bc > d_ac * 1.3:
                backtrack_count += 1
        
        return backtrack_count
    
    def optimize_order_no_backtrack(self, raw_nodes, start_node=None, end_node=None):
        """优化顺序，优先避免回头路，其次考虑总距离"""
        if len(raw_nodes) <= 2:
            return raw_nodes
        
        # 如果指定了起点和终点，固定它们
        if start_node and end_node:
            middle = [n for n in raw_nodes if n != start_node and n != end_node]
            if not middle:
                return [start_node, end_node]
            
            # 尝试所有中间城市的排列
            import itertools
            best_route = None
            best_score = float('inf')
            
            for perm in itertools.permutations(middle):
                route = [start_node] + list(perm) + [end_node]
                
                # 计算总距离
                total_cost = sum(self.get_best_cost(route[i], route[i+1]) for i in range(len(route)-1))
                
                # 计算回头次数
                backtrack_count = self.detect_backtrack(route)

                # 综合评分：回头次数权重50，总距离权重1
                score = backtrack_count * 50 + total_cost
                
                if score < best_score:
                    best_score = score
                    best_route = route
            
            return best_route
        else:
            # 没有指定起终点，也使用避免回头路的逻辑
            import itertools
            best_route = None
            best_score = float('inf')

            for perm in itertools.permutations(raw_nodes):
                route = list(perm)
                total_cost = sum(self.get_best_cost(route[i], route[i+1]) for i in range(len(route)-1))
                backtrack_count = self.detect_backtrack(route)
                score = backtrack_count * 50 + total_cost

                if score < best_score:
                    best_score = score
                    best_route = route

            return best_route if best_route else raw_nodes

    def plan(self, name, raw_nodes, start_node=None, end_node=None, force_order=False, same_day_max_hours=None, region=None):
        # ── 检测是否有loop/linear，如果有则不优化顺序 ──────────────────
        has_special = False
        for node in raw_nodes:
            mapped_node = self.mapping.get(node, node)
            dest_data = self.dest_db.get(mapped_node) or self.dest_db.get(node)
            if dest_data and dest_data.get('loop_type') in ['loop', 'linear']:
                has_special = True
                break

        if force_order or has_special:
            # 有loop/linear时保持用户输入顺序（用户配置时已考虑好）
            nodes = raw_nodes
        else:
            # 纯普通城市，使用避免回头路的优化逻辑
            nodes = self.optimize_order_no_backtrack(raw_nodes, start_node, end_node)
        # ── 预处理结束 ──────────────────────────────────────────────
        itinerary, day = [], 1
        # 记录每个节点处理完后的"实际离开城市"，供下一节点计算跨城交通用
        node_exit_city = {}  # index -> 离开时所在城市
        visited_cities = set()  # 记录已展开行程的城市，避免重复展开

        for i, node in enumerate(nodes):
            # 先 mapping 再查 dest_db
            mapped_node = self.mapping.get(node, node)
            # 引号标准化：将英文直引号转为中文弯引号，确保匹配
            def normalize_quotes(s):
                # 简单策略：奇数位置的"转左引号，偶数位置转右引号
                result = []
                count = 0
                for ch in s:
                    if ch == '"':
                        result.append('\u201c' if count % 2 == 0 else '\u201d')
                        count += 1
                    else:
                        result.append(ch)
                return ''.join(result)
            norm_node = normalize_quotes(node)
            norm_mapped = normalize_quotes(mapped_node)
            dest_data = (self.dest_db.get(mapped_node) or self.dest_db.get(node)
                         or self.dest_db.get(norm_mapped) or self.dest_db.get(norm_node))
            if not dest_data:
                for k, v in self.dest_db.items():
                    if node in k or mapped_node in k or norm_node in k: dest_data = v; break

            # ── 环线节点识别 ──────────────────────────────────────────
            loop_type = dest_data.get('loop_type') if dest_data else None
            hub_city  = dest_data.get('hub_city')  if dest_data else None
            end_city  = dest_data.get('end_city')  if dest_data else None

            if loop_type and hub_city:
                # 1. 计算进入环线的交通（从上一站 → hub_city）
                if i > 0:
                    from_city = node_exit_city.get(i-1, nodes[i-1])
                    if from_city != hub_city:
                        t = self.get_transport(from_city, hub_city, orig_c1=nodes[i-1])
                        if "_total" in t:
                            real_min_t = t["_total"]
                        else:
                            train_t = float(t["train"] or 99)
                            flight_t = float(t["flight"] or 99)
                            drive_t  = float(t["drive"]  or 99)
                            flight_actual = flight_t + 1.0 if flight_t < 99 else 99.0  # 飞机加1h安检
                            real_min_t = min(train_t, flight_actual, drive_t)
                        threshold = same_day_max_hours if same_day_max_hours is not None else self.same_day_max_hours
                        if real_min_t >= threshold and real_min_t != 99.0:
                            if "_detail" in t:   desc = f"🚆/✈️ {t['_detail']}"
                            elif "_total" in t:  desc = f"🚆/✈️ 约 {t['_total']}h"
                            elif real_min_t == float(t["train"] or 99): desc = f"🚆 火车约 {t['train'] if t['train'] else '-'}h"
                            elif real_min_t == float(t["drive"]  or 99): desc = f"🚗 自驾约 {t['drive'] if t['drive'] else '-'}h"
                            else:
                                flight_t = t['flight']
                                if flight_t:
                                    desc = f"✈️ 飞机约 {flight_t + 1.0:.2f}h（{flight_t:.2f}h飞行 + 1.0h安检）"
                                else:
                                    desc = f"✈️ 飞机约 -h"
                            itinerary.append({"day": day, "city": f"{from_city} ➔ {hub_city}", "activity": f"【大交通】前往{hub_city}，开始{node}", "transport": desc, "stay": hub_city})
                            day += 1
                        else:
                            if itinerary:
                                if "_detail" in t:   desc = f"🚆/✈️ {t['_detail']}"
                                elif "_total" in t:  desc = f"🚆/✈️ 约 {t['_total']}h"
                                elif real_min_t == float(t["train"] or 99): desc = f"🚆 火车 {t['train'] if t['train'] else '-'}h"
                                elif real_min_t == float(t["drive"]  or 99): desc = f"🚗 自驾 {t['drive'] if t['drive'] else '-'}h"
                                else:
                                    flight_t = t['flight']
                                    if flight_t:
                                        desc = f"✈️ 飞机 {flight_t + 1.0:.2f}h（{flight_t:.2f}h飞行 + 1.0h安检）"
                                    else:
                                        desc = f"✈️ 飞机 -h"
                                itinerary[-1]["activity"] += f" + 适时前往 {hub_city}"
                                itinerary[-1]["transport"] = f"当地 | 跨城:{desc}"
                                itinerary[-1]["stay"] = hub_city

                # 2. 展开环线逐日行程
                raw_plays = dest_data.get("itinerary", [])
                loop_label = dest_data.get('full_title', node)
                for p in raw_plays:
                    itinerary.append({
                        "day": day,
                        "city": f"[{loop_label}] {p.get('stay', hub_city)}",
                        "activity": p["activity"],
                        "transport": p.get("transport", "🚗 自驾"),
                        "stay": p.get("stay", hub_city) if p.get("stay") not in ["-", None] else hub_city
                    })
                    day += 1

                # 3. 记录离开城市
                if loop_type == 'loop':
                    node_exit_city[i] = hub_city   # 环线回到起点
                else:
                    node_exit_city[i] = end_city or hub_city  # linear 落在终点
                continue  # 跳过下面的普通节点逻辑
            # ── 环线节点识别结束 ──────────────────────────────────────

            # 同一城市第二次出现时，只作为中转/离开点，不重复展开行程
            city_key = mapped_node or node
            if city_key in visited_cities:
                # 只记录离开城市，不展开行程（交通衔接由下一节点处理）
                node_exit_city[i] = city_key
                continue
            visited_cities.add(city_key)

            raw_plays = dest_data["itinerary"] if dest_data else [{"activity": f"游览{node}核心景点", "stay": node, "transport": "当地交通"}]
            # 处理 options：根据下一个 destination 自动选择选项
            plays = []
            next_node = nodes[i+1] if i+1 < len(nodes) else None
            next_mapped = self.mapping.get(next_node, next_node) if next_node else None
            for p in raw_plays:
                if 'options' not in p:
                    plays.append(p)
                    continue

                # 如果是最后一站且有options，忽略options，只保留当地活动
                if not next_node:
                    plays.append({
                        "activity": p['activity'],
                        "stay": p.get('stay', node),
                        "transport": p.get("transport", "当地交通")
                    })
                    continue

                # 找匹配的选项
                chosen = None
                option_matched = False  # 标记是否真的匹配到next_node
                all_options_desc = []
                for opt in p['options']:
                    drive_str = f"🚗 {opt['drive']}h" if opt.get('drive') else ''
                    train_str = f" / 🚆 {opt['train']}h" if opt.get('train') else ''
                    all_options_desc.append(f"  • {opt['label']}：{drive_str}{train_str}　{opt.get('detail','')}" )
                    if any(t in [next_node, next_mapped] for t in opt.get('to', [])):
                        chosen = opt
                        option_matched = True
                if not chosen:
                    chosen = p['options'][0]  # 默认第一个，但没有真正匹配

                # 根据配置选择显示模式
                drive = chosen.get('drive') or 99
                train = chosen.get('train') or 99

                if self.options_display_mode == "compact":
                    # 简洁模式（Europe风格）：判断当天到达，合并进activity
                    travel_h = min(drive, train)
                    max_h = same_day_max_hours if same_day_max_hours is not None else self.same_day_max_hours
                    if travel_h <= max_h:
                        # 当天到当天玩：把交通信息拼进 activity
                        transport_modes = []
                        if drive and drive < 99:
                            transport_modes.append(f"🚗 自驾{drive}h")
                        if train and train < 99:
                            transport_modes.append(f"🚆 火车{train}h")
                        transport_str = " 或 ".join(transport_modes) if transport_modes else "当地交通"
                        activity = p['activity'] + f"，前往{chosen['stay']}（{transport_str}）"
                    else:
                        activity = p['activity']
                else:
                    # 详细模式（North_America风格）：显示所有选项
                    options_text = '\n'.join(all_options_desc)
                    activity = p['activity'] + '\n【可选路线】\n' + options_text + '\n【本次选择】' + chosen['label']

                new_p = dict(p)
                new_p['activity'] = activity
                new_p['stay'] = chosen['stay']
                # 生成transport字符串，只包含有效的交通方式（< 99）
                transport_modes = []
                if train and train < 99:
                    transport_modes.append(f"🚆 火车约{train}h")
                if drive and drive < 99:
                    transport_modes.append(f"🚗 自驾约{drive}h")
                if transport_modes:
                    new_p['transport'] = " 或 ".join(transport_modes)
                else:
                    new_p['transport'] = "当地交通"
                # 只有真正匹配到next_node的option才标记为包含交通信息
                if option_matched:
                    new_p['_chosen_option'] = chosen
                plays.append(new_p)
            
            if i == 0:
                for p in plays:
                    itinerary.append({"day": day, "city": node, "activity": p["activity"], "transport": p.get("transport", "当地交通"), "stay": p.get("stay", node) if p.get("stay") != "-" else node, "_has_option_transport": "_chosen_option" in p})
                    day += 1
            else:
                # 优先用 node_exit_city 记录的上一站实际离开城市（环线会更新这个）
                prev_node = node_exit_city.get(i-1, nodes[i-1])
                # 如果上一站最后一天已经通过 options 包含了到本站的交通，直接跳过跨城计算
                if itinerary and itinerary[-1].get('_has_option_transport') and itinerary[-1].get('stay', '') not in ['', '-']:
                    for p in plays:
                        itinerary.append({"day": day, "city": node, "activity": p["activity"], "transport": p.get("transport", "当地交通"), "stay": p.get("stay", node) if p.get("stay") != "-" else node, "_has_option_transport": "_chosen_option" in p})
                        day += 1
                    continue
                # 检查上一个城市的最后一天是否返回枢纽城市
                # 如果返回了，跨城交通应该从枢纽出发
                # 如果上一站离开城市和当前节点相同（linear环线end_city==下一节点），跳过跨城
                if self.mapping.get(prev_node, prev_node) == self.mapping.get(node, node) or prev_node == node:
                    for p in plays:
                        itinerary.append({"day": day, "city": node, "activity": p["activity"], "transport": p.get("transport", "当地交通"), "stay": p.get("stay", node) if p.get("stay") != "-" else node, "_has_option_transport": "_chosen_option" in p})
                        day += 1
                    continue

                prev_mapped = self.mapping.get(prev_node, prev_node)
                prev_dest_data = self.dest_db.get(prev_mapped) or self.dest_db.get(prev_node)

                # 检查上一个节点（原始destination）是否是loop/linear
                prev_original_node = nodes[i-1]
                prev_original_mapped = self.mapping.get(prev_original_node, prev_original_node)
                prev_original_data = self.dest_db.get(prev_original_mapped) or self.dest_db.get(prev_original_node)
                prev_is_special = prev_original_data and prev_original_data.get('loop_type') in ['loop', 'linear']

                if prev_dest_data and 'itinerary' in prev_dest_data:
                    last_day = prev_dest_data['itinerary'][-1]
                    last_activity = last_day.get('activity', '')
                    # 如果最后一天提到"返回"或"前往下一个目的地"，且有枢纽城市
                    if ('返回' in last_activity or '前往下一个目的地' in last_activity):
                        prev_hubs = self.dependencies.get(prev_mapped, self.dependencies.get(prev_node, []))
                        if prev_hubs:
                            # 从枢纽城市出发
                            prev_node = prev_hubs[0]

                # 优先用已生成 itinerary 里上一站最后一天的实际住宿地作为出发点
                # 但如果上一站是loop/linear，已经通过node_exit_city设置了正确的hub_city，不能覆盖
                if itinerary and not prev_is_special:
                    last_generated = itinerary[-1]
                    last_stay = last_generated.get('stay', '')
                    if last_stay and last_stay != '-' and last_stay != prev_node:
                        prev_node = last_stay
                # 传入原始目的地名（nodes[i-1]），用于查依附关系
                orig_prev = nodes[i-1]
                t = self.get_transport(prev_node, node, orig_c1=orig_prev)
                # 如果有 _total（经枢纽的总时间），优先用它
                if "_total" in t:
                    real_min_t = t["_total"]
                else:
                    train_t, flight_t, drive_t = float(t["train"] or 99), float(t["flight"] or 99), float(t["drive"] or 99)
                    flight_actual = flight_t + 1.0 if flight_t < 99 else 99.0  # 飞机加1h安检

                    # 应用 transport_preference（与 _edge_score 逻辑一致）
                    train_score, flight_score, drive_score = train_t, flight_actual, drive_t
                    if flight_score >= 99.0 and train_score < 99.0 and drive_score < 99.0:
                        pref = self.transport_preference
                        if pref == 'train':
                            drive_score = drive_score * 1.5
                        elif pref == 'drive':
                            train_score = train_score * 1.5

                    real_min_t = min(train_score, flight_score, drive_score)
                
                # 新的”极致压榨白天”熔断逻辑：
                # 只有纯交通时间（不含虚假安检补时）超过 4.0h，才视为需要整天大交通。
                threshold = same_day_max_hours if same_day_max_hours is not None else self.same_day_max_hours
                if real_min_t > threshold and real_min_t != 99.0:
                    if "_detail" in t:
                        desc = f"🚆/✈️ {t['_detail']}"
                    elif "_total" in t:
                        desc = f"🚆/✈️ {prev_node}→{node} 约 {t['_total']}h ({t.get('note', '')})"
                    elif real_min_t == train_score: desc = f"🚆 {prev_node}→{node} 火车约 {t['train'] if t['train'] else '-'}h"
                    elif real_min_t == drive_score: desc = f"🚗 {prev_node}→{node} 自驾约 {t['drive'] if t['drive'] else '-'}h"
                    else:
                        flight_t = t['flight']
                        if flight_t:
                            desc = f"✈️ {prev_node}→{node} 飞机约 {flight_t + 1.0:.2f}h（{flight_t:.2f}h飞行 + 1.0h安检）"
                        else:
                            desc = f"✈️ {prev_node}→{node} 飞机约 -h"

                    itinerary.append({"day": day, "city": f"{prev_node} ➔ {node}", "activity": "【跨城大交通】全天移动及办理入住", "transport": desc, "stay": node})
                    day += 1
                    for p in plays:
                        itinerary.append({"day": day, "city": node, "activity": p["activity"], "transport": p.get("transport", "当地交通"), "stay": p.get("stay", node) if p.get("stay") != "-" else node, "_has_option_transport": "_chosen_option" in p})
                        day += 1
                else:
                    # 短途：白天玩，适时走。
                    if "_detail" in t:
                        desc = f"🚆/✈️ {t['_detail']}"
                    elif "_total" in t:
                        desc = f"🚆/✈️ {prev_node}→{node} 约 {t['_total']}h"
                    elif real_min_t == train_score: desc = f"🚆 {prev_node}→{node} 火车 {t['train'] if t['train'] else '-'}h"
                    elif real_min_t == drive_score: desc = f"🚗 {prev_node}→{node} 自驾 {t['drive'] if t['drive'] else '-'}h"
                    else:
                        flight_t = t['flight']
                        if flight_t:
                            desc = f"✈️ {prev_node}→{node} 飞机 {flight_t + 1.0:.2f}h（{flight_t:.2f}h飞行 + 1.0h安检）"
                        else:
                            desc = f"✈️ {prev_node}→{node} 飞机 -h"
                    note_str = f" ({t['note']})" if t.get('note') and "_detail" not in t else ""
                    if itinerary:
                        itinerary[-1]["activity"] += f" + 适时前往 {node}"
                        itinerary[-1]["transport"] = f"当地 | 跨城:{desc}{note_str}"
                        itinerary[-1]["stay"] = node  # 修正住宿地为目的地
                    for p in plays:
                        itinerary.append({"day": day, "city": node, "activity": p["activity"], "transport": p.get("transport", "当地交通"), "stay": p.get("stay", node) if p.get("stay") != "-" else node, "_has_option_transport": "_chosen_option" in p})
                        day += 1
            # 普通节点：记录实际离开城市（用最后一天的住宿地）
            if itinerary:
                last_stay = itinerary[-1].get('stay', '')
                node_exit_city[i] = last_stay if last_stay and last_stay != '-' else node
        # ... 生成 Markdown 部分省略 ...
        # 添加到达日和离开日
        first_city = nodes[0]
        last_city = nodes[-1]

        # 如果最后一个节点是环线，用它的实际离开城市作为 last_city
        last_idx = len(nodes) - 1
        actual_last_city = node_exit_city.get(last_idx, last_city)
        # 如果第一个节点是环线，用它的 hub_city 作为到达城市
        first_dest_data = self.dest_db.get(self.mapping.get(first_city, first_city)) or self.dest_db.get(first_city)
        actual_first_city = (first_dest_data.get('hub_city') or first_city) if (first_dest_data and first_dest_data.get('loop_type')) else first_city
        
        # 从 hub_cities.json 动态加载主要枢纽（数据驱动，基于航班频率统计）
        # 先加载根目录，再用各区域的补充（区域优先）
        hub_cfg = load_json(os.path.join(self.base_dir, "config/hub_cities.json"))
        MAJOR_HUBS = set(hub_cfg.get("hubs", {}).keys()) if hub_cfg else set()
        for r in ["Europe", "North_America", "Oceania", "Asia"]:
            region_hub_cfg = load_json(os.path.join(self.base_dir, "data", r, "config/hub_cities.json"))
            if region_hub_cfg and "hubs" in region_hub_cfg:
                MAJOR_HUBS.update(region_hub_cfg["hubs"].keys())

        def pick_hub(city, hubs):
            """从候选枢纽中优先选主要国际枢纽，没有则退回第一个"""
            # 城市本身就是主要枢纽
            if city in MAJOR_HUBS:
                return city
            # 从依附枢纽中找主要枢纽
            for h in hubs:
                if h in MAJOR_HUBS:
                    return h
            # 没有主要枢纽，退回第一个依附枢纽
            return hubs[0] if hubs else city

        # 查第一个城市的枢纽（到达）
        first_mapped = self.mapping.get(actual_first_city, actual_first_city)
        first_hubs = self.dependencies.get(first_mapped, self.dependencies.get(actual_first_city, []))
        arrival_hub = pick_hub(first_mapped, first_hubs)

        # 查最后一个城市的枢纽（离开）
        last_mapped = self.mapping.get(actual_last_city, actual_last_city)
        last_hubs = self.dependencies.get(last_mapped, self.dependencies.get(actual_last_city, []))

        if self.force_gateway_departure:
            # 强制从门户城市离开：如果最后一站不是门户，找最近的门户
            if last_mapped in MAJOR_HUBS:
                departure_hub = last_mapped
            else:
                # 优先从依附关系中找门户
                gateway_in_hubs = [h for h in last_hubs if h in MAJOR_HUBS]
                if gateway_in_hubs:
                    departure_hub = gateway_in_hubs[0]
                else:
                    # 从所有门户中找最近的（通过坐标距离）
                    if last_mapped in self.coords:
                        last_coord = self.coords[last_mapped]
                        min_dist = float('inf')
                        nearest_hub = last_mapped
                        for hub in MAJOR_HUBS:
                            if hub in self.coords:
                                hub_coord = self.coords[hub]
                                # 坐标格式：[lat, lng]
                                dist = ((last_coord[0] - hub_coord[0])**2 +
                                       (last_coord[1] - hub_coord[1])**2)**0.5
                                if dist < min_dist:
                                    min_dist = dist
                                    nearest_hub = hub
                        departure_hub = nearest_hub
                    else:
                        # 找不到坐标，回退到第一个依附枢纽或自身
                        departure_hub = last_hubs[0] if last_hubs else last_mapped
        else:
            # 默认行为：优先使用pick_hub逻辑
            departure_hub = pick_hub(last_mapped, last_hubs)
        
        # 插入 Day 0
        arrival_item = {
            'day': 0,
            'activity': f'【到达日】飞抵{arrival_hub}，前往{actual_first_city}',
            'transport': '✈️ 国际航班',
            'stay': actual_first_city
        }
        itinerary.insert(0, arrival_item)

        # 追加离开日 - 从最后一天的实际住宿地出发
        last_stay = itinerary[-1]['stay'] if itinerary else actual_last_city
        # 如果最后住宿地就是离境城市，不写"前往X"
        if last_stay == departure_hub:
            departure_activity = f'【离开日】从{last_stay}飞离'
        else:
            departure_activity = f'【离开日】从{last_stay}前往{departure_hub}，飞离'

        departure_item = {
            'day': len(itinerary),
            'activity': departure_activity,
            'transport': '✈️ 国际航班',
            'stay': '-'
        }
        itinerary.append(departure_item)
        
        # 重新编号
        for i, item in enumerate(itinerary):
            item['day'] = i

        out = f"# {name}\n\n"
        uncertain_legs = [item for item in itinerary if item.get('_uncertain')]
        if uncertain_legs:
            out += "> ⚠️ 以下行程含低频航班（1-4班/天），给出两种方案：\n"
            out += "> - **方案A（乐观）**：假设有晚班，当天游玩后晚上出发\n"
            out += "> - **方案B（保守）**：假设只有白天班，当天行程被拆分\n\n"

        out += "| 天数 | 行程安排 | 交通及耗时预估 | 住宿 |\n|:---:|:---|:---|:---:|\n"
        for item in itinerary:
            transport_str = item['transport']
            if item.get('_uncertain'):
                transport_str += " ⚠️(低频,建议提前查时刻)"
            out += f"| Day {item['day']} | {item['activity']} | {transport_str} | {item['stay']} |\n"
        
        # 保存为 MD 和 CSV
        safe_name = name.replace("/", "-").replace(" ", "_")
        # 自动检测区域（根据第一个城市），config 传入则直接用
        if not region:
            first_city = nodes[0] if nodes else None
            if first_city:
                detected_region = self.get_region_for_city(first_city)
                region = detected_region if detected_region else "Europe"  # 默认Europe
                # DEBUG: 显示区域检测结果
            else:
                region = "Europe"  # 默认

        # 确保generated_routes目录存在
        guide_dir = os.path.join(self.base_dir, "data", region, "generated_routes")
        os.makedirs(guide_dir, exist_ok=True)
        
        md_path = os.path.join(guide_dir, f"{safe_name}.md")
        csv_path = os.path.join(guide_dir, f"{safe_name}.csv")
        
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write(out)
        
        import csv
        with open(csv_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=['day', 'activity', 'transport', 'stay'])
            writer.writeheader()
            for item in itinerary:
                writer.writerow({
                    'day': item['day'],
                    'activity': item['activity'],
                    'transport': item['transport'],
                    'stay': item['stay']
                })
        
        out += f"\n✅ 已保存到:\n- {md_path}\n- {csv_path}\n"
        # 返回Markdown和优化后的城市列表
        return {
            'markdown': out,
            'optimized_nodes': nodes,  # 优化后的城市顺序
            'md_path': md_path,
            'csv_path': csv_path
        }

if __name__ == "__main__":
    import sys
    # 自动检测base_dir：项目根目录（src的上上层）
    script_dir = os.path.dirname(os.path.abspath(__file__))
    base_dir = os.path.dirname(os.path.dirname(script_dir))  # 从 src/core/ 到项目根
    if not os.path.exists(os.path.join(base_dir, "data", "Europe")):
        # fallback到~/Downloads/travel_guide
        base_dir = os.path.expanduser("~/Downloads/travel_guide")
    engine = TravelEngine(base_dir)
    cfg = load_config(base_dir)

    # 支持命令行传入目的地：python route_planner_final.py 城市A 城市B ...
    # 或者用 + 连接：python route_planner_final.py "城市A+城市B+城市C"
    if len(sys.argv) > 1:
        # 如果第一个参数包含 +，则按 + 分隔
        if '+' in sys.argv[1]:
            nodes = [c.strip() for c in sys.argv[1].split('+')]
        else:
            nodes = sys.argv[1:]
        name = " + ".join(nodes)
    elif cfg.get("destinations"):
        nodes = cfg["destinations"]
        name = cfg.get("trip_name") or " + ".join(nodes)
    else:
        print("请在 config.json 中配置 destinations，或通过命令行传入城市名")
        print("示例: python route_planner_final.py 巴黎 阿姆斯特丹 布鲁塞尔")
        sys.exit(1)

    start_city  = cfg.get("start_city") or None
    end_city    = cfg.get("end_city") or None
    force_order = cfg.get("force_order", False)
    region      = cfg.get("region") or None

    # ── 加载所有区域的国际门户城市 ────────────────────────────────
    hub_cfg = load_json(os.path.join(base_dir, "config/hub_cities.json"))
    MAJOR_HUBS = set(hub_cfg.get("hubs", {}).keys()) if hub_cfg else set()
    for r in ["Europe", "North_America", "Oceania", "Asia"]:
        region_hub_cfg = load_json(os.path.join(base_dir, "data", r, "config/hub_cities.json"))
        if region_hub_cfg and "hubs" in region_hub_cfg:
            MAJOR_HUBS.update(region_hub_cfg["hubs"].keys())

    # ── 智能起终点选择（大城市原则 + 最短交通时间）─────────────────
    def calculate_total_travel_time(city, other_cities):
        """计算从city到其他所有城市的总交通时间（小时）"""
        total = 0
        for other in other_cities:
            if other == city:
                continue
            route = engine._lookup_edge(city, other)
            if route:
                # 优先飞机 > 火车 > 自驾
                if route.get('flight_time_hours'):
                    total += route['flight_time_hours']
                elif route.get('train_time_hours'):
                    total += route['train_time_hours']
                elif route.get('drive_time_hours'):
                    total += route['drive_time_hours']
                else:
                    total += 999  # 没有交通数据，惩罚值
            else:
                total += 999  # 查不到路线，惩罚值
        return total

    # 智能选择起点
    if not start_city and nodes:
        # 候选：destinations中的国际门户城市
        hub_candidates = [n for n in nodes if n in MAJOR_HUBS]
        if hub_candidates:
            # 如果只有一个门户，直接用
            if len(hub_candidates) == 1:
                start_city = hub_candidates[0]
            else:
                # 多个门户，选总交通时间最短的
                min_time = float('inf')
                for candidate in hub_candidates:
                    time = calculate_total_travel_time(candidate, nodes)
                    if time < min_time:
                        min_time = time
                        start_city = candidate
            print(f"✓ 智能选择起点：{start_city}（国际门户城市，总交通时间最优）")
        else:
            # 没有门户城市，选第一个
            start_city = nodes[0]
            print(f"ℹ️  起点：{start_city}（默认第一个城市）")

    # 智能选择终点
    if not end_city and nodes:
        # 候选：destinations中的国际门户城市（排除起点）
        hub_candidates = [n for n in nodes if n in MAJOR_HUBS and n != start_city]
        if hub_candidates:
            if len(hub_candidates) == 1:
                end_city = hub_candidates[0]
            else:
                # 多个门户，选总交通时间最短的
                min_time = float('inf')
                for candidate in hub_candidates:
                    time = calculate_total_travel_time(candidate, nodes)
                    if time < min_time:
                        min_time = time
                        end_city = candidate
            print(f"✓ 智能选择终点：{end_city}（国际门户城市，总交通时间最优）")
        else:
            # 没有其他门户城市
            if cfg.get('force_gateway_departure', False):
                # 如果强制从门户离开，不固定终点，让路线自由优化
                # （最终会在plan方法中处理返回起点门户）
                end_city = None
                print(f"ℹ️  终点：自动优化（最终从{start_city}飞离）")
            else:
                # 否则选最后一个（排除起点）
                end_city = nodes[-1] if nodes[-1] != start_city else (nodes[-2] if len(nodes) > 1 else None)
                if end_city:
                    print(f"ℹ️  终点：{end_city}（默认最后一个城市）")

    # ── 起终点城市国际直飞校验 ─────────────────────────────────────
    def check_gateway(city, role):
        if not city or not MAJOR_HUBS:
            return
        if city in MAJOR_HUBS:
            return  # 国际枢纽，有直飞
        # 不在枢纽列表，提示可能无直飞
        print(f"⚠️  {role}城市「{city}」可能无中国直飞航班")
        # 提示最近的国际枢纽（从 dependencies 查枢纽）
        mapped = engine.mapping.get(city, city)
        hubs = engine.dependencies.get(mapped, engine.dependencies.get(city, []))
        hub_suggestions = [h for h in hubs if h in MAJOR_HUBS]
        if hub_suggestions:
            print(f"   建议从以下城市出发/结束：{' 或 '.join(hub_suggestions)}")

    check_gateway(start_city or (nodes[0] if nodes else None), "出发")
    check_gateway(end_city or (nodes[-1] if nodes else None), "结束")
    # ── 校验结束 ──────────────────────────────────────────────────

    print(engine.plan(name, nodes,
                      start_node=start_city,
                      end_node=end_city,
                      force_order=force_order,
                      region=region))

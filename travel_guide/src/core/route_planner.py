import json
import os
import itertools
import math
import re
import csv

from src.core.utils import load_json, load_config, REGIONS
from src.core.route_validator import validate_route

# ============================================================
# 联网查航班时刻开关
CHECK_LOW_FREQ_FLIGHTS = False
# ============================================================


def check_evening_flight(from_city_en, to_city_en):
    """联网查是否有18:00后的航班"""
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


class TravelEngine:
    def __init__(self, base_dir, same_day_max_hours=None):
        self.base_dir = base_dir
        cfg = load_config(base_dir)
        self.same_day_max_hours = same_day_max_hours if same_day_max_hours is not None else cfg["same_day_max_hours"]
        self.options_display_mode = cfg["options_display_mode"]
        self.force_gateway_departure = cfg["force_gateway_departure"]
        self.transport_preference = cfg["transport_preference"]

        global CHECK_LOW_FREQ_FLIGHTS
        CHECK_LOW_FREQ_FLIGHTS = cfg["check_low_freq_flights"]

        # 加载坐标
        self.coords = load_json(os.path.join(base_dir, "city_coordinates.json"))
        for region in REGIONS:
            self.coords.update(load_json(os.path.join(base_dir, "data", region, "city_coordinates.json")))

        # 城市→区域映射
        self.city_to_region = load_json(os.path.join(base_dir, "config/city_to_region.json"))

        # 城市别名映射
        self.mapping = load_json(os.path.join(base_dir, "city_mapping.json"))
        for region in REGIONS:
            self.mapping.update(load_json(os.path.join(base_dir, "data", region, "city_mapping.json")))

        # 交通数据库
        self.trans_db = {}
        for region in REGIONS:
            for fname in ["transport_routes.json", "transport_preset.json"]:
                p = os.path.join(base_dir, "data", region, fname)
                if os.path.exists(p):
                    self._load_transport_file(p)
                    break  # transport_routes 优先

        # 依附关系
        self.dependencies = {}
        for region in REGIONS:
            dep_p = os.path.join(base_dir, "data", region, "city_dependencies.json")
            if os.path.exists(dep_p):
                data = load_json(dep_p)
                if "依附关系" in data:
                    self.dependencies.update(data["依附关系"])

        # 目的地数据库
        self.dest_db = {}
        for root, _, files in os.walk(base_dir):
            if '备份' in root or '_backup' in root.lower():
                continue
            for file in files:
                if file.endswith("_destinations.json"):
                    self.dest_db.update(load_json(os.path.join(root, file)))

    def _load_transport_file(self, path):
        """加载交通数据文件到 trans_db"""
        data = load_json(path)
        for k, v in data.items():
            if "->" in k or "→" in k:
                self.trans_db[k] = v
            elif isinstance(v, dict):
                for sub_k, sub_v in v.items():
                    if "->" in sub_k or "→" in sub_k:
                        self.trans_db[sub_k] = sub_v

    # ==================== 交通查询 ====================

    def _lookup_edge(self, c1, c2):
        for k in [f"{c1}->{c2}", f"{c2}->{c1}", f"{c1}→{c2}", f"{c2}→{c1}"]:
            if k in self.trans_db:
                return self.trans_db[k]
        return None

    def _edge_min_time(self, edge):
        """取最优交通时间（飞机含1h安检）"""
        train = edge.get("train_time_hours")
        drive = edge.get("drive_time_hours")
        flight = edge.get("flight_time_hours")
        if flight:
            times = [flight + 1.0]
            if train: times.append(train)
            if drive: times.append(drive)
            return min(times)
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
        """综合评分：时间越短越好，高频航班加分"""
        if not edge:
            return 99.0
        flight_t = edge.get("flight_time_hours")
        train_t = edge.get("train_time_hours")
        drive_t = edge.get("drive_time_hours")
        freq = edge.get("flight_frequency_per_day") or 0

        if flight_t:
            flight_t_total = flight_t + 1.0
            if freq >= 10:
                flight_score = flight_t_total * 0.3
            elif freq >= 5:
                flight_score = flight_t_total * 0.5
            elif 1 <= freq <= 4:
                if CHECK_LOW_FREQ_FLIGHTS and from_en and to_en:
                    has_evening = check_evening_flight(from_en, to_en)
                    if has_evening is True:
                        flight_score = flight_t_total * 0.6
                        edge['_has_evening'] = True
                    elif has_evening is False:
                        flight_score = flight_t_total * 1.0
                        edge['_has_evening'] = False
                    else:
                        edge['_uncertain'] = True
                        flight_score = flight_t_total * 0.8
                else:
                    edge['_uncertain'] = True
                    flight_score = flight_t_total * 0.8
            else:
                flight_score = flight_t_total * 1.2
        else:
            flight_score = 99.0

        train_score = train_t if train_t else 99.0
        drive_score = drive_t if drive_t else 99.0

        if flight_score >= 99.0 and train_score < 99.0 and drive_score < 99.0:
            pref = getattr(self, 'transport_preference', 'train')
            if pref == 'train':
                drive_score *= 1.5
            elif pref == 'drive':
                train_score *= 1.5

        return min(flight_score, train_score, drive_score)

    # ==================== 交通描述格式化（消除重复） ====================

    def _format_leg_desc(self, edge, min_time):
        """格式化单段交通描述，返回如 '2.50h火车' 或 '3.00h飞机（2.00h飞行 + 1.0h安检）'"""
        if not edge:
            return f"{min_time:.2f}h"

        train_t = edge.get("train_time_hours")
        drive_t = edge.get("drive_time_hours")
        flight_t = edge.get("flight_time_hours")
        flight_actual = (flight_t + 1.0) if flight_t else None

        # 判断实际用了什么交通方式
        if flight_actual and abs(min_time - flight_actual) < 0.01:
            return f"{flight_actual:.2f}h飞机（{flight_t:.2f}h飞行 + 1.0h安检）"
        elif train_t and abs(min_time - train_t) < 0.01:
            return f"{min_time:.2f}h火车"
        elif drive_t and abs(min_time - drive_t) < 0.01:
            return f"{min_time:.2f}h自驾"
        else:
            return f"{min_time:.2f}h"

    def _format_transport_str(self, t, real_min_t, from_city, to_city, prefix=""):
        """
        统一生成交通描述字符串。
        t: get_transport() 返回的字典
        real_min_t: 实际最短时间
        from_city, to_city: 起终点名
        prefix: 前缀（如 "跨城:" 或空）
        """
        if "_detail" in t:
            return f"🚆/✈️ {t['_detail']}"
        if "_total" in t:
            route_label = f"{from_city}→{to_city} " if from_city else ""
            note = f" ({t.get('note', '')})" if t.get('note') else ""
            return f"🚆/✈️ {route_label}约 {t['_total']}h{note}"

        train_t = float(t["train"] or 99)
        drive_t = float(t["drive"] or 99)
        flight_t = float(t["flight"] or 99)
        flight_actual = flight_t + 1.0 if flight_t < 99 else 99.0

        # 判断实际用了哪种
        route_label = f"{from_city}→{to_city} " if from_city else ""

        if real_min_t >= 99.0:
            return f"🚆 {route_label}-h"
        elif abs(real_min_t - train_t) < 0.01 or (train_t < 99 and real_min_t <= train_t * 1.01):
            return f"🚆 {route_label}火车约 {t['train']}h" if t['train'] else f"🚆 {route_label}火车 -h"
        elif abs(real_min_t - drive_t) < 0.01 or (drive_t < 99 and real_min_t <= drive_t * 1.01):
            return f"🚗 {route_label}自驾约 {t['drive']}h" if t['drive'] else f"🚗 {route_label}自驾 -h"
        elif flight_t < 99:
            return f"✈️ {route_label}飞机约 {flight_actual:.2f}h（{flight_t:.2f}h飞行 + 1.0h安检）"
        else:
            return f"🚆 {route_label}-h"

    def _format_transport_str_short(self, t, real_min_t, from_city, to_city):
        """短途版本（不带"约"字）"""
        if "_detail" in t:
            return f"🚆/✈️ {t['_detail']}"
        if "_total" in t:
            return f"🚆/✈️ {from_city}→{to_city} 约 {t['_total']}h"

        train_t = float(t["train"] or 99)
        drive_t = float(t["drive"] or 99)
        flight_t = float(t["flight"] or 99)
        flight_actual = flight_t + 1.0 if flight_t < 99 else 99.0

        route_label = f"{from_city}→{to_city} "
        if abs(real_min_t - train_t) < 0.01 or (train_t < 99 and real_min_t <= train_t * 1.01):
            return f"🚆 {route_label}火车 {t['train']}h" if t['train'] else f"🚆 {route_label}火车 -h"
        elif abs(real_min_t - drive_t) < 0.01 or (drive_t < 99 and real_min_t <= drive_t * 1.01):
            return f"🚗 {route_label}自驾 {t['drive']}h" if t['drive'] else f"🚗 {route_label}自驾 -h"
        elif flight_t < 99:
            return f"✈️ {route_label}飞机 {flight_actual:.2f}h（{flight_t:.2f}h飞行 + 1.0h安检）"
        else:
            return f"🚆 {route_label}-h"

    # ==================== get_transport ====================

    def get_transport(self, raw_c1, raw_c2, orig_c1=None):
        """查交通方式，支持直达、枢纽中转、智能中转"""
        c1 = self.mapping.get(raw_c1, raw_c1)
        c2 = self.mapping.get(raw_c2, raw_c2)

        # 1. 直达
        edge = self._lookup_edge(c1, c2)
        direct_result = None
        direct_min_t = 99.0
        if edge:
            direct_min_t = self._edge_min_time(edge)
            direct_result = {"train": edge.get("train_time_hours"),
                             "drive": edge.get("drive_time_hours"),
                             "flight": edge.get("flight_time_hours"),
                             "note": edge.get("note", "")}
            if direct_min_t <= self.same_day_max_hours:
                return direct_result

        hubs2 = self.dependencies.get(raw_c2, self.dependencies.get(c2, []))
        hubs1 = (self.dependencies.get(c1, []) or self.dependencies.get(raw_c1, []) or
                 (self.dependencies.get(orig_c1, []) if orig_c1 else []))

        # 2. c1 直达 c2 的枢纽
        result = self._try_hub_transit_to_dest(c1, raw_c1, c2, raw_c2, hubs2)
        if result:
            if direct_result and direct_min_t <= (result.get("_total") or 99):
                return direct_result
            return result

        # 3. c1 的枢纽到 c2
        result = self._try_hub_transit_from_src(c1, raw_c1, c2, raw_c2, hubs1, orig_c1)
        if result:
            if direct_result and direct_min_t <= (result.get("_total") or 99):
                return direct_result
            return result

        # 4. 双枢纽中转
        result = self._try_double_hub_transit(c1, raw_c1, c2, raw_c2, hubs1, hubs2)
        if result:
            if direct_result and direct_min_t <= (result.get("_total") or 99):
                return direct_result
            return result

        # 5. 智能中转
        result = self._try_smart_transit(c1, raw_c1, c2, raw_c2, hubs2)
        if result:
            if direct_result and direct_min_t <= (result.get("_total") or 99):
                return direct_result
            return result

        if direct_result:
            return direct_result
        return {"train": None, "drive": None, "flight": None, "note": ""}

    def _build_multi_leg_result(self, legs, raw_c1, raw_c2):
        """
        构建多段中转结果。
        legs: [(edge_or_None, from_city, to_city), ...]
        """
        total = 0
        detail_parts = []
        via_cities = []

        for edge, fc, tc in legs:
            t = self._edge_min_time(edge) if edge else 0
            total += t
            desc = self._format_leg_desc(edge, t)
            detail_parts.append(f"{fc}→{tc}({desc})")
            if fc != raw_c1 and fc not in via_cities:
                via_cities.append(fc)
            if tc != raw_c2 and tc not in via_cities:
                via_cities.append(tc)

        detail = " → ".join(detail_parts)
        note = f"经{'→'.join(via_cities)}" if via_cities else ""

        return {"train": None, "drive": None, "flight": None,
                "_total": round(total, 2), "_detail": detail, "note": note}

    def _try_hub_transit_to_dest(self, c1, raw_c1, c2, raw_c2, hubs2):
        """c1 直达 c2 的枢纽城市"""
        if not hubs2:
            return None

        best_total, best_result = 99.0, None
        for hub in hubs2:
            e1 = self._lookup_edge(c1, hub) or self._lookup_edge(raw_c1, hub)
            if not e1:
                continue
            t1 = self._edge_min_time(e1)
            e2 = self._lookup_edge(hub, c2) or self._lookup_edge(hub, raw_c2)
            t2 = self._edge_min_time(e2) if e2 else 0
            total = t1 + t2
            if total < best_total:
                best_total = total
                if e2:
                    best_result = self._build_multi_leg_result(
                        [(e1, raw_c1, hub), (e2, hub, raw_c2)], raw_c1, raw_c2)
                else:
                    best_result = {"train": e1.get("train_time_hours"),
                                   "drive": e1.get("drive_time_hours"),
                                   "flight": e1.get("flight_time_hours"),
                                   "note": f"到{hub}"}
        return best_result

    def _try_hub_transit_from_src(self, c1, raw_c1, c2, raw_c2, hubs1, orig_c1):
        """c1 的枢纽到 c2"""
        if not hubs1:
            return None

        best_score, best_total = 99.0, 99.0
        best_leg1, best_leg2, best_hub = None, None, None

        for hub in hubs1:
            e1 = self._lookup_edge(c1, hub) or self._lookup_edge(raw_c1, hub)
            e2 = self._lookup_edge(hub, c2)
            if e2:
                t1 = self._edge_min_time(e1) if e1 else 0
                s2 = self._edge_score(e2)
                score = t1 + s2
                total = t1 + self._edge_min_time(e2)
                if score < best_score:
                    best_score, best_total = score, total
                    best_hub, best_leg1, best_leg2 = hub, e1, e2

        if best_leg2:
            return self._build_multi_leg_result(
                [(best_leg1, raw_c1, best_hub), (best_leg2, best_hub, raw_c2)],
                raw_c1, raw_c2)
        return None

    def _try_double_hub_transit(self, c1, raw_c1, c2, raw_c2, hubs1, hubs2):
        """双枢纽中转：A的枢纽→B的枢纽"""
        if not hubs1 or not hubs2:
            return None

        best_score, best_h1, best_h2 = 99.0, None, None
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
                    if score < best_score:
                        best_score, best_h1, best_h2 = score, h1, h2

        if best_h1:
            e1 = self._lookup_edge(c1, best_h1) or self._lookup_edge(raw_c1, best_h1)
            e_mid = self._lookup_edge(best_h1, best_h2)
            e2 = self._lookup_edge(best_h2, c2)
            return self._build_multi_leg_result(
                [(e1, raw_c1, best_h1), (e_mid, best_h1, best_h2), (e2, best_h2, raw_c2)],
                raw_c1, raw_c2)
        return None

    def _try_smart_transit(self, c1, raw_c1, c2, raw_c2, hubs2):
        """智能中转：遍历所有可能的中转城市"""
        all_cities = set()
        for route_key in self.trans_db.keys():
            sep = "->" if "->" in route_key else ("→" if "→" in route_key else None)
            if sep:
                parts = route_key.split(sep)
                if len(parts) == 2:
                    all_cities.add(parts[0].strip())
                    all_cities.add(parts[1].strip())

        target_cities = list(set((hubs2 or []) + [c2]))
        best_score, best_transit, best_target = 99.0, None, None
        best_e1, best_e2, best_e_last = None, None, None

        for transit in all_cities:
            if transit in (c1, c2, raw_c1, raw_c2):
                continue
            e1 = self._lookup_edge(c1, transit) or self._lookup_edge(raw_c1, transit)
            if not e1:
                continue
            for target in target_cities:
                if transit == target:
                    continue
                e2 = self._lookup_edge(transit, target)
                if not e2:
                    continue
                s1 = self._edge_score(e1)
                s2 = self._edge_score(e2)
                score = s1 + s2
                total = self._edge_min_time(e1) + self._edge_min_time(e2)

                e_last = None
                if target != c2 and target != raw_c2:
                    if target in (hubs2 or []):
                        pass  # 到达枢纽即到达
                    else:
                        e_last = self._lookup_edge(target, c2) or self._lookup_edge(target, raw_c2)
                        if e_last:
                            score += self._edge_score(e_last)
                            total += self._edge_min_time(e_last)
                        else:
                            continue

                if score < best_score:
                    best_score = score
                    best_transit, best_target = transit, target
                    best_e1, best_e2, best_e_last = e1, e2, e_last

        if best_transit:
            legs = [(best_e1, raw_c1, best_transit), (best_e2, best_transit, raw_c2 if best_target in (c2, raw_c2) else best_target)]
            if best_e_last:
                legs.append((best_e_last, best_target, raw_c2))
            return self._build_multi_leg_result(legs, raw_c1, raw_c2)
        return None

    # ==================== 公共工具方法 ====================

    def haversine(self, coord1, coord2):
        R = 6371
        lat1, lon1 = math.radians(coord1[0]), math.radians(coord1[1])
        lat2, lon2 = math.radians(coord2[0]), math.radians(coord2[1])
        a = math.sin((lat2-lat1)/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin((math.radians(coord2[1]-coord1[1]))/2)**2
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

    def get_region_for_city(self, city_name):
        if city_name in self.city_to_region:
            return self.city_to_region[city_name]
        mapped_name = self.mapping.get(city_name, city_name)
        if mapped_name in self.city_to_region:
            return self.city_to_region[mapped_name]
        for region in REGIONS:
            if city_name in self.dest_db or mapped_name in self.dest_db:
                region_path = os.path.join(self.base_dir, "data", region, "guides")
                if os.path.exists(region_path):
                    return region
        return None

    def get_best_cost(self, c1, c2):
        t = self.get_transport(c1, c2)
        if "_total" in t and t["_total"] is not None:
            return float(t["_total"])

        train_t = float(t["train"] or 99)
        drive_t = float(t["drive"] or 99)
        flight_t = float(t["flight"] or 99)
        flight_actual = flight_t + 1.0 if flight_t < 99 else 99.0

        train_score, flight_score, drive_score = train_t, flight_actual, drive_t
        if flight_score >= 99.0 and train_score < 99.0 and drive_score < 99.0:
            pref = self.transport_preference
            if pref == 'train':
                drive_score *= 1.5
            elif pref == 'drive':
                train_score *= 1.5

        return min(train_score, drive_score, flight_score)

    def detect_backtrack(self, route):
        if len(route) < 3:
            return 0
        count = 0
        for i in range(len(route) - 2):
            d_ab = self.get_best_cost(route[i], route[i+1])
            d_bc = self.get_best_cost(route[i+1], route[i+2])
            d_ac = self.get_best_cost(route[i], route[i+2])
            if d_ab + d_bc > d_ac * 1.3:
                count += 1
        return count

    def optimize_order_no_backtrack(self, raw_nodes, start_node=None, end_node=None):
        if len(raw_nodes) <= 2:
            return raw_nodes

        if start_node and end_node:
            middle = [n for n in raw_nodes if n != start_node and n != end_node]
            if not middle:
                return [start_node, end_node]
            best_route, best_score = None, float('inf')
            for perm in itertools.permutations(middle):
                route = [start_node] + list(perm) + [end_node]
                total_cost = sum(self.get_best_cost(route[i], route[i+1]) for i in range(len(route)-1))
                backtrack_count = self.detect_backtrack(route)
                score = backtrack_count * 50 + total_cost
                if score < best_score:
                    best_score, best_route = score, route
            return best_route
        else:
            best_route, best_score = None, float('inf')
            for perm in itertools.permutations(raw_nodes):
                route = list(perm)
                total_cost = sum(self.get_best_cost(route[i], route[i+1]) for i in range(len(route)-1))
                backtrack_count = self.detect_backtrack(route)
                score = backtrack_count * 50 + total_cost
                if score < best_score:
                    best_score, best_route = score, route
            return best_route if best_route else raw_nodes

    # ==================== 计算跨城交通时间 ====================

    def _calc_real_min_time(self, t, same_day_max_hours):
        """从 get_transport 结果中计算实际最短时间（应用偏好权重）"""
        if "_total" in t:
            return t["_total"]

        train_t = float(t["train"] or 99)
        drive_t = float(t["drive"] or 99)
        flight_t = float(t["flight"] or 99)
        flight_actual = flight_t + 1.0 if flight_t < 99 else 99.0

        train_score, flight_score, drive_score = train_t, flight_actual, drive_t
        if flight_score >= 99.0 and train_score < 99.0 and drive_score < 99.0:
            pref = self.transport_preference
            if pref == 'train':
                drive_score *= 1.5
            elif pref == 'drive':
                train_score *= 1.5

        return min(train_score, flight_score, drive_score)

    # ==================== plan() 主方法 ====================

    def plan(self, name, raw_nodes, start_node=None, end_node=None,
             force_order=False, same_day_max_hours=None, region=None):

        threshold = same_day_max_hours if same_day_max_hours is not None else self.same_day_max_hours

        # 1. 优化城市顺序
        nodes = self._optimize_node_order(raw_nodes, start_node, end_node, force_order)

        # 2. 构建逐日行程
        itinerary, node_exit_city = self._build_itinerary(nodes, threshold)

        # 3. 添加到达日和离开日
        self._add_arrival_departure(itinerary, nodes, node_exit_city, threshold)

        # 4. 重新编号
        for i, item in enumerate(itinerary):
            item['day'] = i

        # 5. 输出 MD + CSV
        return self._save_output(name, nodes, itinerary, region)

    def _optimize_node_order(self, raw_nodes, start_node, end_node, force_order):
        """检测环线节点，决定是否优化顺序"""
        has_special = False
        for node in raw_nodes:
            mapped = self.mapping.get(node, node)
            dest_data = self.dest_db.get(mapped) or self.dest_db.get(node)
            if dest_data and dest_data.get('loop_type') in ['loop', 'linear']:
                has_special = True
                break

        if force_order or has_special:
            return raw_nodes
        return self.optimize_order_no_backtrack(raw_nodes, start_node, end_node)

    def _resolve_dest_data(self, node):
        """查找节点对应的目的地数据"""
        mapped = self.mapping.get(node, node)

        def normalize_quotes(s):
            result, count = [], 0
            for ch in s:
                if ch == '"':
                    result.append('\u201c' if count % 2 == 0 else '\u201d')
                    count += 1
                else:
                    result.append(ch)
            return ''.join(result)

        norm_node = normalize_quotes(node)
        norm_mapped = normalize_quotes(mapped)
        dest_data = (self.dest_db.get(mapped) or self.dest_db.get(node)
                     or self.dest_db.get(norm_mapped) or self.dest_db.get(norm_node))
        if not dest_data:
            for k, v in self.dest_db.items():
                if node in k or mapped in k or norm_node in k:
                    dest_data = v
                    break
        return dest_data

    def _build_itinerary(self, nodes, threshold):
        """构建完整的逐日行程"""
        itinerary, day = [], 1
        node_exit_city = {}
        visited_cities = set()

        for i, node in enumerate(nodes):
            dest_data = self._resolve_dest_data(node)
            mapped_node = self.mapping.get(node, node)
            loop_type = dest_data.get('loop_type') if dest_data else None
            hub_city = dest_data.get('hub_city') if dest_data else None

            if loop_type and hub_city:
                day = self._build_loop_node(itinerary, nodes, i, node, dest_data, day, threshold, node_exit_city)
                end_city = dest_data.get('end_city')
                node_exit_city[i] = hub_city if loop_type == 'loop' else (end_city or hub_city)
                continue

            city_key = mapped_node or node
            if city_key in visited_cities:
                node_exit_city[i] = city_key
                continue
            visited_cities.add(city_key)

            plays = self._resolve_plays(dest_data, node, nodes, i, threshold)

            if i == 0:
                for p in plays:
                    itinerary.append({"day": day, "city": node, "activity": p["activity"],
                                      "transport": p.get("transport", "当地交通"),
                                      "stay": p.get("stay", node) if p.get("stay") != "-" else node,
                                      "_has_option_transport": "_chosen_option" in p})
                    day += 1
            else:
                day = self._build_normal_node(itinerary, nodes, i, node, plays, day, threshold, node_exit_city)

            if itinerary:
                last_stay = itinerary[-1].get('stay', '')
                node_exit_city[i] = last_stay if last_stay and last_stay != '-' else node

        return itinerary, node_exit_city

    def _build_loop_node(self, itinerary, nodes, i, node, dest_data, day, threshold, node_exit_city):
        """处理环线节点"""
        hub_city = dest_data['hub_city']

        # 从上一站到 hub_city 的交通
        if i > 0:
            from_city = node_exit_city.get(i-1, nodes[i-1])
            if from_city != hub_city:
                t = self.get_transport(from_city, hub_city, orig_c1=nodes[i-1])
                real_min_t = self._calc_real_min_time(t, threshold)

                if real_min_t >= threshold and real_min_t != 99.0:
                    desc = self._format_transport_str(t, real_min_t, from_city, hub_city)
                    itinerary.append({"day": day, "city": f"{from_city} ➔ {hub_city}",
                                      "activity": f"【大交通】前往{hub_city}，开始{node}",
                                      "transport": desc, "stay": hub_city})
                    day += 1
                else:
                    if itinerary:
                        desc = self._format_transport_str_short(t, real_min_t, from_city, hub_city)
                        itinerary[-1]["activity"] += f" + 适时前往 {hub_city}"
                        itinerary[-1]["transport"] = f"当地 | 跨城:{desc}"
                        itinerary[-1]["stay"] = hub_city

        # 展开环线行程
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

        return day

    def _resolve_plays(self, dest_data, node, nodes, i, threshold):
        """处理 options，返回最终的行程列表"""
        raw_plays = dest_data["itinerary"] if dest_data else [{"activity": f"游览{node}核心景点", "stay": node, "transport": "当地交通"}]
        plays = []
        next_node = nodes[i+1] if i+1 < len(nodes) else None
        next_mapped = self.mapping.get(next_node, next_node) if next_node else None

        for p in raw_plays:
            if 'options' not in p:
                plays.append(p)
                continue

            if not next_node:
                plays.append({"activity": p['activity'], "stay": p.get('stay', node),
                              "transport": p.get("transport", "当地交通")})
                continue

            chosen, option_matched = None, False
            all_options_desc = []
            for opt in p['options']:
                drive_str = f"🚗 {opt['drive']}h" if opt.get('drive') else ''
                train_str = f" / 🚆 {opt['train']}h" if opt.get('train') else ''
                all_options_desc.append(f"  • {opt['label']}：{drive_str}{train_str}　{opt.get('detail','')}")
                if any(t in [next_node, next_mapped] for t in opt.get('to', [])):
                    chosen = opt
                    option_matched = True

            if not chosen:
                chosen = p['options'][0]

            drive = chosen.get('drive') or 99
            train = chosen.get('train') or 99

            if self.options_display_mode == "compact":
                travel_h = min(drive, train)
                max_h = threshold
                if travel_h <= max_h:
                    transport_modes = []
                    if drive and drive < 99: transport_modes.append(f"🚗 自驾{drive}h")
                    if train and train < 99: transport_modes.append(f"🚆 火车{train}h")
                    transport_str = " 或 ".join(transport_modes) if transport_modes else "当地交通"
                    activity = p['activity'] + f"，前往{chosen['stay']}（{transport_str}）"
                else:
                    activity = p['activity']
            else:
                options_text = '\n'.join(all_options_desc)
                activity = p['activity'] + '\n【可选路线】\n' + options_text + '\n【本次选择】' + chosen['label']

            new_p = dict(p)
            new_p['activity'] = activity
            new_p['stay'] = chosen['stay']
            transport_modes = []
            if train and train < 99: transport_modes.append(f"🚆 火车约{train}h")
            if drive and drive < 99: transport_modes.append(f"🚗 自驾约{drive}h")
            new_p['transport'] = " 或 ".join(transport_modes) if transport_modes else "当地交通"
            if option_matched:
                new_p['_chosen_option'] = chosen
            plays.append(new_p)

        return plays

    def _build_normal_node(self, itinerary, nodes, i, node, plays, day, threshold, node_exit_city):
        """处理普通节点的跨城交通和行程展开"""
        prev_node = node_exit_city.get(i-1, nodes[i-1])

        # options 已包含交通
        if itinerary and itinerary[-1].get('_has_option_transport') and itinerary[-1].get('stay', '') not in ['', '-']:
            for p in plays:
                itinerary.append({"day": day, "city": node, "activity": p["activity"],
                                  "transport": p.get("transport", "当地交通"),
                                  "stay": p.get("stay", node) if p.get("stay") != "-" else node,
                                  "_has_option_transport": "_chosen_option" in p})
                day += 1
            return day

        # 同城跳过
        if self.mapping.get(prev_node, prev_node) == self.mapping.get(node, node) or prev_node == node:
            for p in plays:
                itinerary.append({"day": day, "city": node, "activity": p["activity"],
                                  "transport": p.get("transport", "当地交通"),
                                  "stay": p.get("stay", node) if p.get("stay") != "-" else node,
                                  "_has_option_transport": "_chosen_option" in p})
                day += 1
            return day

        # 检查上一站是否返回枢纽
        prev_mapped = self.mapping.get(prev_node, prev_node)
        prev_dest_data = self.dest_db.get(prev_mapped) or self.dest_db.get(prev_node)

        prev_original_node = nodes[i-1]
        prev_original_mapped = self.mapping.get(prev_original_node, prev_original_node)
        prev_original_data = self.dest_db.get(prev_original_mapped) or self.dest_db.get(prev_original_node)
        prev_is_special = prev_original_data and prev_original_data.get('loop_type') in ['loop', 'linear']

        if prev_dest_data and 'itinerary' in prev_dest_data:
            last_day = prev_dest_data['itinerary'][-1]
            last_activity = last_day.get('activity', '')
            if '返回' in last_activity or '前往下一个目的地' in last_activity:
                prev_hubs = self.dependencies.get(prev_mapped, self.dependencies.get(prev_node, []))
                if prev_hubs:
                    prev_node = prev_hubs[0]

        if itinerary and not prev_is_special:
            last_stay = itinerary[-1].get('stay', '')
            if last_stay and last_stay != '-' and last_stay != prev_node:
                prev_node = last_stay

        orig_prev = nodes[i-1]
        t = self.get_transport(prev_node, node, orig_c1=orig_prev)
        real_min_t = self._calc_real_min_time(t, threshold)

        if real_min_t > threshold and real_min_t != 99.0:
            desc = self._format_transport_str(t, real_min_t, prev_node, node)
            itinerary.append({"day": day, "city": f"{prev_node} ➔ {node}",
                              "activity": "【跨城大交通】全天移动及办理入住",
                              "transport": desc, "stay": node})
            day += 1
            for p in plays:
                itinerary.append({"day": day, "city": node, "activity": p["activity"],
                                  "transport": p.get("transport", "当地交通"),
                                  "stay": p.get("stay", node) if p.get("stay") != "-" else node,
                                  "_has_option_transport": "_chosen_option" in p})
                day += 1
        else:
            desc = self._format_transport_str_short(t, real_min_t, prev_node, node)
            note_str = f" ({t['note']})" if t.get('note') and "_detail" not in t else ""
            if itinerary:
                itinerary[-1]["activity"] += f" + 适时前往 {node}"
                itinerary[-1]["transport"] = f"当地 | 跨城:{desc}{note_str}"
                itinerary[-1]["stay"] = node
            for p in plays:
                itinerary.append({"day": day, "city": node, "activity": p["activity"],
                                  "transport": p.get("transport", "当地交通"),
                                  "stay": p.get("stay", node) if p.get("stay") != "-" else node,
                                  "_has_option_transport": "_chosen_option" in p})
                day += 1

        return day

    def _add_arrival_departure(self, itinerary, nodes, node_exit_city, threshold):
        """添加到达日（Day 0）和离开日"""
        first_city = nodes[0]
        last_idx = len(nodes) - 1
        actual_last_city = node_exit_city.get(last_idx, nodes[-1])

        # 第一个城市
        first_dest_data = self.dest_db.get(self.mapping.get(first_city, first_city)) or self.dest_db.get(first_city)
        actual_first_city = (first_dest_data.get('hub_city') or first_city) if (first_dest_data and first_dest_data.get('loop_type')) else first_city

        # 加载 hub 城市
        MAJOR_HUBS = self._load_major_hubs()

        def pick_hub(city, hubs):
            if city in MAJOR_HUBS:
                return city
            for h in hubs:
                if h in MAJOR_HUBS:
                    return h
            return hubs[0] if hubs else city

        # 到达 hub
        first_mapped = self.mapping.get(actual_first_city, actual_first_city)
        first_hubs = self.dependencies.get(first_mapped, self.dependencies.get(actual_first_city, []))

        if self.force_gateway_departure:
            if first_mapped in MAJOR_HUBS:
                arrival_hub = first_mapped
            else:
                gateway_in_hubs = [h for h in first_hubs if h in MAJOR_HUBS]
                if gateway_in_hubs:
                    arrival_hub = gateway_in_hubs[0]
                else:
                    # 用自身坐标或deps第一个的坐标找最近hub
                    coord_city = first_mapped if first_mapped in self.coords else (first_hubs[0] if first_hubs else None)
                    if coord_city and coord_city in self.coords:
                        coord = self.coords[coord_city]
                        min_dist, nearest = float('inf'), first_mapped
                        for hub in MAJOR_HUBS:
                            if hub in self.coords:
                                dist = ((coord[0] - self.coords[hub][0])**2 + (coord[1] - self.coords[hub][1])**2)**0.5
                                if dist < min_dist:
                                    min_dist, nearest = dist, hub
                        arrival_hub = nearest
                    else:
                        arrival_hub = first_hubs[0] if first_hubs else first_mapped
        else:
            arrival_hub = pick_hub(first_mapped, first_hubs)

        # 离开 hub
        last_mapped = self.mapping.get(actual_last_city, actual_last_city)
        last_hubs = self.dependencies.get(last_mapped, self.dependencies.get(actual_last_city, []))

        if self.force_gateway_departure:
            if last_mapped in MAJOR_HUBS:
                departure_hub = last_mapped
            else:
                gateway_in_hubs = [h for h in last_hubs if h in MAJOR_HUBS]
                if gateway_in_hubs:
                    departure_hub = gateway_in_hubs[0]
                elif last_mapped in self.coords:
                    last_coord = self.coords[last_mapped]
                    min_dist, nearest = float('inf'), last_mapped
                    for hub in MAJOR_HUBS:
                        if hub in self.coords:
                            dist = ((last_coord[0] - self.coords[hub][0])**2 + (last_coord[1] - self.coords[hub][1])**2)**0.5
                            if dist < min_dist:
                                min_dist, nearest = dist, hub
                    departure_hub = nearest
                else:
                    departure_hub = last_hubs[0] if last_hubs else last_mapped
        else:
            departure_hub = pick_hub(last_mapped, last_hubs)

        # Day 0
        itinerary.insert(0, {
            'day': 0,
            'activity': f'【到达日】飞抵{arrival_hub}，前往{actual_first_city}',
            'transport': '✈️ 国际航班',
            'stay': actual_first_city
        })

        # 离开日
        last_stay = itinerary[-1]['stay'] if itinerary else actual_last_city
        if last_stay == departure_hub:
            departure_activity = f'【离开日】从{last_stay}飞离'
        else:
            departure_activity = f'【离开日】从{last_stay}前往{departure_hub}，飞离'

        itinerary.append({
            'day': len(itinerary),
            'activity': departure_activity,
            'transport': '✈️ 国际航班',
            'stay': '-'
        })

    def _load_major_hubs(self):
        """加载所有区域的主要枢纽城市"""
        hub_cfg = load_json(os.path.join(self.base_dir, "config/hub_cities.json"))
        hubs = set(hub_cfg.get("hubs", {}).keys()) if hub_cfg else set()
        for r in REGIONS:
            region_hub_cfg = load_json(os.path.join(self.base_dir, "data", r, "config/hub_cities.json"))
            if region_hub_cfg and "hubs" in region_hub_cfg:
                hubs.update(region_hub_cfg["hubs"].keys())
        return hubs

    def _save_output(self, name, nodes, itinerary, region):
        """生成 MD 和 CSV 输出"""
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

        # 检测区域
        if not region:
            first_city = nodes[0] if nodes else None
            if first_city:
                detected = self.get_region_for_city(first_city)
                region = detected if detected else "Europe"
            else:
                region = "Europe"

        safe_name = name.replace("/", "-").replace(" ", "_")
        guide_dir = os.path.join(self.base_dir, "data", region, "generated_routes")
        os.makedirs(guide_dir, exist_ok=True)

        md_path = os.path.join(guide_dir, f"{safe_name}.md")
        csv_path = os.path.join(guide_dir, f"{safe_name}.csv")

        with open(md_path, 'w', encoding='utf-8') as f:
            f.write(out)

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

        # 自动验证路线质量
        validation_result = validate_route(md_path, region, self.base_dir)

        # 输出验证结果
        if validation_result['status'] == 'ok':
            out += "\n✅ 路线验证通过\n"
        elif validation_result['status'] == 'warning':
            out += "\n⚠️  路线验证警告:\n"
            for warning in validation_result['warnings']:
                out += f"  • {warning}\n"
        else:  # error
            out += "\n❌ 路线验证失败:\n"
            for issue in validation_result['issues']:
                out += f"  • {issue}\n"
            for warning in validation_result['warnings']:
                out += f"  • {warning}\n"

        return {
            'markdown': out,
            'optimized_nodes': nodes,
            'md_path': md_path,
            'csv_path': csv_path,
            'validation': validation_result  # 添加验证结果
        }

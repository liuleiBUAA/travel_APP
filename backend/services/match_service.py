"""匹配算法服务"""

from typing import Dict, Any, List
from datetime import date, timedelta


class MatchService:
    """搭子匹配服务"""

    def calculate_route_similarity(self, route_a: Dict[str, Any], route_b: Dict[str, Any]) -> float:
        """
        计算两条路线的相似度

        算法：
        1. 城市重合度 (70%)：重合城市数 / 总城市数
        2. 顺序相似度 (20%)：核心城市顺序匹配度
        3. 天数相似度 (10%)：总天数接近程度

        返回：0-1之间的相似度分数
        """
        cities_a = set(route_a.get("cities", []))
        cities_b = set(route_b.get("cities", []))

        if not cities_a or not cities_b:
            return 0.0

        # 1. 城市重合度
        overlap = cities_a & cities_b  # 交集
        union = cities_a | cities_b    # 并集
        overlap_score = len(overlap) / len(union) if union else 0.0

        # ⭐ 关键修改：如果没有任何城市重合，直接返回0
        if len(overlap) == 0:
            return 0.0

        # 2. 顺序相似度（只比较重合的城市）
        order_score = 0.0
        if overlap:
            order_score = self._calculate_order_similarity(
                route_a.get("cities", []),
                route_b.get("cities", []),
                overlap
            )

        # 3. 天数相似度
        days_a = route_a.get("total_days", 0)
        days_b = route_b.get("total_days", 0)

        if days_a > 0 and days_b > 0:
            days_diff = abs(days_a - days_b)
            days_score = max(0, 1 - days_diff / max(days_a, days_b))
        else:
            days_score = 0.0

        # 综合分数（提高城市重合的权重）
        total_score = overlap_score * 0.7 + order_score * 0.2 + days_score * 0.1

        return min(1.0, total_score)

    def _calculate_order_similarity(self, cities_a: List[str], cities_b: List[str], overlap: set) -> float:
        """
        计算重合城市的顺序相似度
        使用位置差异的归一化值
        """
        if not overlap:
            return 0.0

        # 获取重合城市在各自路线中的位置
        positions_a = {city: i for i, city in enumerate(cities_a) if city in overlap}
        positions_b = {city: i for i, city in enumerate(cities_b) if city in overlap}

        if not positions_a or not positions_b:
            return 0.0

        # 计算位置差异
        total_diff = 0
        for city in overlap:
            if city in positions_a and city in positions_b:
                # 归一化位置 (0-1)
                pos_a = positions_a[city] / max(1, len(cities_a) - 1)
                pos_b = positions_b[city] / max(1, len(cities_b) - 1)
                total_diff += abs(pos_a - pos_b)

        # 平均差异
        avg_diff = total_diff / len(overlap)

        # 转换为相似度分数 (差异越小，分数越高)
        order_score = 1 - avg_diff

        return max(0.0, order_score)

    def calculate_time_score(self, date_a: date, date_b: date, flexibility: int = 7) -> float:
        """
        计算时间契合度

        参数：
        - date_a, date_b: 两个日期
        - flexibility: 时间灵活度（天）

        返回：0-1之间的契合度分数
        """
        days_diff = abs((date_a - date_b).days)

        if days_diff == 0:
            return 1.0  # 完全匹配

        if days_diff > flexibility:
            return 0.0  # 超出灵活范围

        # 线性衰减
        score = 1 - (days_diff / flexibility)

        return max(0.0, score)

    def calculate_preference_similarity(self, pref_a: Dict[str, Any], pref_b: Dict[str, Any]) -> float:
        """
        计算偏好相似度（可选）

        比较：
        1. 消费水平是否匹配
        2. 技能标签重合度
        3. 旅行风格匹配度
        """
        if not pref_a or not pref_b:
            return 0.5  # 默认中等相似

        score = 0.0
        factors = 0

        # 1. 消费水平
        budget_a = pref_a.get("budget_level", "")
        budget_b = pref_b.get("budget_level", "")
        if budget_a and budget_b:
            budget_levels = ["穷游", "经济", "舒适", "轻奢"]
            try:
                idx_a = budget_levels.index(budget_a)
                idx_b = budget_levels.index(budget_b)
                budget_score = 1 - abs(idx_a - idx_b) / len(budget_levels)
                score += budget_score
                factors += 1
            except ValueError:
                pass

        # 2. 技能标签重合度
        skills_a = set(pref_a.get("skills", []))
        skills_b = set(pref_b.get("skills", []))
        if skills_a or skills_b:
            overlap = skills_a & skills_b
            union = skills_a | skills_b
            skills_score = len(overlap) / len(union) if union else 0.0
            score += skills_score
            factors += 1

        # 3. 旅行风格
        style_a = pref_a.get("style", "")
        style_b = pref_b.get("style", "")
        if style_a and style_b:
            style_score = 1.0 if style_a == style_b else 0.3
            score += style_score
            factors += 1

        return score / factors if factors > 0 else 0.5

    def calculate_preference_match(self, pref_a: Dict[str, Any], pref_b: Dict[str, Any]) -> float:
        """
        计算出行偏好匹配度

        包含：
        1. 交通方式匹配 (30%)
        2. 消费水平匹配 (30%)
        3. 旅游节奏匹配 (25%)
        4. 住宿安排匹配 (10%)
        5. 拍照技能互补 (5%)

        返回：0-1之间的匹配度
        """
        # 1. 交通方式匹配 (40%)
        transport_a = pref_a.get("transport_mode", "不限")
        transport_b = pref_b.get("transport_mode", "不限")

        # 不限的人完全不挑，与任何选项都完美兼容
        if transport_a == "不限" or transport_b == "不限":
            transport_score = 1.0
        elif transport_a == transport_b:
            transport_score = 1.0
        elif "混合" in [transport_a, transport_b]:
            # 混合的人能适应大部分场景
            transport_score = 0.8
        elif {transport_a, transport_b} == {"公共交通为主", "自驾为主"}:
            # 都是"为主"，不是强制的，有协商空间
            transport_score = 0.3
        else:
            transport_score = 0.3

        # 2. 消费水平匹配 (40%) - 支持多选
        budget_map = {
            "穷游": 1,
            "经济": 2,
            "舒适": 3,
            "轻奢": 4
        }

        # 处理多选消费水平（逗号分隔）
        budget_str_a = pref_a.get("budget_level", "经济")
        budget_str_b = pref_b.get("budget_level", "经济")

        budgets_a = set(budget_str_a.split(',')) if ',' in budget_str_a else {budget_str_a}
        budgets_b = set(budget_str_b.split(',')) if ',' in budget_str_b else {budget_str_b}

        # 计算两个集合的重合度
        overlap = budgets_a & budgets_b
        if overlap:
            # 有重合，完美匹配
            budget_score = 1.0
        else:
            # 无重合，计算最小差距
            min_diff = 4  # 最大差距
            for ba in budgets_a:
                for bb in budgets_b:
                    level_a = budget_map.get(ba, 2)
                    level_b = budget_map.get(bb, 2)
                    min_diff = min(min_diff, abs(level_a - level_b))

            if min_diff == 0:
                budget_score = 1.0
            elif min_diff == 1:
                budget_score = 0.5
            else:
                budget_score = 0.0

        # 3. 住宿安排匹配 (10%)
        accom_a = pref_a.get("accommodation", "不限")
        accom_b = pref_b.get("accommodation", "不限")

        # 不限的人完全不挑，与任何选项都完美兼容
        if accom_a == "不限" or accom_b == "不限":
            accom_score = 1.0
        elif accom_a == accom_b:
            accom_score = 1.0
        elif {accom_a, accom_b} == {"可拼房", "各住各的"}:
            # 可拼房和想各住各的是利益冲突，无法凑一起
            accom_score = 0.0
        else:
            accom_score = 0.3

        # 4. 拍照技能互补/匹配 (10%)
        photo_a = pref_a.get("good_at_photo", "不限")
        photo_b = pref_b.get("good_at_photo", "不限")

        # 如果任一方是"不限"，给高分（完全兼容）
        if photo_a == "不限" or photo_b == "不限":
            photo_score = 0.9
        else:
            photo_map = {
                "一般": 1,
                "擅长": 2,
                "大师": 3
            }

            level_a = photo_map.get(photo_a, 1)
            level_b = photo_map.get(photo_b, 1)

            # 互补逻辑：有一方技能高，另一方一般 → 加分
            if (level_a >= 2 and level_b == 1) or (level_b >= 2 and level_a == 1):
                photo_score = 1.0  # 互补，完美
            # 都是高手 → 也不错
            elif level_a >= 2 and level_b >= 2:
                photo_score = 0.9
            # 技能接近 → 正常
            elif abs(level_a - level_b) <= 1:
                photo_score = 0.7
            else:
                photo_score = 0.5

        # 5. 旅游节奏匹配 (25%)
        pace_a = pref_a.get("travel_pace", "不限") or "不限"
        pace_b = pref_b.get("travel_pace", "不限") or "不限"

        if pace_a == "不限" or pace_b == "不限":
            pace_score = 1.0
        elif pace_a == pace_b:
            pace_score = 1.0
        elif {pace_a, pace_b} == {"特种兵", "慢悠悠"}:
            # 一个天天赶景点、一个想躺平，作息强冲突
            pace_score = 0.0
        else:
            # 适中 与 特种兵/慢悠悠：有协商空间
            pace_score = 0.5

        # 综合分数
        total = (transport_score * 0.30 +
                budget_score * 0.30 +
                pace_score * 0.25 +
                accom_score * 0.10 +
                photo_score * 0.05)

        return total

"""路线生成服务 - 集成travel_guide系统"""

import sys
import os
import json
import hashlib
from pathlib import Path
from typing import List, Dict, Any, Optional
from functools import lru_cache

# 添加travel_guide到路径
travel_guide_path = Path(__file__).parent.parent.parent / "travel_guide"
sys.path.insert(0, str(travel_guide_path))

from src.core.route_planner import TravelEngine
from src.core.recommend_smart import (
    get_all_destinations,
    calculate_season_score,
    load_coordinates,
    load_city_mapping
)


class RouteService:
    """路线生成服务 - 已优化：启动时加载数据到内存，缓存路线结果"""

    def __init__(self):
        # 获取travel_guide的base_dir
        base_dir = str(Path(__file__).parent.parent.parent / "travel_guide")
        self.engine = TravelEngine(base_dir=base_dir)

        # 🚀 性能优化：启动时一次性加载，缓存到内存
        print("🚀 [RouteService] 初始化：加载目的地、坐标、城市映射...")
        self.destinations = get_all_destinations(base_dir=base_dir)
        self.coordinates = load_coordinates(base_dir=base_dir)
        self.city_mapping = load_city_mapping(base_dir=base_dir)
        print(f"✅ [RouteService] 已加载 {len(self.destinations)} 个目的地")

    @staticmethod
    def _make_cache_key(cities: List[str], **kwargs) -> str:
        """生成缓存键"""
        key_data = {
            'cities': sorted(cities),
            **{k: v for k, v in kwargs.items() if v is not None}
        }
        key_str = json.dumps(key_data, sort_keys=True)
        return hashlib.md5(key_str.encode()).hexdigest()

    @lru_cache(maxsize=128)
    def _cached_generate(self, cache_key: str, cities_tuple: tuple, **kwargs) -> str:
        """内部缓存方法，返回 JSON 字符串"""
        cities = list(cities_tuple)
        result = self._do_generate_from_cities(cities, **kwargs)
        return json.dumps(result, ensure_ascii=False)

    def generate_from_cities(self, cities: List[str], **kwargs) -> Dict[str, Any]:
        """生成路线 - 带缓存"""
        cache_key = self._make_cache_key(cities, **kwargs)
        cities_tuple = tuple(cities)
        result_json = self._cached_generate(cache_key, cities_tuple, **kwargs)
        return json.loads(result_json)

    def _do_generate_from_cities(self, cities: List[str], **kwargs) -> Dict[str, Any]:
        """实际生成路线逻辑（被缓存调用）"""
        # 原来的 generate_from_cities 逻辑
        pass  # 待补充

    def recommend_route(self, month: int, days: int,
                       destinations: List[str] = None,
                       region: str = None,
                       countries: List[str] = None,
                       tags: List[str] = None,
                       start_city: str = None,
                       force_gateway_departure: bool = True,
                       force_order: bool = False,
                       same_day_max_hours: float = 4.0,
                       transport_preference: str = "auto",
                       options_display_mode: str = "compact") -> Dict[str, Any]:
        """
        基于月份和天数推荐路线
        使用travel_guide的完整智能推荐系统

        参数：
        - month: 旅行月份（1-12）
        - days: 总天数
        - destinations: 指定目的地（可选，如果指定则跳过推荐）
        - region: 区域筛选（Europe/Asia/North_America/Oceania）
        - countries: 国家筛选（如 ["法国", "意大利"]）
        - tags: 标签筛选（如 ["自然风光", "人文历史"]）
        - start_city: 起点城市（可选）
        """
        if destinations and len(destinations) > 0:
            # 用户指定了目的地，直接生成路线
            return self.generate_from_cities(
                destinations,
                start_node=start_city,
                force_gateway_departure=force_gateway_departure,
                force_order=force_order,
                same_day_max_hours=same_day_max_hours,
                transport_preference=transport_preference,
                options_display_mode=options_display_mode
            )

        # 调用完整推荐算法
        from src.core.recommend_smart import recommend_route as full_recommend

        # 如果没指定区域，默认欧洲
        if not region:
            region = "Europe"

        # 调用完整推荐算法
        result = full_recommend(
            region=region,
            total_days=days,
            tags=tags,
            month=month,
            start_city=start_city,
            countries=countries,
            base_dir=self.engine.base_dir
        )

        if not result.get('success'):
            raise ValueError(result.get('message', '推荐失败'))

        # 提取推荐的城市列表
        selected_cities = [dest['name'] for dest in result.get('selected', [])]

        if not selected_cities:
            raise ValueError(f"未找到适合的推荐路线")

        # 保底：只选了1个城市时，从候选中补一个天数最短的
        if len(selected_cities) == 1:
            candidates = result.get('candidates', [])
            for cand in sorted(candidates, key=lambda c: c['days']):
                if cand['name'] != selected_cities[0]:
                    selected_cities.append(cand['name'])
                    break
            # 补了城市需要重新生成
            return self.generate_from_cities(
                selected_cities,
                force_gateway_departure=force_gateway_departure,
                force_order=force_order,
                same_day_max_hours=same_day_max_hours,
                start_node=start_city,
                region=region,
                transport_preference=transport_preference,
                options_display_mode=options_display_mode
            )

        # recommend_smart已经生成了完整路线，直接读取CSV（不重复生成）
        route_text = result.get('route_text', {})
        csv_path = route_text.get('csv_path') if isinstance(route_text, dict) else None
        optimized_nodes = route_text.get('optimized_nodes', selected_cities) if isinstance(route_text, dict) else selected_cities

        if csv_path and Path(csv_path).exists():
            import csv
            itinerary = []
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    itinerary.append({
                        "day": int(row["day"]),
                        "city": row["stay"],
                        "activity": row["activity"],
                        "transport": row["transport"],
                        "stay": row["stay"]
                    })

            total_days = len(itinerary)
            unique_cities = list(dict.fromkeys([d["stay"] for d in itinerary if d["stay"] not in ["", "-"]]))
            days_per_city = {}
            for d in itinerary:
                c = d.get("stay", "")
                if c and c not in ["", "-"]:
                    days_per_city[c] = days_per_city.get(c, 0) + 1

            # 提取国家信息和验证结果
            countries = self._extract_countries_from_cities(optimized_nodes)
            validation_result = route_text.get('validation', {}) if isinstance(route_text, dict) else {}

            return {
                "route_type": "recommended",
                "countries": countries,
                "cities": optimized_nodes,
                "city_count": len(optimized_nodes),
                "total_days": total_days,
                "itinerary": itinerary,
                "days_per_city": days_per_city,
                "unique_cities": unique_cities,
                "description": f"{' → '.join(optimized_nodes)} 共{total_days}天",
                "cities_detail": [{"name": c, "stay_days": days_per_city.get(c, 0), "coordinates": self.coordinates.get(c, {})} for c in unique_cities],
                "validation": validation_result  # ⭐ 自动验证结果
            }

        # CSV不存在时回退到重新生成
        return self.generate_from_cities(
            selected_cities,
            start_node=start_city,
            force_gateway_departure=force_gateway_departure,
            force_order=force_order,
            same_day_max_hours=same_day_max_hours,
            region=region,
            transport_preference=transport_preference,
            options_display_mode=options_display_mode
        )

    def generate_from_cities(self, cities: List[str],
                            force_gateway_departure: bool = True,
                            force_order: bool = False,
                            same_day_max_hours: float = 4.0,
                            start_node: str = None,
                            end_node: str = None,
                            region: str = None,
                            transport_preference: str = "auto",
                            options_display_mode: str = "compact") -> Dict[str, Any]:
        """
        基于城市列表生成路线
        调用完整的TravelEngine生成详细行程

        参数：
        - cities: 城市列表
        - force_gateway_departure: 是否大城市出发/离开（默认True）
        - force_order: 是否保持输入顺序（默认False，会优化避免回头路）
        - same_day_max_hours: 单日最大行程时间（小时）
        - start_node: 指定起始城市（可选）
        - end_node: 指定结束城市（可选）
        """
        if not cities or len(cities) < 2:
            raise ValueError("至少需要2个城市才能生成路线")

        try:
            # 确定区域：优先使用传入的region，否则根据城市名推断
            if not region:
                region = self._detect_region(cities[0])

            # 调用TravelEngine.plan生成完整行程
            # plan方法会：
            # 1. 优化城市顺序（避免回头路）
            # 2. 计算跨城交通
            # 3. 展开每个城市的详细行程
            # 4. 生成Day by Day的itinerary

            # 注意：plan方法返回的是Markdown字符串，我们需要从CSV获取结构化数据
            import tempfile
            import csv

            # 创建临时输出目录
            with tempfile.TemporaryDirectory() as tmpdir:
                # 临时覆盖引擎实例属性
                _orig_transport = self.engine.transport_preference
                _orig_display = self.engine.options_display_mode
                _orig_force_gateway = self.engine.force_gateway_departure
                self.engine.force_gateway_departure = force_gateway_departure
                self.engine.transport_preference = transport_preference
                self.engine.options_display_mode = options_display_mode
                try:
                    # 调用plan方法（它会生成MD和CSV，并返回优化后的城市列表）
                    plan_result = self.engine.plan(
                        name="temp_route",
                        raw_nodes=cities,
                        start_node=start_node,
                        end_node=end_node,
                        force_order=force_order,
                        same_day_max_hours=same_day_max_hours,
                        region=region
                    )
                finally:
                    self.engine.force_gateway_departure = _orig_force_gateway
                    self.engine.transport_preference = _orig_transport
                    self.engine.options_display_mode = _orig_display

                # 获取优化后的城市列表和验证结果
                optimized_cities = plan_result.get('optimized_nodes', cities) if isinstance(plan_result, dict) else cities
                validation_result = plan_result.get('validation', {}) if isinstance(plan_result, dict) else {}

                # 读取生成的CSV（最新的）
                csv_path = Path(self.engine.base_dir) / "data" / region / "generated_routes" / "temp_route.csv"

                if csv_path.exists():
                    itinerary = []
                    with open(csv_path, 'r', encoding='utf-8') as f:
                        reader = csv.DictReader(f)
                        for row in reader:
                            # CSV格式: day, activity, transport, stay
                            # 需要从activity中提取city
                            day_num = int(row["day"])
                            activity_text = row["activity"]

                            # 判断是否是跨城交通
                            if "➔" in activity_text or "大交通" in activity_text:
                                # 跨城交通，从activity中提取城市
                                city = activity_text.split("前往")[-1].split("，")[0].strip() if "前往" in activity_text else row["stay"]
                            else:
                                # 普通活动，使用stay作为城市
                                city = row["stay"]

                            itinerary.append({
                                "day": day_num,
                                "city": city,
                                "activity": activity_text,
                                "transport": row["transport"],
                                "stay": row["stay"]
                            })

                    # 删除临时文件
                    csv_path.unlink()
                    md_path = csv_path.with_suffix('.md')
                    if md_path.exists():
                        md_path.unlink()
                else:
                    # 如果CSV生成失败，使用简化版本
                    raise Exception("路线生成失败，CSV文件未找到")

            # 统计信息
            total_days = len(itinerary)
            unique_cities = list(dict.fromkeys([day["stay"] for day in itinerary if day["stay"] not in ["", "-"]]))

            # 计算每个城市的停留天数
            days_per_city = {}
            for day in itinerary:
                city = day.get("stay", "")
                if city and city not in ["", "-"]:
                    days_per_city[city] = days_per_city.get(city, 0) + 1

            # 提取国家信息
            countries = self._extract_countries_from_cities(optimized_cities)

            return {
                "route_type": "generated",
                "countries": countries,
                "cities": optimized_cities,  # ✅ 使用优化后的城市顺序
                "input_cities": cities,  # 保留用户输入的顺序（供参考）
                "city_count": len(optimized_cities),
                "total_days": total_days,
                "itinerary": itinerary,  # ⭐完整的Day-by-Day行程
                "days_per_city": days_per_city,
                "unique_cities": unique_cities,
                "description": f"{' → '.join(optimized_cities)} 共{total_days}天，含详细行程",
                "cities_detail": [
                    {
                        "name": city,
                        "stay_days": days_per_city.get(city, 0),
                        "coordinates": self.coordinates.get(city, {})
                    }
                    for city in unique_cities
                ],
                "validation": validation_result  # ⭐ 自动验证结果
            }

        except Exception as e:
            # 如果完整生成失败，回退到简化版本
            print(f"完整路线生成失败: {e}，使用简化版本")
            return self._generate_simple_route(cities)

    def _generate_simple_route(self, cities: List[str]) -> Dict[str, Any]:
        """简化版路线生成（备用）"""
        total_days = 0
        cities_detail = []
        itinerary = []
        day_counter = 1

        for i, city in enumerate(cities):
            # 起点和终点2天，中间城市3天
            if i == 0 or i == len(cities) - 1:
                days = 2
            else:
                days = 3

            # 生成简单的行程
            for d in range(days):
                itinerary.append({
                    "day": day_counter,
                    "city": city,
                    "activity": f"{city}游览",
                    "transport": "当地交通",
                    "stay": city
                })
                day_counter += 1

            cities_detail.append({
                "name": city,
                "stay_days": days,
                "order": i + 1,
                "coordinates": self.coordinates.get(city, {})
            })
            total_days += days

        return {
            "route_type": "simple",
            "cities": cities,
            "city_count": len(cities),
            "total_days": total_days,
            "itinerary": itinerary,
            "cities_detail": cities_detail,
            "description": f"{' → '.join(cities)} 共{total_days}天"
        }

    def _detect_region(self, city: str) -> str:
        """根据城市名检测所属区域"""
        # 从destinations中查找城市所属区域
        for dest_name, dest_info in self.destinations.items():
            if city in dest_name or dest_name in city:
                region = dest_info.get("region", "")
                if region:
                    return region

        # 默认欧洲
        return "Europe"

    def _extract_countries_from_cities(self, cities: List[str]) -> List[str]:
        """从城市列表中提取所属国家（使用和route_planner相同的匹配逻辑）"""
        countries = set()
        for city in cities:
            # 1. 先通过 mapping 映射城市名
            mapped_city = self.city_mapping.get(city, city)

            # 2. 精确匹配（优先）
            dest_info = self.destinations.get(mapped_city) or self.destinations.get(city)

            # 3. 如果精确匹配失败，fallback到子串匹配（只用于模糊查找）
            if not dest_info:
                for dest_name, dest_data in self.destinations.items():
                    if city in dest_name or mapped_city in dest_name:
                        dest_info = dest_data
                        break

            # 提取国家信息
            if dest_info:
                dest_countries = dest_info.get('countries', [])
                countries.update(dest_countries)

        return sorted(list(countries))

    def format_manual_route(self, route: Dict[str, Any], region: str, countries: List[str]) -> Dict[str, Any]:
        """
        格式化手动输入的路线（用于找搭子）
        不生成详细行程，只标准化格式

        参数：
        - route: 包含 cities 和 days 的字典
        - region: 区域（Europe/North_America/Asia/Oceania）
        - countries: 国家列表（用户选择）
        """
        # 验证必需字段
        required_fields = ["cities", "days"]
        for field in required_fields:
            if field not in route:
                raise ValueError(f"缺少必需字段: {field}")

        # 标准化格式
        cities = route.get("cities", [])
        days = route.get("days", {})
        total_days = sum(days.values()) if isinstance(days, dict) else len(days)

        return {
            "route_type": "manual",
            "region": region,
            "countries": countries,
            "cities": cities,
            "city_count": len(cities),
            "total_days": total_days,
            "days_per_city": days,
            "description": f"{' → '.join(cities)} 共{total_days}天（自定义路线，{region}）",
            "cities_detail": [
                {
                    "name": city,
                    "stay_days": days.get(city, 2) if isinstance(days, dict) else 2,
                    "coordinates": self.coordinates.get(city, {})
                }
                for city in cities
            ]
        }

    def _recommend_destinations_by_season(self, month: int, max_days: int) -> Optional[Dict[str, Any]]:
        """
        根据季节推荐目的地
        返回最适合的城市列表
        """
        scored_destinations = []

        for dest_name, dest_info in self.destinations.items():
            season_score = calculate_season_score(dest_info.get("best_season", "全年"), month)

            if season_score > 0:  # 只考虑适合的季节
                scored_destinations.append({
                    "name": dest_name,
                    "score": season_score,
                    "region": dest_info.get("region", ""),
                    "days": dest_info.get("recommended_days", 3)
                })

        # 按分数排序
        scored_destinations.sort(key=lambda x: x["score"], reverse=True)

        # 选择前几个目的地，总天数接近max_days
        selected_cities = []
        total_days = 0

        for dest in scored_destinations[:5]:  # 最多5个目的地
            if total_days + dest["days"] <= max_days:
                selected_cities.append(dest["name"])
                total_days += dest["days"]

        if not selected_cities:
            return None

        return {
            "cities": selected_cities,
            "estimated_days": total_days,
            "reason": f"这些目的地在{month}月非常适合旅行"
        }

    def get_destination_structure(self) -> Dict[str, Any]:
        """
        获取完整的目的地结构（区域→国家→城市）
        基于实际的destinations.json文件
        """
        structure = {
            "Europe": {
                "name": "欧洲",
                "countries": {
                    "法国": "法国_destinations.json",
                    "英国": "英国_destinations.json",
                    "意大利": "意大利_destinations.json",
                    "西班牙": "西班牙_destinations.json",
                    "德国": "德国_destinations.json",
                    "瑞士": "瑞士_destinations.json",
                    "希腊": "希腊_destinations.json",
                    "葡萄牙": "葡萄牙_destinations.json",
                    "荷兰比利时": "荷兰比利时_destinations.json",
                    "奥地利克罗地亚": "奥地利克罗地亚_destinations.json",
                    "捷克匈牙利": "捷克匈牙利_destinations.json",
                    "北欧": "北欧_destinations.json",
                    "土耳其": "土耳其_destinations.json",
                    "阿联酋埃及": "阿联酋埃及_destinations.json",
                }
            },
            "North_America": {
                "name": "北美",
                "countries": {
                    "加拿大": "加拿大_destinations.json",
                    "美国西部": "美国西部_destinations.json",
                    "美国东部中部": "美国东部中部_destinations.json",
                    "阿拉斯加加勒比海夏威夷": "阿拉斯加加勒比海夏威夷_destinations.json",
                }
            },
            "Asia": {
                "name": "亚洲",
                "countries": {
                    "日本": "日本_destinations.json",
                }
            },
            "Oceania": {
                "name": "大洋洲",
                "countries": {
                    "澳大利亚": "澳大利亚_destinations.json",
                    "新西兰": "新西兰_destinations.json",
                    "斐济": "斐济_destinations.json",
                }
            }
        }
        return structure

    def get_countries_by_region(self, region: str) -> List[str]:
        """
        获取指定区域下的所有国家
        """
        structure = self.get_destination_structure()
        region_map = {
            "欧洲": "Europe",
            "亚洲": "Asia",
            "北美": "North_America",
            "大洋洲": "Oceania"
        }

        region_key = region_map.get(region, region)
        if region_key in structure:
            return list(structure[region_key]["countries"].keys())
        return []

    def get_cities_by_country(self, region: str, country: str, limit: int = 16) -> List[Dict[str, Any]]:
        """
        获取指定国家下的所有城市/目的地
        返回前limit个（默认16个）
        """
        region_map = {
            "欧洲": "Europe",
            "亚洲": "Asia",
            "北美": "North_America",
            "大洋洲": "Oceania"
        }

        region_key = region_map.get(region, region)
        structure = self.get_destination_structure()

        if region_key not in structure:
            return []

        countries = structure[region_key]["countries"]
        if country not in countries:
            return []

        # 读取对应的destinations.json文件
        file_name = countries[country]
        file_path = Path(self.engine.base_dir) / "data" / region_key / "guides" / file_name

        if not file_path.exists():
            return []

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                destinations = json.load(f)

            # 提取城市信息
            cities = []
            for city_name, city_info in list(destinations.items())[:limit]:
                # 过滤规则：
                # - 保留有实际行程内容的🔄环线（羚羊谷+大峡谷、黄石大提顿等）
                # - 只过滤纯粹的返回标记（🔄 返回起点、🔄 环回）
                if "🔄" in city_name:
                    # 检查是否有实际行程内容
                    has_itinerary = city_info.get("itinerary") and len(city_info.get("itinerary", [])) > 0
                    is_loop_route = city_info.get("loop_type") == "loop"

                    # 保留有详细行程的环线，过滤纯返回标记
                    if not (has_itinerary and is_loop_route):
                        continue

                # 根据itinerary数组计算天数，如果没有则使用recommended_days字段
                itinerary = city_info.get("itinerary", [])
                if itinerary:
                    # 直接使用itinerary数组长度作为建议天数
                    # 这代表了攻略中实际的day-by-day条目数
                    recommended_days = len(itinerary)
                else:
                    recommended_days = city_info.get("recommended_days", 2)

                cities.append({
                    "name": city_name,
                    "best_season": city_info.get("best_season", "全年"),
                    "recommended_days": recommended_days,
                })

            return cities[:limit]

        except Exception as e:
            print(f"读取城市数据失败: {e}")
            return []

    def get_popular_destinations(self, region: str = None) -> Dict[str, Any]:
        """
        获取热门目的地城市列表
        返回按地区分组的热门城市
        """
        all_popular = {
            "欧洲": [
                {"name": "巴黎", "country": "法国"},
                {"name": "伦敦", "country": "英国"},
                {"name": "罗马", "country": "意大利"},
                {"name": "威尼斯", "country": "意大利"},
                {"name": "佛罗伦萨", "country": "意大利"},
                {"name": "米兰", "country": "意大利"},
                {"name": "阿姆斯特丹", "country": "荷兰"},
                {"name": "巴塞罗那", "country": "西班牙"},
                {"name": "马德里", "country": "西班牙"},
                {"name": "布拉格", "country": "捷克"},
                {"name": "维也纳", "country": "奥地利"},
                {"name": "苏黎世", "country": "瑞士"},
            ],
            "亚洲": [
                {"name": "东京", "country": "日本"},
                {"name": "京都", "country": "日本"},
                {"name": "大阪", "country": "日本"},
                {"name": "北海道", "country": "日本"},
                {"name": "冲绳", "country": "日本"},
                {"name": "曼谷", "country": "泰国"},
                {"name": "新加坡", "country": "新加坡"},
                {"name": "首尔", "country": "韩国"},
            ],
            "北美": [
                {"name": "纽约", "country": "美国"},
                {"name": "洛杉矶", "country": "美国"},
                {"name": "旧金山", "country": "美国"},
                {"name": "拉斯维加斯", "country": "美国"},
                {"name": "西雅图", "country": "美国"},
                {"name": "芝加哥", "country": "美国"},
                {"name": "温哥华", "country": "加拿大"},
                {"name": "多伦多", "country": "加拿大"},
            ],
            "大洋洲": [
                {"name": "悉尼", "country": "澳大利亚"},
                {"name": "墨尔本", "country": "澳大利亚"},
                {"name": "黄金海岸", "country": "澳大利亚"},
                {"name": "凯恩斯", "country": "澳大利亚"},
                {"name": "奥克兰", "country": "新西兰"},
                {"name": "皇后镇", "country": "新西兰"},
            ]
        }

        if region and region in all_popular:
            # 返回指定区域
            return {
                "region": region,
                "cities": all_popular[region]
            }
        else:
            # 返回所有区域
            return {
                "regions": list(all_popular.keys()),
                "all_cities": all_popular
            }

    def search_destinations(self, query: str) -> List[str]:
        """
        搜索目的地（自动完成）
        返回匹配的城市名称列表
        """
        if not query:
            return []

        # 从destinations中搜索
        matched = []
        for dest_name in self.destinations.keys():
            if query.lower() in dest_name.lower() or query in dest_name:
                matched.append(dest_name)

        # 限制返回数量
        return matched[:20]

    def _format_route_json(self, raw_result: Dict[str, Any], cities: List[str]) -> Dict[str, Any]:
        """
        格式化路线JSON为标准格式
        """
        # 从route_planner的结果中提取关键信息
        itinerary = raw_result.get("itinerary", [])

        # 计算每个城市的停留天数
        days_per_city = {}
        for day in itinerary:
            city = day.get("city", "")
            if city:
                days_per_city[city] = days_per_city.get(city, 0) + 1

        return {
            "route_type": "generated",
            "cities": cities,
            "city_count": len(cities),
            "total_days": len(itinerary),
            "days_per_city": days_per_city,
            "itinerary": itinerary,  # 完整行程
            "cities_detail": [
                {
                    "name": city,
                    "stay_days": days_per_city.get(city, 0),
                    "coordinates": self.coordinates.get(city, {})
                }
                for city in cities
            ],
            "raw_result": raw_result  # 保留原始数据
        }

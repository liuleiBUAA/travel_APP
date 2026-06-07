#!/usr/bin/env python3
"""
从 destinations.json 自动生成 classic_routes.json
只使用已有攻略的目的地，确保测试路线可用
"""
import json
import os
from src.core.recommend_smart import get_all_destinations

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUTPUT_FILE = os.path.join(BASE_DIR, "config", "classic_routes.json")

# 经典路线配置模板
# 每条路线指定：区域、国家/主题、标签筛选、天数范围、是否循环
ROUTE_TEMPLATES = [
    # Europe
    {
        "name": "英国全景",
        "region": "Europe",
        "countries": ["英国"],
        "cities": ["伦敦", "牛津", "英国湖区", "爱丁堡", "苏格兰高地"],
        "force_order": True,
        "circular": True
    },
    {
        "name": "法国经典",
        "region": "Europe",
        "countries": ["法国"],
        "tags": ["人文历史", "自然风光"],
        "max_cities": 5,
        "force_order": True,
        "circular": True
    },
    {
        "name": "意大利经典",
        "region": "Europe",
        "countries": ["意大利"],
        "cities": ["罗马", "佛罗伦萨", "威尼斯", "米兰"],
        "force_order": False
    },
    {
        "name": "瑞士湖光山色",
        "region": "Europe",
        "countries": ["瑞士"],
        "tags": ["自然风光"],
        "max_cities": 5
    },
    {
        "name": "西班牙文化",
        "region": "Europe",
        "countries": ["西班牙"],
        "tags": ["人文历史", "海滩度假"],
        "max_cities": 5,
        "force_order": True,
        "circular": True
    },
    {
        "name": "希腊浪漫",
        "region": "Europe",
        "countries": ["希腊"],
        "tags": ["人文历史", "海滩度假"],
        "force_order": True,
        "circular": True
    },
    {
        "name": "中欧文化",
        "region": "Europe",
        "countries": ["捷克", "奥地利", "匈牙利"],
        "cities": ["布拉格", "维也纳", "布达佩斯"]
    },
    {
        "name": "北欧三国",
        "region": "Europe",
        "countries": ["北欧"],
        "tags": ["自然风光"],
        "max_cities": 5
    },
    {
        "name": "土耳其文化",
        "region": "Europe",
        "countries": ["土耳其"],
        "tags": ["人文历史"],
        "force_order": True,
        "circular": True
    },

    # North America
    {
        "name": "美西海岸",
        "region": "North_America",
        "cities": ["西雅图", "波特兰", "旧金山", "洛杉矶"]
    },
    {
        "name": "加州精华",
        "region": "North_America",
        "cities": ["旧金山", "洛杉矶", "圣地亚哥"],
        "circular": True
    },
    {
        "name": "美东文化",
        "region": "North_America",
        "cities": ["纽约", "费城", "华盛顿", "波士顿"]
    },
    {
        "name": "加拿大西部",
        "region": "North_America",
        "countries": ["加拿大"],
        "cities": ["温哥华", "班夫国家公园", "贾斯珀国家公园"],
        "force_order": True,
        "circular": True
    },
    {
        "name": "加拿大东部",
        "region": "North_America",
        "cities": ["多伦多", "尼亚加拉瀑布"],
        "force_order": True,
        "circular": True
    },

    # Oceania
    {
        "name": "澳洲东海岸",
        "region": "Oceania",
        "cities": ["悉尼", "黄金海岸", "凯恩斯"],
        "force_order": True,
        "circular": True
    },
    {
        "name": "澳洲南部",
        "region": "Oceania",
        "cities": ["墨尔本", "大洋路", "塔斯马尼亚"],
        "force_order": True,
        "circular": True
    },
    {
        "name": "新西兰南北岛",
        "region": "Oceania",
        "cities": ["奥克兰", "南岛", "皇后镇", "北岛"],
        "force_order": True,
        "circular": True
    },

    # Asia
    {
        "name": "日本关西关东",
        "region": "Asia",
        "cities": ["东京", "京都", "大阪", "奈良"],
        "circular": True
    },
    {
        "name": "日本全景",
        "region": "Asia",
        "countries": ["日本"],
        "max_cities": 4
    },
]

def find_destinations(region, countries=None, tags=None, cities=None, max_cities=None):
    """
    根据条件查找目的地

    Args:
        region: 区域
        countries: 国家列表（可选）
        tags: 标签列表（可选）
        cities: 指定城市列表（优先使用）
        max_cities: 最大城市数量

    Returns:
        城市名列表
    """
    all_dests = get_all_destinations(BASE_DIR)

    # 如果指定了具体城市，先验证是否存在
    if cities:
        validated_cities = []
        for city in cities:
            if city in all_dests:
                validated_cities.append(city)
            else:
                print(f"    ⚠️  {city} 不存在，跳过")
        return validated_cities

    # 否则按条件筛选
    candidates = []
    for dest_name, dest_info in all_dests.items():
        # 区域筛选
        if dest_info['region'] != region:
            continue

        # 国家筛选
        if countries:
            dest_countries = dest_info.get('countries', [])
            if not any(c in dest_countries for c in countries):
                continue

        # 标签筛选
        if tags:
            dest_tags = dest_info.get('tags', {})
            if not any(tag in dest_tags for tag in tags):
                continue

        # 计算分数（标签权重和）
        score = sum(dest_info.get('tags', {}).values())
        candidates.append((dest_name, score))

    # 按分数排序
    candidates.sort(key=lambda x: x[1], reverse=True)

    # 取前N个
    if max_cities:
        candidates = candidates[:max_cities]

    return [name for name, score in candidates]

def generate_route(template):
    """根据模板生成路线配置"""
    name = template['name']
    region = template['region']

    print(f"📍 生成: {name} ({region})")

    # 查找目的地
    cities = find_destinations(
        region=region,
        countries=template.get('countries'),
        tags=template.get('tags'),
        cities=template.get('cities'),
        max_cities=template.get('max_cities')
    )

    if not cities:
        print(f"    ⚠️  未找到符合条件的目的地，跳过")
        return None

    print(f"    ✅ {' → '.join(cities)}")

    # 如果是循环路线，添加起点到终点
    if template.get('circular') and len(cities) > 1:
        cities.append(cities[0])

    # 构建路线配置
    route = {
        "name": name,
        "region": region,
        "cities": cities
    }

    # 添加可选配置
    config = {}
    if template.get('force_order') is not None:
        config['force_order'] = template['force_order']

    if config:
        route['config'] = config

    return route

def generate_classic_routes():
    """生成所有经典路线"""
    print("🚀 开始生成经典测试路线\n")

    routes = []
    for template in ROUTE_TEMPLATES:
        route = generate_route(template)
        if route:
            routes.append(route)
            print()

    # 构建完整配置
    config_data = {
        "description": f"{len(routes)}条经典旅游路线配置 - 自动生成，所有城市均在destinations.json中存在",
        "global_config": {
            "same_day_max_hours": 4.0,
            "force_gateway_departure": True,
            "force_order": False,
            "options_display_mode": "compact",
            "transport_preference": "auto"
        },
        "routes": routes
    }

    # 保存
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(config_data, f, ensure_ascii=False, indent=2)

    print(f"{'='*60}")
    print(f"📊 生成完成")
    print(f"{'='*60}")
    print(f"✅ 成功生成 {len(routes)} 条路线")
    print(f"💾 已保存到: {OUTPUT_FILE}")
    print(f"{'='*60}\n")

    # 验证：所有城市都应该存在
    print("🔍 验证城市名...")
    all_dests = get_all_destinations(BASE_DIR)
    all_valid = True

    for route in routes:
        for city in route['cities']:
            if city not in all_dests:
                print(f"❌ [{route['name']}] {city} 不存在！")
                all_valid = False

    if all_valid:
        print("✅ 所有城市验证通过！\n")
    else:
        print("⚠️  发现无效城市，请检查\n")

    return config_data

if __name__ == '__main__':
    generate_classic_routes()

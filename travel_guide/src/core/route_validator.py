#!/usr/bin/env python3
"""
路线质量验证模块 - 从 verify_routes.py 提取核心验证逻辑
供 route_planner.py 在生成路线后自动调用
"""

import os
import re
import json
from collections import defaultdict
from pathlib import Path

# 城市别名/区域映射
CITY_ALIASES = {
    "北海道": ["札幌", "函馆", "美瑛", "小樽"],
    "南岛": ["皇后镇", "基督城", "蒂卡波", "但尼丁"],
    "北岛": ["奥克兰", "罗托鲁瓦", "惠灵顿"],
    "挪威": ["卑尔根", "奥斯陆", "特罗姆瑟"],
    "冲绳": ["那霸市区", "那霸", "恩纳村"],
    "塔斯马尼亚": ["霍巴特", "朗塞斯顿"],
    "阿拉斯加": ["安克雷奇", "费尔班克斯"],
    "特内里费岛": ["特内里费"],
    "蔚蓝海岸": ["尼斯"],
    "苏格兰高地": ["因弗内斯", "天空岛"],
}

def normalize_city(city):
    """标准化城市名"""
    if not city:
        return city
    if "前往" in city:
        city = city.split("前往")[0].strip()
    city = city.rstrip("，。")
    return city

def cities_match(city1, city2):
    """判断两个城市是否匹配（考虑别名）"""
    city1 = normalize_city(city1)
    city2 = normalize_city(city2)

    if city1 == city2:
        return True

    # 检查别名
    for key, aliases in CITY_ALIASES.items():
        if city1 == key and city2 in aliases:
            return True
        if city2 == key and city1 in aliases:
            return True
        if city1 in aliases and city2 in aliases:
            return True

    # 部分匹配
    if city1 in city2 or city2 in city1:
        return True

    return False

def load_json(path):
    """加载JSON文件"""
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def load_region_hubs(base_dir):
    """加载各区域hub配置"""
    hubs = {}
    for region in ["Europe", "North_America", "Oceania", "Asia"]:
        hub_file = os.path.join(base_dir, "data", region, "hub_cities.json")
        if os.path.exists(hub_file):
            data = load_json(hub_file)
            if 'hubs' in data:
                hubs[region] = list(data['hubs'].keys())
    return hubs

def load_transport_data(base_dir, region):
    """加载交通数据"""
    routes_file = os.path.join(base_dir, "data", region, "transport_routes.json")
    return load_json(routes_file)

def load_destinations(base_dir, region):
    """加载目的地攻略数据"""
    all_dests = {}
    for dest_file in Path(base_dir).rglob("*_destinations.json"):
        if region in str(dest_file):
            all_dests.update(load_json(dest_file))
    return all_dests

def validate_route(md_path, region, base_dir):
    """
    验证生成的路线文件

    Args:
        md_path: 路线文件路径
        region: 区域名
        base_dir: travel_guide 根目录

    Returns:
        dict: {
            'status': 'ok'/'warning'/'error',
            'issues': [...],  # 错误列表
            'warnings': [...]  # 警告列表
        }
    """
    with open(md_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 加载数据
    region_hubs = load_region_hubs(base_dir)
    transport_data = load_transport_data(base_dir, region)
    destinations = load_destinations(base_dir, region)

    issues = []
    warnings = []

    # ========== 格式和语法检查 ==========
    lines = content.split('\n')

    # 1. 检查交通时间显示错误
    if ' -h' in content or 'Noneh' in content:
        line_nums = []
        for i, line in enumerate(lines, 1):
            if ' -h' in line or 'Noneh' in line:
                line_nums.append(f"L{i}")
        issues.append(f"交通时间显示错误: {', '.join(line_nums)}")

    # 2. 检查Day编号连续性
    day_pattern = re.compile(r'\| Day (\d+) \|')
    days = []
    for line in lines:
        match = day_pattern.search(line)
        if match:
            days.append(int(match.group(1)))

    if days:
        expected = list(range(days[0], days[-1] + 1))
        if days != expected:
            issues.append(f"Day编号不连续: {days}")

    # 3. 检查重复地名
    duplicate_pattern = re.compile(r'从([^前往，、\s]+)前往\1[，、]')
    for i, line in enumerate(lines, 1):
        match = duplicate_pattern.search(line)
        if match:
            issues.append(f"L{i}: 重复地名 '从{match.group(1)}前往{match.group(1)}'")

    # 4. 检查占位符残留
    if '游览' in content and '核心景点' in content:
        placeholder_lines = []
        for i, line in enumerate(lines, 1):
            if '游览' in line and '核心景点' in line:
                placeholder_lines.append(f"L{i}")
        if placeholder_lines:
            warnings.append(f"使用了通用占位符: {', '.join(placeholder_lines)}")

    # ========== 提取路线数据 ==========
    route_sequence = []
    city_days = defaultdict(int)
    for line in lines:
        if '| Day' in line and '天数' not in line and '【到达日】' not in line and '【离开日】' not in line:
            parts = [p.strip() for p in line.split('|')]
            if len(parts) >= 5:
                stay = normalize_city(parts[4])
                if stay and stay != '-':
                    if not route_sequence or route_sequence[-1] != stay:
                        route_sequence.append(stay)
                    city_days[stay] += 1

    # ========== 质量检查 ==========

    # 1. 检查走回头路
    if len(route_sequence) != len(set(route_sequence)):
        revisits = [city for i, city in enumerate(route_sequence)
                   if city in route_sequence[:i]]
        warnings.append(f"走回头路: {', '.join(set(revisits))}")

    # 2. 检查起终点是否为hub城市
    hubs = region_hubs.get(region, [])

    # 提取起点
    start_city = None
    for line in lines:
        if '| Day 0 |' in line or '| Day 1 |' in line:
            parts = [p.strip() for p in line.split('|')]
            if len(parts) >= 5:
                start_city = normalize_city(parts[4])
                if start_city and start_city != '-':
                    break

    # 提取终点
    end_city = None
    for i in range(len(lines)-1, -1, -1):
        if '【离开日】' in lines[i]:
            parts = [p.strip() for p in lines[i].split('|')]
            if len(parts) >= 3:
                activity_text = parts[2]
                if '从' in activity_text and '飞离' in activity_text:
                    end_city = normalize_city(activity_text.split('从')[1].split('飞离')[0])
                elif '从' in activity_text and '前往' in activity_text:
                    match_text = activity_text.split('从')[1].split('前往')
                    if len(match_text) >= 2:
                        end_city = normalize_city(match_text[1].split('，')[0])
                if not end_city and route_sequence:
                    end_city = route_sequence[-1]
            break

    start_in_hub = any(cities_match(start_city, hub) for hub in hubs) if start_city else False
    end_in_hub = any(cities_match(end_city, hub) for hub in hubs) if end_city else False

    if start_city and not start_in_hub:
        warnings.append(f"起点 '{start_city}' 不在hub城市")

    if end_city and not end_in_hub:
        warnings.append(f"终点 '{end_city}' 不在hub城市")

    # 3. 检查停留天数
    for city, days_count in city_days.items():
        city_info = destinations.get(city, {})
        recommended_days = len(city_info.get('itinerary', []))

        if recommended_days > 0:
            if days_count < recommended_days * 0.5:
                warnings.append(f"{city} 停留{days_count}天偏短，建议至少{recommended_days}天")
            elif days_count > recommended_days * 2:
                warnings.append(f"{city} 停留{days_count}天过长，建议{recommended_days}天")

    # ========== 判断状态 ==========
    if issues:
        status = "error"
    elif len(warnings) >= 3:
        status = "warning"
    else:
        status = "ok"

    return {
        "status": status,
        "issues": issues,
        "warnings": warnings,
        "days": sum(city_days.values()),
        "cities": len(route_sequence),
        "route_sequence": route_sequence
    }

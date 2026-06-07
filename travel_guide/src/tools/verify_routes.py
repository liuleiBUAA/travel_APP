#!/usr/bin/env python3
"""
完整版路线验证工具 - 格式检查 + 质量验证
合并了 validate_generated_routes.py 和原 verify_routes_enhanced.py 的全部功能

格式和语法检查（6项）：
1. 交通时间显示错误（-h, Noneh）
2. Day编号连续性
3. 命令行参数残留
4. 重复地名检查
5. 占位符残留
6. 过多0.00h中转点

路线质量验证（6大维度）：
1. 路线顺序优化
2. 起终点选择（区域级hub配置 + 城市别名）
3. 停留天数分配
4. 交通方式合理性
5. 数据来源准确性
6. 行程内容匹配度
"""
import os
import re
import json
from collections import defaultdict

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 城市别名/区域映射（来自 verify_routes_fixed.py）
CITY_ALIASES = {
    # 区域→内部城市
    "北海道": ["札幌", "函馆", "美瑛", "小樽"],
    "南岛": ["皇后镇", "基督城", "蒂卡波", "但尼丁"],
    "北岛": ["奥克兰", "罗托鲁瓦", "惠灵顿"],
    "挪威": ["卑尔根", "奥斯陆", "特罗姆瑟"],
    "冲绳": ["那霸市区", "那霸", "恩纳村"],
    "塔斯马尼亚": ["霍巴特", "朗塞斯顿"],
    "阿拉斯加": ["安克雷奇", "费尔班克斯"],

    # 命名变体
    "特内里费岛": ["特内里费"],
    "蔚蓝海岸": ["尼斯"],
    "苏格兰高地": ["因弗内斯", "天空岛"],
}

with open(f"{BASE}/config/city_to_region.json", 'r', encoding='utf-8') as f:
    CITY_TO_REGION = json.load(f)

def normalize_city(city):
    """标准化城市名（去除后缀等）"""
    if not city:
        return city
    # 去除"前往XX"后缀
    if "前往" in city:
        city = city.split("前往")[0].strip()
    # 去除标点
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

def load_region_hubs():
    """加载各区域hub配置（使用区域级配置文件）"""
    hubs = {}
    for region in ["Europe", "North_America", "Oceania", "Asia"]:
        hub_file = f"{BASE}/data/{region}/hub_cities.json"
        if os.path.exists(hub_file):
            with open(hub_file, 'r', encoding='utf-8') as f:
                hubs[region] = list(json.load(f)['hubs'].keys())
    return hubs

def load_transport_data(region):
    """加载交通数据"""
    routes_file = f"{BASE}/data/{region}/transport_routes.json"
    if os.path.exists(routes_file):
        with open(routes_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def load_destinations(region):
    """加载目的地攻略数据"""
    guides_dir = f"{BASE}/data/{region}/guides"
    all_dests = {}
    if os.path.exists(guides_dir):
        for file in os.listdir(guides_dir):
            if file.endswith('_destinations.json'):
                with open(f"{guides_dir}/{file}", 'r', encoding='utf-8') as f:
                    all_dests.update(json.load(f))
    return all_dests

def verify_route_enhanced(region, filename, region_hubs):
    """完整版路线验证（格式检查 + 质量检查）"""
    md_path = os.path.join(BASE, "data", region, "generated_routes", filename)

    with open(md_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 加载数据
    transport_data = load_transport_data(region)
    destinations = load_destinations(region)

    issues = []
    warnings = []

    # ========== 格式和语法检查（来自 validate_generated_routes.py）==========
    lines = content.split('\n')

    # 1. 检查交通时间显示错误（-h或Noneh）
    if ' -h' in content or 'Noneh' in content:
        line_nums = []
        for i, line in enumerate(lines, 1):
            if ' -h' in line or 'Noneh' in line:
                line_nums.append(f"L{i}")
        issues.append(f"交通时间显示错误（-h或Noneh）: {', '.join(line_nums)}")

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

    # 3. 检查命令行参数残留
    if '--region' in content or '--nodes' in content or '--start' in content:
        issues.append("包含命令行参数残留")

    # 4. 检查重复地名（"从X前往X"）
    duplicate_pattern = re.compile(r'从([^前往，、\s]+)前往\1[，、]')
    for i, line in enumerate(lines, 1):
        match = duplicate_pattern.search(line)
        if match:
            issues.append(f"L{i}: 重复地名 '从{match.group(1)}前往{match.group(1)}'")

    # 5. 检查占位符残留（警告）
    if '游览' in content and '核心景点' in content:
        placeholder_lines = []
        for i, line in enumerate(lines, 1):
            if '游览' in line and '核心景点' in line:
                placeholder_lines.append(f"L{i}")
        if placeholder_lines:
            warnings.append(f"使用了通用占位符: {', '.join(placeholder_lines)}")

    # 6. 检查过多0.00h中转点（警告）
    for i, line in enumerate(lines, 1):
        if '0.00h' in line and '跨城' in line and line.count('0.00h') > 2:
            warnings.append(f"L{i}: 过多的0.00h中转点")

    # ========== 基础数据提取 ==========
    title_match = re.search(r'# (.+)', content)
    if not title_match:
        return {"status": "error", "issues": ["无标题"]}

    title = title_match.group(1)
    expected_cities = [c.strip() for c in title.split('+')]

    # 提取完整行程
    route_sequence = []
    city_days = defaultdict(int)
    for line in lines:
        if '| Day' in line and '天数' not in line and '【到达日】' not in line and '【离开日】' not in line:
            parts = [p.strip() for p in line.split('|')]
            if len(parts) >= 5:
                day_num = parts[1]
                activity = parts[2]
                stay = normalize_city(parts[4])

                if stay and stay != '-':
                    if not route_sequence or route_sequence[-1] != stay:
                        route_sequence.append(stay)
                    city_days[stay] += 1
    
    # ========== 1. 路线顺序检查 ==========
    # 检查是否有往返重复（走回头路）
    if len(route_sequence) != len(set(route_sequence)):
        revisits = [city for i, city in enumerate(route_sequence)
                   if city in route_sequence[:i]]
        warnings.append(f"走回头路: {', '.join(set(revisits))}")

    # ========== 2. 起终点选择检查（使用精确提取 + 区域hub + 别名匹配）==========
    # 提取起点（Day 0 或 Day 1）
    start_city = None
    for line in lines:
        if '| Day 0 |' in line or '| Day 1 |' in line:
            parts = [p.strip() for p in line.split('|')]
            if len(parts) >= 5:
                start_city = normalize_city(parts[4])
                if start_city and start_city != '-':
                    break

    # 提取终点（离开日的出发城市）
    end_city = None
    for i in range(len(lines)-1, -1, -1):
        if '【离开日】' in lines[i]:
            parts = [p.strip() for p in lines[i].split('|')]
            if len(parts) >= 3:
                activity_text = parts[2]
                # 匹配"从XX前往YY"模式
                if '从' in activity_text and '前往' in activity_text:
                    match_text = activity_text.split('从')[1].split('前往')
                    if len(match_text) >= 2:
                        end_city = normalize_city(match_text[1].split('，')[0].split('、')[0])
                # 匹配"从XX飞离"模式
                elif '从' in activity_text and '飞离' in activity_text:
                    end_city = normalize_city(activity_text.split('从')[1].split('飞离')[0])
                # 如果都没匹配到，检查前一天的住宿
                if not end_city or end_city == '-':
                    for j in range(i-1, -1, -1):
                        if '| Day' in lines[j] and '【到达日】' not in lines[j]:
                            day_parts = [p.strip() for p in lines[j].split('|')]
                            if len(day_parts) >= 5:
                                end_city = normalize_city(day_parts[4])
                                if end_city and end_city != '-':
                                    break
                        break
            break

    # 如果没找到离开日，使用route_sequence的最后一个城市
    if not end_city and route_sequence:
        end_city = route_sequence[-1]

    # 使用区域级hub配置和别名匹配检查
    hubs = region_hubs.get(region, [])
    start_in_hub = any(cities_match(start_city, hub) for hub in hubs) if start_city else False
    end_in_hub = any(cities_match(end_city, hub) for hub in hubs) if end_city else False

    if start_city and not start_in_hub:
        warnings.append(f"起点 '{start_city}' 不在hub城市")

    if end_city and not end_in_hub:
        warnings.append(f"终点 '{end_city}' 不在hub城市")
    
    # ========== 3. 停留天数分配检查 ==========
    for city, days in city_days.items():
        city_info = destinations.get(city, {})
        recommended_days = len(city_info.get('itinerary', []))
        
        if recommended_days > 0:
            if days < recommended_days * 0.5:
                warnings.append(f"{city} 停留{days}天，建议至少{recommended_days}天")
            elif days > recommended_days * 2:
                warnings.append(f"{city} 停留{days}天过长，建议{recommended_days}天")
    
    # ========== 4. 交通方式检查 ==========
    transport_modes = []
    for match in re.finditer(r'跨城:([^|]+)', content):
        transport_modes.append(match.group(1).strip())
    
    # 检查是否有不合理的交通方式（如短途用飞机、长途用自驾）
    for i, mode_info in enumerate(transport_modes):
        if '飞机' in mode_info:
            time_match = re.search(r'(\d+\.?\d*)h', mode_info)
            if time_match and float(time_match.group(1)) < 0.5:
                warnings.append(f"短途使用飞机可能不合理: {mode_info}")
        
        if '自驾' in mode_info:
            time_match = re.search(r'(\d+\.?\d*)h', mode_info)
            if time_match and float(time_match.group(1)) > 6:
                warnings.append(f"长途自驾可能太累: {mode_info}")
    
    # ========== 5. 数据来源准确性检查 ==========
    # 检查交通时间是否来自transport_routes.json
    route_pairs = []
    for i in range(len(route_sequence) - 1):
        route_pairs.append((route_sequence[i], route_sequence[i+1]))
    
    data_source_issues = 0
    for i, (from_city, to_city) in enumerate(route_pairs):
        route_key = f"{from_city}->{to_city}"
        
        if route_key not in transport_data:
            data_source_issues += 1
    
    if data_source_issues > 0:
        warnings.append(f"{data_source_issues}段交通可能缺少准确数据")
    
    # ========== 6. 行程内容匹配度检查 ==========
    content_issues = 0
    for city in expected_cities:
        # 检查城市是否在攻略中
        if city not in destinations:
            content_issues += 1
    
    if content_issues > 0:
        warnings.append(f"{content_issues}个城市缺少攻略数据")
    
    # ========== 统计信息 ==========
    total_days = sum(city_days.values())
    num_cities = len(route_sequence)
    num_transports = len(transport_modes)
    
    # 提取交通时间
    transport_times = []
    for match in re.finditer(r'(\d+\.?\d*)h', ' '.join(transport_modes)):
        transport_times.append(float(match.group(1)))
    
    avg_transport = round(sum(transport_times) / len(transport_times), 2) if transport_times else 0
    
    # ========== 判断状态 ==========
    if issues:
        status = "error"
    elif len(warnings) >= 3:
        status = "warning"
    else:
        status = "ok"
    
    return {
        "status": status,
        "days": total_days,
        "cities": num_cities,
        "transports": num_transports,
        "avg_transport": avg_transport,
        "issues": issues,
        "warnings": warnings,
        "route_sequence": route_sequence,
        "city_days": dict(city_days)
    }

def main():
    print("🔍 完整版路线验证工具 - 格式检查 + 质量验证\n")
    print("📋 格式检查（6项）：")
    print("   • 交通时间显示错误")
    print("   • Day编号连续性")
    print("   • 命令行参数残留")
    print("   • 重复地名检查")
    print("   • 占位符残留")
    print("   • 过多0.00h中转点")
    print("\n✨ 质量验证（6大维度）：")
    print("   1. 路线顺序优化")
    print("   2. 起终点选择（区域hub + 别名匹配）")
    print("   3. 停留天数分配")
    print("   4. 交通方式合理性")
    print("   5. 数据来源准确性")
    print("   6. 行程内容匹配度\n")

    # 加载区域级hub配置
    region_hubs = load_region_hubs()

    stats = {"Europe": 0, "North_America": 0, "Oceania": 0, "Asia": 0}
    total_ok = 0
    total_warning = 0
    total_error = 0

    for region in ["Europe", "North_America", "Oceania", "Asia"]:
        routes_dir = os.path.join(BASE, "data", region, "generated_routes")
        if not os.path.exists(routes_dir):
            continue

        files = sorted([f for f in os.listdir(routes_dir) if f.endswith('.md')])
        stats[region] = len(files)

        print(f"\n{'='*70}")
        print(f"📍 {region} ({len(files)} 条路线)")
        if region in region_hubs:
            print(f"   Hub城市: {', '.join(region_hubs[region][:8])}" +
                  ("..." if len(region_hubs[region]) > 8 else ""))
        print(f"{'='*70}")

        for filename in files:
            result = verify_route_enhanced(region, filename, region_hubs)
            route_name = filename.replace('.md', '').replace('_+_', ' + ')
            
            if result["status"] == "ok":
                status_icon = "✅"
                total_ok += 1
            elif result["status"] == "warning":
                status_icon = "⚠️ "
                total_warning += 1
            else:
                status_icon = "❌"
                total_error += 1
            
            print(f"\n{status_icon} {route_name}")
            print(f"    天数: {result['days']} | "
                  f"城市: {result['cities']} | "
                  f"转场: {result['transports']}次 | "
                  f"平均交通: {result['avg_transport']}h")
            
            # 显示路线顺序
            if result['route_sequence']:
                print(f"    路线: {' → '.join(result['route_sequence'][:5])}" + 
                      ("..." if len(result['route_sequence']) > 5 else ""))
            
            # 显示各城市停留天数
            if result['city_days']:
                days_str = ', '.join([f"{c}:{d}天" for c, d in list(result['city_days'].items())[:3]])
                print(f"    停留: {days_str}" + ("..." if len(result['city_days']) > 3 else ""))
            
            # 显示问题
            if result.get('issues'):
                for issue in result['issues']:
                    print(f"    ❌ {issue}")
            
            if result.get('warnings'):
                for warning in result['warnings']:
                    print(f"    ⚠️  {warning}")
    
    print(f"\n{'='*70}")
    print(f"📊 验证结果汇总")
    print(f"{'='*70}")
    print(f"区域分布: Europe {stats['Europe']} | North_America {stats['North_America']} | "
          f"Oceania {stats['Oceania']} | Asia {stats['Asia']}")
    print(f"质量统计: ✅ {total_ok} 条 | ⚠️  {total_warning} 条 | ❌ {total_error} 条")
    print(f"{'='*70}\n")

if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""
智能推荐系统 + TravelEngine集成
方案A：基于内容推荐 + 完整路线生成
"""

import json
import os
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime
from src.core.route_planner import TravelEngine
from src.core.utils import load_json, REGIONS

def parse_season(season_str: str) -> List[int]:
    """解析最佳季节字符串，返回月份列表"""
    if "全年" in season_str:
        return list(range(1, 13))

    months = []
    import re
    # 解析 "6-8月" 格式
    patterns = re.findall(r'(\d+)-(\d+)月', season_str)
    for start, end in patterns:
        months.extend(range(int(start), int(end) + 1))

    # 解析单独月份
    single_months = re.findall(r'(\d+)月', season_str)
    for m in single_months:
        if int(m) not in months:
            months.append(int(m))

    return sorted(list(set(months))) if months else list(range(1, 13))

def calculate_season_score(best_season: str, target_month: int) -> float:
    """
    计算季节匹配分数
    - 在最佳季节内：+0.3
    - 全年可去：+0.1
    - 不在最佳季节：-0.2
    """
    valid_months = parse_season(best_season)

    if target_month in valid_months:
        if len(valid_months) == 12:  # 全年
            return 0.1
        else:  # 在最佳季节
            return 0.3
    else:  # 不在最佳季节
        return -0.2

def load_coordinates(base_dir=os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))):
    """加载所有区域的城市坐标"""
    all_coords = {}
    for region in REGIONS:
        coord_file = os.path.join(base_dir, "data", region, "city_coordinates.json")
        if os.path.exists(coord_file):
            coords = load_json(coord_file)
            all_coords.update(coords)
    return all_coords

def load_city_mapping(base_dir=os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))):
    """加载所有区域的城市映射（别名 -> 标准名）"""
    all_mapping = {}
    # 先加载根目录 mapping（如果有）
    root_mapping_file = os.path.join(base_dir, "city_mapping.json")
    if os.path.exists(root_mapping_file):
        all_mapping.update(load_json(root_mapping_file))

    # 再加载各区域的 mapping（区域优先）
    for region in REGIONS:
        mapping_file = os.path.join(base_dir, "data", region, "city_mapping.json")
        if os.path.exists(mapping_file):
            region_mapping = load_json(mapping_file)
            all_mapping.update(region_mapping)
    return all_mapping

def get_all_destinations(base_dir=os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))):
    """加载所有目的地数据"""
    dest_files = list(Path(base_dir).rglob("*_destinations.json"))
    coords = load_coordinates(base_dir)

    all_destinations = {}
    for file_path in dest_files:
        # 确定区域
        if "Asia" in str(file_path):
            region = "Asia"
        elif "North_America" in str(file_path):
            region = "North_America"
        elif "Europe" in str(file_path):
            region = "Europe"
        elif "Oceania" in str(file_path):
            region = "Oceania"
        else:
            continue

        # 从文件名提取国家信息（如"德国_destinations.json" -> ["德国"]）
        file_name = file_path.stem  # 获取不带扩展名的文件名
        countries = []
        if "_destinations" in file_name:
            country_part = file_name.replace("_destinations", "")
            # 处理组合国家名（如"奥地利克罗地亚" -> ["奥地利", "克罗地亚"]）
            # 简单启发式：常见国家名分割
            known_countries = ["德国", "法国", "意大利", "西班牙", "瑞士", "奥地利", "克罗地亚",
                             "荷兰", "比利时", "捷克", "匈牙利", "希腊", "葡萄牙", "土耳其",
                             "阿联酋", "埃及", "北欧", "加拿大", "美国西部", "美国东部中部", "美国", "日本", "澳大利亚", "新西兰",
                             "阿拉斯加加勒比海夏威夷", "阿拉斯加", "加勒比海", "夏威夷", "斐济"]
            for country in known_countries:
                if country in country_part:
                    countries.append(country)
            # 如果没匹配到任何已知国家，保留原始字符串
            if not countries:
                countries = [country_part]

        data = load_json(file_path)

        for dest_name, dest_data in data.items():
            days = len(dest_data.get('itinerary', []))

            # 获取坐标（优先hub_city，其次自身，支持模糊匹配）
            city_for_coord = dest_data.get('hub_city') or dest_name
            coord = coords.get(city_for_coord)

            # 如果没找到，尝试模糊匹配（去掉常见后缀）
            if not coord:
                for suffix in ['岛', '（8天环线）', '（阿维尼翁/马赛）']:
                    clean_name = city_for_coord.replace(suffix, '')
                    if clean_name in coords:
                        coord = coords[clean_name]
                        break

            # 如果还没找到，尝试部分匹配
            if not coord:
                for coord_city, coord_val in coords.items():
                    if coord_city in city_for_coord or city_for_coord in coord_city:
                        coord = coord_val
                        break

            # Fallback：为常见缺失坐标的目的地提供默认值
            if not coord:
                fallback_coords = {
                    '马略卡岛': [39.57, 2.65],  # 帕尔马
                    '挪威': [59.91, 10.75],  # 奥斯陆
                    '瑞典': [59.33, 18.07],  # 斯德哥尔摩
                    '芬兰': [60.17, 24.94],  # 赫尔辛基
                }
                for key, val in fallback_coords.items():
                    if key in dest_name:
                        coord = val
                        break

            all_destinations[dest_name] = {
                'region': region,
                'countries': countries,  # 新增：国家列表
                'days': days,
                'tags': dest_data.get('tags', {}),
                'best_season': dest_data.get('best_season', '全年'),
                'full_title': dest_data.get('full_title', dest_name),
                'loop_type': dest_data.get('loop_type'),
                'hub_city': dest_data.get('hub_city'),
                'end_city': dest_data.get('end_city'),
                'coordinates': coord  # [lat, lon] or None
            }

    return all_destinations

def recommend_destinations(
    region: str,
    tags: Optional[List[str]] = None,
    month: Optional[int] = None,
    min_days: Optional[int] = None,
    max_days: Optional[int] = None,
    countries: Optional[List[str]] = None,
    top_n: int = 20
) -> List[Dict]:
    """
    推荐目的地（第1步：筛选+打分）

    Args:
        region: 区域（必填）
        tags: 标签列表
        month: 出发月份
        min_days: 单个目的地最小天数
        max_days: 单个目的地最大天数
        countries: 国家列表（可选，如 ["德国", "奥地利"]）
        top_n: 返回前N个候选

    Returns:
        候选目的地列表，按分数降序
    """
    if month is None:
        month = datetime.now().month

    all_dests = get_all_destinations()
    candidates = []

    for dest_name, dest_info in all_dests.items():
        # 区域筛选（必须）
        if dest_info['region'] != region:
            continue

        # 国家筛选（可选）
        if countries:
            dest_countries = dest_info.get('countries', [])
            # 如果目的地的国家列表与用户指定的国家列表有交集，则通过筛选
            if not any(c in dest_countries for c in countries):
                continue

        # 天数筛选
        if min_days and dest_info['days'] < min_days:
            continue
        if max_days and dest_info['days'] > max_days:
            continue

        # 标签打分
        tag_score = 0
        matched_tags = {}
        if tags:
            for tag in tags:
                if tag in dest_info['tags']:
                    weight = dest_info['tags'][tag]
                    tag_score += weight
                    matched_tags[tag] = weight

            # 没有匹配任何标签，跳过
            if tag_score == 0:
                continue
        else:
            # 没指定标签，使用所有标签总分
            tag_score = sum(dest_info['tags'].values()) if dest_info['tags'] else 0
            matched_tags = dest_info['tags']

        # 季节打分
        season_score = calculate_season_score(dest_info['best_season'], month)

        # 总分
        total_score = tag_score + season_score

        candidates.append({
            'name': dest_name,
            'days': dest_info['days'],
            'tag_score': round(tag_score, 2),
            'season_score': round(season_score, 2),
            'total_score': round(total_score, 2),
            'matched_tags': matched_tags,
            'best_season': dest_info['best_season'],
            'loop_type': dest_info['loop_type'],
            'hub_city': dest_info['hub_city'],
            'coordinates': dest_info.get('coordinates')
        })

    # 按总分降序
    candidates.sort(key=lambda x: x['total_score'], reverse=True)
    return candidates[:top_n]

def haversine_distance(coord1, coord2):
    """计算两个坐标之间的距离（公里）"""
    if not coord1 or not coord2:
        return 9999  # 无坐标时返回很大的距离

    import math
    lat1, lon1 = coord1
    lat2, lon2 = coord2

    R = 6371  # 地球半径（公里）
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)

    a = (math.sin(dlat/2)**2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlon/2)**2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

    return R * c

def select_destinations_by_days(candidates: List[Dict], total_days: int) -> List[str]:
    """
    从候选列表中选择目的地组合，使总天数接近目标
    优先选择地理位置相近的目的地，避免东跑西颠

    Args:
        candidates: 候选目的地列表
        total_days: 目标总天数

    Returns:
        选中的目的地名称列表
    """
    if not candidates:
        return []

    selected = []
    selected_coords = []  # 已选目的地的坐标
    current_days = 0
    remaining = candidates.copy()

    # 第一步：选择分数最高的作为起点
    first = remaining[0]
    if current_days + first['days'] <= total_days:
        selected.append(first['name'])
        selected_coords.append(first.get('coordinates'))
        current_days += first['days']
        remaining.remove(first)

    # 第二步：贪心选择：优先选择距离最近且分数较高的
    # 使用三个阶段：严格距离限制 → 放宽限制 → 完全忽略距离
    for phase in [1, 2, 3]:
        # Phase 1: 严格距离惩罚（优先地理聚类）
        # Phase 2: 放宽距离惩罚
        # Phase 3: 完全忽略距离（纯分数排序）
        if phase == 1:
            distance_weight = 1.0
        elif phase == 2:
            distance_weight = 0.3
        else:  # phase == 3
            distance_weight = 0.0  # 完全忽略距离


        while remaining and current_days < total_days * 0.9:
            best_candidate = None
            best_score = -999999

            for cand in remaining:
                # 天数检查
                if current_days + cand['days'] > total_days:
                    continue

                # 计算综合分数：原始分数 - 距离惩罚
                if distance_weight > 0:
                    valid_coords = [sc for sc in selected_coords if sc]
                    if valid_coords:
                        min_distance = min([haversine_distance(cand.get('coordinates'), sc)
                                           for sc in valid_coords])
                    else:
                        min_distance = 0

                    # 距离惩罚
                    if min_distance < 500:
                        distance_penalty = 0
                    elif min_distance < 1500:
                        distance_penalty = (min_distance - 500) / 200
                    else:
                        distance_penalty = 5 + (min_distance - 1500) / 500

                    combined_score = cand['total_score'] - (distance_penalty * distance_weight)
                else:
                    combined_score = cand['total_score']  # Phase 3: 纯分数

                if combined_score > best_score:
                    best_score = combined_score
                    best_candidate = cand

            if not best_candidate:
                break

            # 选中这个目的地
            selected.append(best_candidate['name'])
            selected_coords.append(best_candidate.get('coordinates'))
            current_days += best_candidate['days']
            remaining.remove(best_candidate)

        # 如果已经选够了，不需要进入下一阶段
        if current_days >= total_days * 0.9:
            break

    return selected

def recommend_route(
    region: str,
    total_days: int,
    tags: Optional[List[str]] = None,
    month: Optional[int] = None,
    start_city: Optional[str] = None,
    countries: Optional[List[str]] = None,
    base_dir: str = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
) -> Dict:
    """
    完整推荐流程：筛选 + 路线生成

    Args:
        region: 区域
        total_days: 总天数
        tags: 标签
        month: 月份
        start_city: 起点城市（可选）
        countries: 国家列表（可选）
        base_dir: 数据目录

    Returns:
        包含候选列表、选中目的地、完整路线的字典
    """
    # 第1步：推荐候选目的地
    print(f"\n{'='*80}")
    print(f"🔍 第1步：筛选候选目的地...")
    if countries:
        print(f"   国家筛选：{' + '.join(countries)}")
    if tags:
        print(f"   标签筛选：{' + '.join(tags)}")
    print(f"{'='*80}")

    candidates = recommend_destinations(
        region=region,
        tags=tags,
        month=month,
        countries=countries,
        top_n=20
    )

    if not candidates:
        return {
            'success': False,
            'message': '没有找到符合条件的目的地'
        }

    print(f"找到 {len(candidates)} 个候选目的地")
    for i, c in enumerate(candidates[:5], 1):
        season_icon = "✅" if c['season_score'] > 0 else "⚠️"
        print(f"  {i}. {c['name']} - {c['days']}天 - 评分:{c['total_score']} {season_icon}")

    # 第2步：选择目的地组合（方案1：推荐TOP目的地，不强制凑天数）
    print(f"\n{'='*80}")
    print(f"🎯 第2步：推荐最佳目的地（参考天数：{total_days}天）...")
    print(f"{'='*80}")

    # 智能选择：基于分数选TOP目的地，天数作为参考
    # 策略：选择评分最高的目的地，总天数在 total_days ±30% 范围内
    min_days = int(total_days * 0.7)  # 最少70%
    max_days = int(total_days * 1.3)  # 最多130%

    selected_info = []
    selected_names = []
    cumulative_days = 0

    for candidate in candidates:
        # 如果加上这个目的地会超过最大天数，跳过
        if cumulative_days + candidate['days'] > max_days:
            continue

        selected_info.append(candidate)
        selected_names.append(candidate['name'])
        cumulative_days += candidate['days']

        # 达到目标天数范围内，停止
        if cumulative_days >= min_days:
            break

    # 如果选了的目的地少于3个，继续补充（不管天数）
    if len(selected_info) < 3:
        for candidate in candidates:
            if candidate['name'] not in selected_names:
                selected_info.append(candidate)
                selected_names.append(candidate['name'])
                cumulative_days += candidate['days']
                if len(selected_info) >= 5:  # 最多5个
                    break

    if not selected_names:
        return {
            'success': False,
            'message': '没有找到合适的推荐目的地'
        }

    actual_days = sum(c['days'] for c in selected_info)

    print(f"已推荐 {len(selected_names)} 个目的地：")
    for c in selected_info:
        print(f"  ✓ {c['name']} ({c['days']}天) - 评分:{c['total_score']}")
    print(f"总天数：{actual_days}天（参考：{total_days}天）")

    # 第3步：调用TravelEngine生成完整路线
    print(f"\n{'='*80}")
    print(f"🗺️  第3步：生成完整路线（TravelEngine）...")
    print(f"{'='*80}")

    try:
        engine = TravelEngine(base_dir)

        # generated_routes（返回markdown文本）
        route_text = engine.plan(
            name=f"{region}{total_days}天推荐路线",
            raw_nodes=selected_names,
            start_node=start_city,
            region=region
        )

        result = {
            'success': True,
            'candidates': candidates[:10],
            'selected': selected_info,
            'route_text': route_text,
            'total_days': actual_days,
            'target_days': total_days,
            'region': region,
            'month': month or datetime.now().month
        }

        # 自动保存 JSON 元数据
        output_dir = f"{base_dir}/data/{region}/generated_routes"
        os.makedirs(output_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = os.path.join(output_dir, f"推荐结果_{timestamp}.json")

        save_data = {
            'region': result['region'],
            'month': result['month'],
            'total_days': result['total_days'],
            'target_days': result['target_days'],
            'candidates': result['candidates'],
            'selected': result['selected']
        }

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(save_data, f, ensure_ascii=False, indent=2)

        result['json_file'] = output_file
        return result

    except Exception as e:
        return {
            'success': False,
            'message': f'路线生成失败: {str(e)}',
            'candidates': candidates[:10],
            'selected': selected_info
        }

def print_result(result: Dict):
    """打印推荐结果"""
    if not result.get('success'):
        print(f"\n❌ {result.get('message', '推荐失败')}")
        return

    print(f"\n{'='*80}")
    print(f"✅ 推荐完成！")
    print(f"{'='*80}")
    print(f"区域: {result['region']}")
    print(f"月份: {result['month']}月")
    print(f"总天数: {result['total_days']}/{result['target_days']}天")
    print(f"包含目的地: {len(result['selected'])}个")

    print(f"\n📍 路线详情：")
    print(f"{'='*80}")

    # TravelEngine.plan()返回的是markdown文本
    if result.get('route_text'):
        print(result['route_text'])

    # 显示保存的文件路径
    if result.get('json_file'):
        print(f"\n💾 推荐元数据已保存到: {result['json_file']}")
        print(f"💾 完整路线已由 TravelEngine 保存为 .md 和 .csv 格式")

def main():
    import argparse

    parser = argparse.ArgumentParser(description='智能旅行推荐系统')

    # 必填参数
    parser.add_argument('-r', '--region', required=True,
                        choices=['Asia', 'North_America', 'Europe', 'Oceania'],
                        help='区域（必填）')
    parser.add_argument('--days', type=int, nargs='*',
                        help='总行程天数（可选）。不填则给出7/10/14天三个方案；填1个数字指定天数；填2个数字指定范围（如：--days 10 14）')

    # 可选参数
    parser.add_argument('-t', '--tags', nargs='+',
                        choices=['人文历史', '自然风光', '海岛海滨', '现代都市',
                                '户外探险', '小镇村落', '亲子家庭'],
                        help='标签筛选（可多选）')
    parser.add_argument('-c', '--countries', nargs='+',
                        help='国家筛选（可多选），如：德国 奥地利')
    parser.add_argument('-m', '--month', type=int, choices=range(1, 13),
                        help='出发月份（1-12），默认当前月份')
    parser.add_argument('--start', help='起点城市（可选）')

    args = parser.parse_args()

    # 处理天数参数
    if not args.days or len(args.days) == 0:
        # 不填天数：给出 7/10/14 天三个方案
        day_options = [7, 10, 14]
        print(f"\n{'='*80}")
        print(f"💡 未指定天数，将为您推荐 3 个不同时长的方案")
        print(f"{'='*80}\n")

        for i, days in enumerate(day_options, 1):
            print(f"\n{'#'*80}")
            print(f"# 方案 {i}: {days}天行程")
            print(f"{'#'*80}")

            result = recommend_route(
                region=args.region,
                total_days=days,
                tags=args.tags,
                month=args.month,
                start_city=args.start,
                countries=args.countries
            )
            print_result(result)

    elif len(args.days) == 1:
        # 填1个天数：执行单次推荐
        result = recommend_route(
            region=args.region,
            total_days=args.days[0],
            tags=args.tags,
            month=args.month,
            start_city=args.start,
            countries=args.countries
        )
        print_result(result)

    elif len(args.days) == 2:
        # 填2个天数：范围推荐，尝试最小/中间/最大三个方案
        min_days, max_days = min(args.days), max(args.days)
        mid_days = (min_days + max_days) // 2
        day_options = [min_days, mid_days, max_days] if mid_days not in [min_days, max_days] else [min_days, max_days]

        print(f"\n{'='*80}")
        print(f"💡 天数范围：{min_days}-{max_days}天，将尝试 {len(day_options)} 个方案")
        print(f"{'='*80}\n")

        for i, days in enumerate(day_options, 1):
            print(f"\n{'#'*80}")
            print(f"# 方案 {i}: {days}天行程（{min_days}-{max_days}天范围内）")
            print(f"{'#'*80}")

            result = recommend_route(
                region=args.region,
                total_days=days,
                tags=args.tags,
                month=args.month,
                start_city=args.start,
                countries=args.countries
            )
            print_result(result)
    else:
        print("❌ 错误：--days 参数最多接受2个数字（范围）")
        sys.exit(1)

    # 不再需要单独的 print_result 和保存逻辑，已经在 recommend_route 内部处理

if __name__ == "__main__":
    main()

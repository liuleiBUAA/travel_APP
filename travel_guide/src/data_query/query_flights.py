#!/usr/bin/env python3
"""
通用航班查询工具 - 支持全球所有区域
用法：
  python query_flights.py --region Europe --from 巴塞罗那 --to 塞维利亚
  python query_flights.py --region North_America --from 旧金山 --to 洛杉矶
  python query_flights.py --region Oceania --from 悉尼 --to 墨尔本
  python query_flights.py --region Asia --from 东京 --to 大阪
  python query_flights.py --region Europe --batch  # 批量模式：从脚本底部读取列表
"""
import json
import time
import re
import os
import argparse
from playwright.sync_api import sync_playwright

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CITY_CONFIG_FILE = os.path.join(BASE_DIR, 'city_names_config.json')

# 加载城市英文名配置
with open(CITY_CONFIG_FILE, 'r', encoding='utf-8') as f:
    CITY_NAMES = json.load(f)


def get_region_routes_file(region):
    """获取区域的路线数据文件路径"""
    region_dir = os.path.join(BASE_DIR, "data", region)
    return os.path.join(region_dir, 'transport_routes.json')


def query_flight(page, from_city, to_city, region):
    """查询两城市之间的直飞航班信息"""
    try:
        city_en = CITY_NAMES.get(region, {})
        from_en = city_en.get(from_city, from_city)
        to_en = city_en.get(to_city, to_city)

        # 只取英文名第一个词用于匹配
        from_en_short = from_en.split()[0]
        to_en_short = to_en.split()[0]

        url = f"https://www.google.com/travel/flights?q=Flights%20from%20{from_en}%20to%20{to_en}&hl=en"
        page.goto(url, wait_until='domcontentloaded', timeout=20000)
        page.wait_for_timeout(6000)

        labels = page.evaluate("""() => {
            const cards = document.querySelectorAll('div.JMc5Xc');
            return Array.from(cards).map(c => c.getAttribute('aria-label')).filter(Boolean);
        }""")

        nonstop = [l for l in labels if 'Nonstop' in l]
        if not nonstop:
            return None

        # 提取飞行时间（支持 "X hr Y min" 和 "Y min" 格式）
        times = []
        for l in nonstop:
            m = re.search(r'Total duration (?:(\d+) hr )?(\d+) min', l)
            if m:
                hours = int(m.group(1)) if m.group(1) else 0
                minutes = int(m.group(2))
                times.append(hours + minutes / 60)

        # 只统计从出发城市到目的地的单程班次
        dep_times = []
        for l in nonstop:
            if from_en_short.lower() in l.lower() and to_en_short.lower() in l.lower():
                m = re.search(r'Leaves .+ at (\d+:\d+ [AP]M)', l)
                if m:
                    dep_times.append(m.group(1))

        unique_times = list(set(dep_times))

        return {
            'flight_time': round(min(times), 2) if times else None,
            'frequency': len(unique_times)
        }
    except Exception as e:
        print(f"    ⚠️ 查询失败: {e}", flush=True)
        return None


def update_routes_file(region, route_key, data):
    """更新或新增路线数据到对应区域的文件"""
    routes_file = get_region_routes_file(region)

    # 读取现有数据
    if os.path.exists(routes_file):
        with open(routes_file, 'r', encoding='utf-8') as f:
            routes = json.load(f)
    else:
        routes = {}

    # 更新数据
    if route_key not in routes:
        routes[route_key] = {}

    routes[route_key].update({
        'flight_time_hours': data['flight_time'],
        'flight_frequency_per_day': data['frequency'],
        'is_nonstop': True
    })

    # 保存
    with open(routes_file, 'w', encoding='utf-8') as f:
        json.dump(routes, f, ensure_ascii=False, indent=2)

    return routes_file


def main():
    parser = argparse.ArgumentParser(description='通用航班查询工具')
    parser.add_argument('--region', required=True, choices=['Europe', 'North_America', 'Oceania', 'Asia'],
                        help='查询的区域')
    parser.add_argument('--from', dest='from_city', help='出发城市（中文名）')
    parser.add_argument('--to', dest='to_city', help='到达城市（中文名）')
    parser.add_argument('--batch', action='store_true',
                        help='批量模式：从脚本底部的routes_to_query列表读取')

    args = parser.parse_args()
    region = args.region

    # ============================================================
    # 批量查询列表（--batch 模式时使用）
    # 在这里填入要查询的路线，格式：("出发城市", "到达城市")
    # ============================================================
    routes_to_query = [
        # 日本远距离航线
        ("东京", "北海道"),
        ("大阪", "北海道"),
        ("大阪", "冲绳"),
        ("东京", "石垣岛"),
        ("冲绳", "石垣岛"),
        ("北海道", "东京"),
        ("北海道", "大阪"),
        ("冲绳", "大阪"),
        ("石垣岛", "东京"),
        ("石垣岛", "冲绳"),
    ]

    # 单条查询模式
    if not args.batch:
        if not args.from_city or not args.to_city:
            print("❌ 单条查询模式需要 --from 和 --to 参数")
            return
        routes_to_query = [(args.from_city, args.to_city)]

    if not routes_to_query:
        print("❌ 请在脚本底部的 routes_to_query 列表中添加要查询的路线")
        return

    print(f"\n🌍 开始查询 {region} 区域航班信息")
    print(f"📋 共 {len(routes_to_query)} 条路线\n")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        for i, (from_city, to_city) in enumerate(routes_to_query, 1):
            route_key = f"{from_city}->{to_city}"
            print(f"[{i}/{len(routes_to_query)}] 查询 {route_key}...", end=' ', flush=True)

            result = query_flight(page, from_city, to_city, region)

            if result and result['flight_time']:
                print(f"✅ {result['flight_time']}h, {result['frequency']}班/天")
                routes_file = update_routes_file(region, route_key, result)
                print(f"    💾 已更新到: {routes_file}")
            else:
                print(f"❌ 无直飞")

            time.sleep(2)  # 避免请求过快

        browser.close()

    print(f"\n✅ 查询完成！")


if __name__ == '__main__':
    main()

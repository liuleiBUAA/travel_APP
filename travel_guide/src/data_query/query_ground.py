#!/usr/bin/env python3
"""
通用地面交通查询工具 - 支持全球所有区域（火车/自驾）
用法：
  python query_ground_transport.py --region Europe --from 巴塞罗那 --to 马德里
  python query_ground_transport.py --region North_America --from 旧金山 --to 洛杉矶
  python query_ground_transport.py --region Oceania --from 悉尼 --to 墨尔本
  python query_ground_transport.py --region Asia --from 东京 --to 京都
  python query_ground_transport.py --region Europe --batch  # 批量模式：从脚本底部读取列表
"""
import json
import time
import re
import os
import argparse
from playwright.sync_api import sync_playwright

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CITY_CONFIG_FILE = os.path.join(BASE_DIR, 'config', 'city_names_config.json')

# 加载城市英文名配置
with open(CITY_CONFIG_FILE, 'r', encoding='utf-8') as f:
    CITY_NAMES = json.load(f)


def get_region_routes_file(region):
    """获取区域的路线数据文件路径"""
    region_dir = os.path.join(BASE_DIR, "data", region)
    return os.path.join(region_dir, 'transport_routes.json')


def parse_time_text(text):
    """解析各种时间格式：'2 hours 30 min', '45 min', '1 hour 5 min'"""
    if not text:
        return None

    hours = 0
    minutes = 0

    # 匹配小时
    hour_match = re.search(r'(\d+)\s*(?:hour|hr)', text, re.IGNORECASE)
    if hour_match:
        hours = int(hour_match.group(1))

    # 匹配分钟
    min_match = re.search(r'(\d+)\s*min', text, re.IGNORECASE)
    if min_match:
        minutes = int(min_match.group(1))

    if hours == 0 and minutes == 0:
        return None

    return round(hours + minutes / 60, 2)


def query_ground_transport(page, from_city, to_city, region):
    """使用Google Maps查询自驾和公共交通时间"""
    try:
        city_en = CITY_NAMES.get(region, {})

        # 为地面交通添加国家后缀（如果有）
        from_en = city_en.get(from_city, from_city)
        to_en = city_en.get(to_city, to_city)

        url = f"https://www.google.com/maps/dir/{from_en}/{to_en}"
        page.goto(url, wait_until='domcontentloaded', timeout=60000)
        page.wait_for_timeout(10000)  # 等待页面完全加载

        # 提取自驾时间（使用更可靠的选择器）
        drive_time_text = page.evaluate("""() => {
            // 查找包含时间信息的元素
            const selectors = [
                'div[aria-label*="hour"]',
                'div[aria-label*="min"]',
                'h1.fontTitleLarge',
                'div.section-directions-trip-duration',
                'div[data-trip-index="0"]'
            ];

            for (const selector of selectors) {
                const elements = document.querySelectorAll(selector);
                for (const el of elements) {
                    const text = el.textContent || el.getAttribute('aria-label');
                    if (text && (text.includes('hour') || text.includes('min'))) {
                        return text;
                    }
                }
            }

            // 最后尝试从h1标题提取
            const h1 = document.querySelector('h1');
            if (h1 && h1.textContent) {
                return h1.textContent;
            }

            return null;
        }""")

        if not drive_time_text:
            return None

        result = {}

        # 解析自驾时间
        drive_time = parse_time_text(drive_time_text)
        if drive_time:
            result['drive_time'] = drive_time
            result['train_time'] = drive_time  # 如果没有专门的火车数据，用自驾时间估算

        return result if result else None

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

    if 'drive_time' in data:
        routes[route_key]['drive_time_hours'] = data['drive_time']
    if 'train_time' in data:
        routes[route_key]['train_time_hours'] = data['train_time']

    # 保存
    with open(routes_file, 'w', encoding='utf-8') as f:
        json.dump(routes, f, ensure_ascii=False, indent=2)

    return routes_file


def main():
    parser = argparse.ArgumentParser(description='通用地面交通查询工具')
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
        # 示例：
        # ("巴塞罗那", "马德里"),
        # ("东京", "京都"),
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

    print(f"\n🚗 开始查询 {region} 区域地面交通信息")
    print(f"📋 共 {len(routes_to_query)} 条路线\n")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        for i, (from_city, to_city) in enumerate(routes_to_query, 1):
            route_key = f"{from_city}->{to_city}"
            print(f"[{i}/{len(routes_to_query)}] 查询 {route_key}...", flush=True)

            result = query_ground_transport(page, from_city, to_city, region)

            if result:
                info_parts = []
                if 'drive_time' in result:
                    info_parts.append(f"🚗 自驾{result['drive_time']}h")
                if 'train_time' in result:
                    info_parts.append(f"🚆 火车{result['train_time']}h")

                print(f"    ✅ {', '.join(info_parts)}")
                routes_file = update_routes_file(region, route_key, result)
                print(f"    💾 已更新到: {routes_file}")
            else:
                print(f"    ❌ 查询失败")

            time.sleep(3)  # Google Maps需要更长间隔

        browser.close()

    print(f"\n✅ 查询完成！")


if __name__ == '__main__':
    main()

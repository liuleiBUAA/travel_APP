#!/usr/bin/env python3
"""命令行入口：python -m src.core.cli 城市A 城市B ..."""

import os
import sys

from src.core.utils import load_json, load_config
from src.core.route_planner import TravelEngine


def calculate_total_travel_time(engine, city, other_cities):
    total = 0
    for other in other_cities:
        if other == city:
            continue
        route = engine._lookup_edge(city, other)
        if route:
            if route.get('flight_time_hours'):
                total += route['flight_time_hours']
            elif route.get('train_time_hours'):
                total += route['train_time_hours']
            elif route.get('drive_time_hours'):
                total += route['drive_time_hours']
            else:
                total += 999
        else:
            total += 999
    return total


def pick_smart_endpoint(engine, nodes, major_hubs, exclude=None, role="起点"):
    """智能选择起点或终点"""
    candidates = [n for n in nodes if n in major_hubs and n != exclude]
    if not candidates:
        return None

    if len(candidates) == 1:
        city = candidates[0]
    else:
        min_time, city = float('inf'), candidates[0]
        for c in candidates:
            t = calculate_total_travel_time(engine, c, nodes)
            if t < min_time:
                min_time, city = t, c

    print(f"✓ 智能选择{role}：{city}（国际门户城市，总交通时间最优）")
    return city


def check_gateway(engine, city, major_hubs, role):
    if not city or not major_hubs:
        return
    if city in major_hubs:
        return
    print(f"⚠️  {role}城市「{city}」可能无中国直飞航班")
    mapped = engine.mapping.get(city, city)
    hubs = engine.dependencies.get(mapped, engine.dependencies.get(city, []))
    hub_suggestions = [h for h in hubs if h in major_hubs]
    if hub_suggestions:
        print(f"   建议从以下城市出发/结束：{' 或 '.join(hub_suggestions)}")


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    base_dir = os.path.dirname(os.path.dirname(script_dir))
    if not os.path.exists(os.path.join(base_dir, "data", "Europe")):
        base_dir = os.path.expanduser("~/Downloads/travel_guide")

    engine = TravelEngine(base_dir)
    cfg = load_config(base_dir)

    # 解析命令行参数
    if len(sys.argv) > 1:
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
        print("示例: python -m src.core.cli 巴黎 阿姆斯特丹 布鲁塞尔")
        sys.exit(1)

    start_city = cfg.get("start_city") or None
    end_city = cfg.get("end_city") or None
    force_order = cfg.get("force_order", False)
    region = cfg.get("region") or None

    # 加载主要枢纽
    MAJOR_HUBS = engine._load_major_hubs()

    # 智能选择起终点
    if not start_city and nodes:
        start_city = pick_smart_endpoint(engine, nodes, MAJOR_HUBS, role="起点")
        if not start_city:
            start_city = nodes[0]
            print(f"ℹ️  起点：{start_city}（默认第一个城市）")

    if not end_city and nodes:
        end_city = pick_smart_endpoint(engine, nodes, MAJOR_HUBS, exclude=start_city, role="终点")
        if not end_city:
            if cfg.get('force_gateway_departure', False):
                end_city = None
                print(f"ℹ️  终点：自动优化（最终从{start_city}飞离）")
            else:
                end_city = nodes[-1] if nodes[-1] != start_city else (nodes[-2] if len(nodes) > 1 else None)
                if end_city:
                    print(f"ℹ️  终点：{end_city}（默认最后一个城市）")

    check_gateway(engine, start_city or (nodes[0] if nodes else None), MAJOR_HUBS, "出发")
    check_gateway(engine, end_city or (nodes[-1] if nodes else None), MAJOR_HUBS, "结束")

    print(engine.plan(name, nodes, start_node=start_city, end_node=end_city,
                      force_order=force_order, region=region))


if __name__ == "__main__":
    main()

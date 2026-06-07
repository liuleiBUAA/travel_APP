#!/usr/bin/env python3
"""
日本交通数据填充工具
直接使用已知的新干线/JR时刻表数据，避免Google Maps查询不准确的问题
数据来源：JR官网、新干线时刻表
"""
import json
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ROUTES_FILE = os.path.join(BASE_DIR, "data", "Asia", "transport_routes.json")

# 日本核心铁路交通数据（基于真实时刻表）
JAPAN_TRAIN_DATA = {
    # ========== 东海道新干线（东京-大阪黄金线）==========
    "东京->大阪": {
        "train_time_hours": 2.5,  # のぞみ号最快2小时30分
        "drive_time_hours": 6.5,
        "note": "东海道新干线のぞみ，每15分钟一班"
    },
    "大阪->东京": {
        "train_time_hours": 2.5,
        "drive_time_hours": 6.5,
        "note": "东海道新干线のぞみ"
    },
    "东京->京都": {
        "train_time_hours": 2.2,  # のぞみ号2小时15分
        "drive_time_hours": 6.0,
        "note": "东海道新干线のぞみ"
    },
    "京都->东京": {
        "train_time_hours": 2.2,
        "drive_time_hours": 6.0,
        "note": "东海道新干线のぞみ"
    },

    # ========== 关西圈短途（大阪-京都-奈良）==========
    "大阪->京都": {
        "train_time_hours": 0.25,  # 新干线15分钟
        "drive_time_hours": 0.75,
        "note": "东海道新干线，或JR京都线30分钟"
    },
    "京都->大阪": {
        "train_time_hours": 0.25,
        "drive_time_hours": 0.75,
        "note": "东海道新干线"
    },
    "大阪->奈良": {
        "train_time_hours": 0.75,  # 近铁奈良线快速急行45分钟
        "drive_time_hours": 0.67,
        "note": "近铁奈良线（难波站出发）或JR大和路线"
    },
    "奈良->大阪": {
        "train_time_hours": 0.75,
        "drive_time_hours": 0.67,
        "note": "近铁奈良线"
    },
    "京都->奈良": {
        "train_time_hours": 0.75,  # JR奈良线45分钟
        "drive_time_hours": 0.75,
        "note": "JR奈良线（京都站出发）或近铁京都线"
    },
    "奈良->京都": {
        "train_time_hours": 0.75,
        "drive_time_hours": 0.75,
        "note": "JR奈良线"
    },

    # ========== 北海道路线（需要航班+内部交通）==========
    # 注：东京/大阪到北海道主要靠航班，北海道内部用JR

    # ========== 冲绳路线（只能航班）==========
    # 注：本州到冲绳只能航班
}

def update_routes_file():
    """更新或创建Asia区域的交通路线文件"""

    # 读取现有数据
    if os.path.exists(ROUTES_FILE):
        with open(ROUTES_FILE, 'r', encoding='utf-8') as f:
            routes = json.load(f)
    else:
        routes = {}

    # 统计
    updated = 0
    added = 0

    print("🚄 开始填充日本铁路交通数据\n")

    for route_key, data in JAPAN_TRAIN_DATA.items():
        if route_key in routes:
            # 更新现有路线
            old_train = routes[route_key].get('train_time_hours')
            routes[route_key].update({
                'train_time_hours': data['train_time_hours'],
                'drive_time_hours': data.get('drive_time_hours')
            })

            if old_train != data['train_time_hours']:
                print(f"✏️  更新 {route_key}")
                print(f"    旧数据: {old_train}h → 新数据: {data['train_time_hours']}h")
                print(f"    备注: {data.get('note', '')}\n")
                updated += 1
            else:
                print(f"✅ 保持 {route_key}: {data['train_time_hours']}h")
        else:
            # 新增路线
            routes[route_key] = {
                'train_time_hours': data['train_time_hours'],
                'drive_time_hours': data.get('drive_time_hours')
            }
            print(f"➕ 新增 {route_key}: {data['train_time_hours']}h")
            print(f"    备注: {data.get('note', '')}\n")
            added += 1

    # 保存
    with open(ROUTES_FILE, 'w', encoding='utf-8') as f:
        json.dump(routes, f, ensure_ascii=False, indent=2)

    print(f"\n" + "="*60)
    print(f"✅ 数据填充完成！")
    print(f"📊 统计：")
    print(f"   - 新增路线：{added} 条")
    print(f"   - 更新路线：{updated} 条")
    print(f"   - 总路线数：{len(routes)} 条")
    print(f"💾 已保存到: {ROUTES_FILE}")
    print("="*60)

if __name__ == '__main__':
    update_routes_file()

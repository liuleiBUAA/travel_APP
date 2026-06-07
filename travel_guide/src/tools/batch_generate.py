#!/usr/bin/env python3
"""
批量生成经典旅游路线 - 从classic_routes.json读取配置
"""
import subprocess
import time
import json
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ROUTES_CONFIG_FILE = os.path.join(BASE_DIR, "config", "classic_routes.json")
CONFIG_FILE = os.path.join(BASE_DIR, "config", "config.json")

def load_routes_config():
    """加载路线配置"""
    with open(ROUTES_CONFIG_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def generate_route(route_info, global_config, index, total):
    """生成单条路线"""
    name = route_info['name']
    region = route_info['region']
    cities = route_info['cities']
    route_config = route_info.get('config', {})

    print(f"\n{'='*60}")
    print(f"[{index}/{total}] 生成: {name}")
    print(f"区域: {region}")
    print(f"目的地: {' → '.join(cities)}")
    print(f"{'='*60}")

    # 合并配置：global_config + route特定config
    config = global_config.copy()
    config.update(route_config)
    config['region'] = region
    config['destinations'] = cities

    # 临时写入config.json
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

    try:
        # 调用route_planner.py（不传参数，从config.json读取）
        result = subprocess.run(
            ['python3', 'src/core/route_planner.py'],
            cwd=BASE_DIR,
            capture_output=True,
            text=True,
            timeout=60
        )

        if result.returncode == 0:
            print(f"✅ {name} 生成成功")
            if result.stdout:
                for line in result.stdout.split('\n'):
                    if '已保存到' in line:
                        print(f"   {line.strip()}")
        else:
            print(f"❌ {name} 生成失败")
            if result.stderr:
                print(f"   错误: {result.stderr[:300]}")

        return result.returncode == 0

    except subprocess.TimeoutExpired:
        print(f"⏱️ {name} 超时")
        return False
    except Exception as e:
        print(f"❌ {name} 异常: {e}")
        return False

def main():
    routes_config = load_routes_config()
    global_config = routes_config['global_config']
    routes = routes_config['routes']

    print(f"🚀 开始批量生成{len(routes)}条经典旅游路线")
    print(f"全局配置: {json.dumps(global_config, ensure_ascii=False)}\n")

    success = 0
    failed = 0
    start_time = time.time()

    for i, route_info in enumerate(routes, 1):
        if generate_route(route_info, global_config, i, len(routes)):
            success += 1
        else:
            failed += 1
        time.sleep(1)

    elapsed = time.time() - start_time

    print(f"\n{'='*60}")
    print(f"📊 生成完成统计")
    print(f"{'='*60}")
    print(f"✅ 成功: {success} 条")
    print(f"❌ 失败: {failed} 条")
    print(f"⏱️  耗时: {elapsed:.1f}秒")
    print(f"{'='*60}")

if __name__ == '__main__':
    main()

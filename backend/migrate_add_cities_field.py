#!/usr/bin/env python3
"""
数据库迁移：为 companions 表添加 cities 字段并填充现有数据

运行方式：
    python3 migrate_add_cities_field.py
"""

import sys
import json
from pathlib import Path

# 添加 backend 到路径
sys.path.insert(0, str(Path(__file__).parent))

from database import get_db
from models import Companion
from sqlalchemy import text


def migrate():
    """执行迁移"""
    db = next(get_db())

    try:
        print("🔧 开始迁移：添加 cities 字段...")

        # 1. 检查字段是否已存在
        result = db.execute(text("PRAGMA table_info(companions)"))
        columns = [row[1] for row in result]

        if 'cities' not in columns:
            print("✅ 添加 cities 字段...")
            db.execute(text("ALTER TABLE companions ADD COLUMN cities VARCHAR(500)"))
            db.commit()
            print("✅ 字段添加成功")
        else:
            print("ℹ️  cities 字段已存在，跳过添加")

        # 2. 为现有数据填充 cities 字段
        print("🔄 填充现有数据的 cities 字段...")
        companions = db.query(Companion).filter(
            (Companion.cities == None) | (Companion.cities == '')
        ).all()

        updated_count = 0
        for companion in companions:
            try:
                route = json.loads(companion.route_json)
                cities_list = route.get('cities', [])
                if cities_list:
                    companion.cities = ','.join(cities_list)
                    updated_count += 1
            except Exception as e:
                print(f"⚠️  处理 companion {companion.id} 失败: {e}")

        db.commit()
        print(f"✅ 已更新 {updated_count} 条记录")

        # 3. 创建索引
        print("📊 创建索引...")
        try:
            db.execute(text("CREATE INDEX IF NOT EXISTS idx_companions_cities ON companions(cities)"))
            db.commit()
            print("✅ 索引创建成功")
        except Exception as e:
            print(f"ℹ️  索引可能已存在: {e}")

        print("✅ 迁移完成！")

    except Exception as e:
        print(f"❌ 迁移失败: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    migrate()

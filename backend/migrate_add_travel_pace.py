#!/usr/bin/env python3
"""
数据库迁移：users / companions 表添加「旅游节奏」字段 travel_pace

- users.travel_pace       旅行名片上的节奏偏好（特种兵/适中/慢悠悠/不限）
- companions.travel_pace  单条找搭子行程的节奏（同上）

幂等：已存在的列会跳过，可以反复运行。

运行方式：
    cd backend && python3 migrate_add_travel_pace.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from database import get_db
from sqlalchemy import text

# 表名 -> {字段名: SQLite 列定义}
NEW_COLUMNS = {
    "users": {"travel_pace": "VARCHAR(20)"},
    "companions": {"travel_pace": "VARCHAR(20)"},
}


def migrate():
    db = next(get_db())
    try:
        print("🔧 开始迁移：添加 travel_pace（旅游节奏）字段...")

        for table, cols in NEW_COLUMNS.items():
            result = db.execute(text(f"PRAGMA table_info({table})"))
            existing = [row[1] for row in result]

            if not existing:
                print(f"ℹ️  {table} 表不存在（全新数据库），建表时会自带新字段")
                continue

            for col, col_type in cols.items():
                if col in existing:
                    print(f"ℹ️  {table}.{col} 已存在，跳过")
                else:
                    db.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {col_type}"))
                    print(f"✅ {table}.{col} 已添加")

        db.commit()

        # 验证
        for table in NEW_COLUMNS:
            result = db.execute(text(f"PRAGMA table_info({table})"))
            cols = [row[1] for row in result]
            if cols and "travel_pace" not in cols:
                raise RuntimeError(f"{table}.travel_pace 添加失败")

        print("🎉 迁移完成")
    finally:
        db.close()


if __name__ == "__main__":
    migrate()

#!/usr/bin/env python3
"""
数据库迁移：users 表添加 MBTI 和星座字段（均为选填）

运行方式：
    python3 migrate_add_mbti_zodiac.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from database import get_db
from sqlalchemy import text

# 字段名 -> SQLite 列定义
USER_NEW_COLUMNS = {
    "mbti": "VARCHAR(10)",
    "zodiac": "VARCHAR(10)",
}


def migrate():
    db = next(get_db())
    try:
        print("🔧 开始迁移：users 表添加 mbti / zodiac 字段...")

        result = db.execute(text("PRAGMA table_info(users)"))
        columns = [row[1] for row in result]

        if not columns:
            print("ℹ️  users 表不存在（全新数据库），init_db() 建表时会自带新字段")
        else:
            for col, col_type in USER_NEW_COLUMNS.items():
                if col in columns:
                    print(f"ℹ️  users.{col} 已存在，跳过")
                else:
                    db.execute(text(f"ALTER TABLE users ADD COLUMN {col} {col_type}"))
                    print(f"✅ users.{col} 已添加")
            db.commit()

        print("🎉 迁移完成")
    finally:
        db.close()


if __name__ == "__main__":
    migrate()

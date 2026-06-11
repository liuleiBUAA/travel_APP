#!/usr/bin/env python3
"""
数据库迁移：users 表添加旅行名片字段 + 创建 comments 表

运行方式：
    python3 migrate_add_user_profile_comments.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from database import get_db, init_db
from sqlalchemy import text

# 字段名 -> SQLite 列定义
USER_NEW_COLUMNS = {
    "bio": "VARCHAR(200)",
    "budget_level": "VARCHAR(20)",
    "good_at_photo": "VARCHAR(10)",
    "accommodation_pref": "VARCHAR(20)",
    "driving": "VARCHAR(20)",
    "tags": "VARCHAR(300)",
}


def migrate():
    db = next(get_db())
    try:
        print("🔧 开始迁移：users 表名片字段 + comments 表...")

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

        # comments 表：init_db 的 create_all 只建不存在的表，幂等
        init_db()

        result = db.execute(text("PRAGMA table_info(comments)"))
        comment_columns = [row[1] for row in result]
        if comment_columns:
            print(f"✅ comments 表就绪，字段: {comment_columns}")
        else:
            raise RuntimeError("comments 表创建失败")

        print("🎉 迁移完成")
    finally:
        db.close()


if __name__ == "__main__":
    migrate()

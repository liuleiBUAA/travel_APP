#!/usr/bin/env python3
"""
数据库迁移：为 companions 表添加 contact_wechat 字段

运行方式：
    python3 migrate_add_contact_field.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from database import get_db
from sqlalchemy import text


def migrate():
    db = next(get_db())
    try:
        print("🔧 开始迁移：添加 contact_wechat 字段...")

        result = db.execute(text("PRAGMA table_info(companions)"))
        columns = [row[1] for row in result]

        if not columns:
            print("ℹ️  companions 表不存在（全新数据库），init_db() 建表时会自带新字段，无需迁移")
            return

        if 'contact_wechat' not in columns:
            db.execute(text("ALTER TABLE companions ADD COLUMN contact_wechat VARCHAR(100)"))
            db.commit()
            print("✅ 字段添加成功")
        else:
            print("ℹ️  contact_wechat 字段已存在，跳过")

        print("✅ 迁移完成！")
    except Exception as e:
        print(f"❌ 迁移失败: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    migrate()

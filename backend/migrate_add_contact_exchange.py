#!/usr/bin/env python3
"""
数据库迁移：交换微信申请制

1. users 表添加 wechat_id 私密字段
2. 创建 contact_exchanges 表
3. 数据迁移：把老帖子上的 contact_wechat 搬到发帖人的 users.wechat_id
   （同一用户多个帖子取最新一条；用户已有 wechat_id 则不覆盖）

运行方式：
    python3 migrate_add_contact_exchange.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from database import get_db, init_db
from sqlalchemy import text


def migrate():
    db = next(get_db())
    try:
        print("🔧 开始迁移：交换微信申请制...")

        # 1. users.wechat_id
        result = db.execute(text("PRAGMA table_info(users)"))
        columns = [row[1] for row in result]
        if not columns:
            print("ℹ️  users 表不存在（全新数据库），init_db() 建表时会自带新字段")
        elif "wechat_id" in columns:
            print("ℹ️  users.wechat_id 已存在，跳过")
        else:
            db.execute(text("ALTER TABLE users ADD COLUMN wechat_id VARCHAR(100)"))
            db.commit()
            print("✅ users.wechat_id 已添加")

        # 2. contact_exchanges 表（create_all 只建不存在的表，幂等）
        init_db()
        result = db.execute(text("PRAGMA table_info(contact_exchanges)"))
        exchange_columns = [row[1] for row in result]
        if exchange_columns:
            print(f"✅ contact_exchanges 表就绪，字段: {exchange_columns}")
        else:
            raise RuntimeError("contact_exchanges 表创建失败")

        # 3. 老帖子 contact_wechat → users.wechat_id（按帖子时间倒序，只填空缺）
        rows = db.execute(text(
            "SELECT user_id, contact_wechat FROM companions "
            "WHERE contact_wechat IS NOT NULL AND contact_wechat != '' "
            "ORDER BY created_at DESC"
        )).fetchall()
        migrated = 0
        seen = set()
        for user_id, contact in rows:
            if user_id in seen:
                continue
            seen.add(user_id)
            try:
                uid = int(user_id)
            except (ValueError, TypeError):
                print(f"⚠️  跳过旧格式 user_id: {user_id}")
                continue
            updated = db.execute(text(
                "UPDATE users SET wechat_id = :contact "
                "WHERE id = :uid AND (wechat_id IS NULL OR wechat_id = '')"
            ), {"contact": contact, "uid": uid})
            if updated.rowcount:
                migrated += 1
        db.commit()
        print(f"✅ 已迁移 {migrated} 个用户的微信号（帖子 contact_wechat → users.wechat_id）")

        print("🎉 迁移完成")
    finally:
        db.close()


if __name__ == "__main__":
    migrate()

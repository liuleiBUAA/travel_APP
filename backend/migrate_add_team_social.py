#!/usr/bin/env python3
"""
数据库迁移：组队 + 社交化功能

1. companions 表新增列：team_size / team_status / view_count / like_count
2. 新建表：team_members / companion_likes / companion_views
3. 回填：每个已有帖子的作者写一条 role=leader / status=approved 的成员记录；
   team_size = seeking.people_max + 1（含队长），team_status 据已批准人数判断。

幂等：可重复运行，已存在的列/表/回填记录会自动跳过。

运行方式：
    python3 migrate_add_team_social.py
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from database import get_db, init_db
from sqlalchemy import text

# companions 表新增列 -> SQLite 列定义
COMPANION_NEW_COLUMNS = {
    "team_size": "INTEGER",
    "team_status": "VARCHAR(20) DEFAULT 'recruiting'",
    "view_count": "INTEGER DEFAULT 0",
    "like_count": "INTEGER DEFAULT 0",
}


def _add_columns(db):
    result = db.execute(text("PRAGMA table_info(companions)"))
    columns = [row[1] for row in result]
    if not columns:
        print("ℹ️  companions 表不存在（全新数据库），init_db() 建表时会自带新字段")
        return False
    for col, col_type in COMPANION_NEW_COLUMNS.items():
        if col in columns:
            print(f"ℹ️  companions.{col} 已存在，跳过")
        else:
            db.execute(text(f"ALTER TABLE companions ADD COLUMN {col} {col_type}"))
            print(f"✅ companions.{col} 已添加")
    db.commit()
    return True


def _backfill_leaders(db):
    """为每个已有帖子写一条队长成员记录，并计算 team_size / team_status。"""
    rows = db.execute(text("SELECT id, user_id, seeking FROM companions")).fetchall()
    created = 0
    for cid, uid, seeking_json in rows:
        try:
            uid_int = int(uid)
        except (ValueError, TypeError):
            print(f"⚠️  帖子 {cid} 的 user_id={uid!r} 非法，跳过队长回填")
            continue

        # team_size = people_max + 1（含队长）；缺省按 2 人队
        people_max = 1
        try:
            seeking = json.loads(seeking_json) if seeking_json else {}
            people_max = int(seeking.get("people_max", 1)) or 1
        except (ValueError, TypeError, json.JSONDecodeError):
            people_max = 1
        team_size = people_max + 1

        # 队长成员记录（幂等：已存在则不重复插入）
        exists = db.execute(
            text("SELECT 1 FROM team_members WHERE companion_id=:c AND user_id=:u"),
            {"c": cid, "u": uid_int},
        ).first()
        if not exists:
            db.execute(
                text(
                    "INSERT INTO team_members (companion_id, user_id, role, status, flight_status) "
                    "VALUES (:c, :u, 'leader', 'approved', 'none')"
                ),
                {"c": cid, "u": uid_int},
            )
            created += 1

        # 已批准人数（含队长）-> 决定 team_status
        approved = db.execute(
            text("SELECT COUNT(*) FROM team_members WHERE companion_id=:c AND status='approved'"),
            {"c": cid},
        ).scalar() or 1
        status = "full" if approved >= team_size else "recruiting"

        db.execute(
            text("UPDATE companions SET team_size=:ts, team_status=:st WHERE id=:c "
                 "AND (team_size IS NULL OR team_status IS NULL OR team_status='')"),
            {"ts": team_size, "st": status, "c": cid},
        )
    db.commit()
    print(f"✅ 队长成员回填完成，新增 {created} 条 leader 记录")


def migrate():
    db = next(get_db())
    try:
        print("🔧 开始迁移：组队 + 社交化...")
        # 1. 建新表（team_members / companion_likes / companion_views）
        init_db()
        print("✅ 新表已确保创建（team_members / companion_likes / companion_views）")

        # 2. companions 加列
        has_table = _add_columns(db)

        # 3. 回填队长 + team_size/team_status
        if has_table:
            _backfill_leaders(db)

        print("🎉 迁移完成")
    finally:
        db.close()


if __name__ == "__main__":
    migrate()

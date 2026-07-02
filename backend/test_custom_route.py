#!/usr/bin/env python3
"""自定义路线发布功能验证测试。跑通：上传图片 → 发布自定义帖(图/文) → 读取详情。
用全新临时 SQLite 库（按当前 models 建表），不碰生产库。"""
import os
os.environ.setdefault("DEV_AUTH", "1")  # 开发鉴权模式

import io
import sys
import tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

# —— 用临时库替换默认引擎，按最新 models 建表，避免生产库缺列 ——
import database
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

_tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False).name
database.engine = create_engine(f"sqlite:///{_tmp_db}", connect_args={"check_same_thread": False})
database.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=database.engine)
import models  # noqa: F401  确保所有模型注册到 Base
database.Base.metadata.create_all(bind=database.engine)

from fastapi.testclient import TestClient
from main import app
from services.auth_service import create_token
from database import get_db
from models import User

client = TestClient(app)


def _ensure_user():
    """确保有个测试用户并返回其 token。"""
    db = next(get_db())
    u = db.query(User).filter(User.openid == "test_custom_openid").first()
    if not u:
        u = User(openid="test_custom_openid", nickname="自定义测试君", login_type="miniprogram")
        db.add(u)
        db.commit()
        db.refresh(u)
    token = create_token(u.id, u.openid)
    db.close()
    return token, u.id


def _png_bytes():
    """造一张最小合法 PNG。"""
    import struct, zlib
    w = h = 1
    raw = b"\x00\xff\x00\x00"  # 1px 红
    def chunk(typ, data):
        c = typ + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xffffffff)
    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    idat = zlib.compress(raw)
    return sig + chunk(b"IHDR", ihdr) + chunk(b"IDAT", idat) + chunk(b"IEND", b"")


def main():
    token, uid = _ensure_user()
    headers = {"Authorization": token}  # 前端传裸 token，不带 Bearer 前缀
    print(f"测试用户 id={uid}")

    # 1. 上传图片
    files = {"file": ("route.png", io.BytesIO(_png_bytes()), "image/png")}
    r = client.post("/api/upload/image", files=files, headers=headers)
    print("上传图片:", r.status_code, r.json())
    assert r.status_code == 200 and r.json()["success"], "上传失败"
    img_url = r.json()["url"]
    assert img_url.startswith("/api/static/uploads/"), "URL 前缀错误"

    # 1b. 上传非法格式应被拒
    bad = {"file": ("x.txt", io.BytesIO(b"hello"), "text/plain")}
    rb = client.post("/api/upload/image", files=bad, headers=headers)
    print("上传非法格式:", rb.status_code)
    assert rb.status_code == 400, "非法格式应被拒绝"

    # 2. 发布图片型自定义帖（不填天数/人数）
    payload_img = {
        "route_json": {
            "route_type": "custom",
            "cities": ["法国", "巴黎", "尼斯"],
            "custom_text": "国庆去法国摇人！想找爱拍照的姐妹",
            "custom_images": [img_url],
        },
        "travel_date": "2026-10-01",
    }
    r = client.post("/api/companions/publish", json=payload_img, headers=headers)
    print("发布图片型帖:", r.status_code, r.json())
    assert r.status_code == 200 and r.json()["success"], "发布图片型帖失败"
    cid_img = r.json()["companion_id"]

    # 3. 发布纯文字型自定义帖
    payload_text = {
        "route_json": {
            "route_type": "custom",
            "cities": ["日本", "大阪", "京都"],
            "custom_text": "圣诞想去关西自由行，有没有同频搭子",
            "custom_images": [],
        },
        "travel_date": "2026-12-20",
    }
    r = client.post("/api/companions/publish", json=payload_text, headers=headers)
    print("发布文字型帖:", r.status_code, r.json())
    assert r.status_code == 200 and r.json()["success"], "发布文字型帖失败"
    cid_text = r.json()["companion_id"]

    # 4. 校验：既无文字也无图，应被拒
    payload_empty = {
        "route_json": {"route_type": "custom", "cities": ["泰国"], "custom_text": "", "custom_images": []},
        "travel_date": "2026-11-01",
    }
    r = client.post("/api/companions/publish", json=payload_empty, headers=headers)
    print("空内容帖:", r.status_code)
    assert r.status_code == 400, "空内容帖应被拒绝"

    # 5. 校验：无地点应被拒
    payload_noloc = {
        "route_json": {"route_type": "custom", "cities": [], "custom_text": "随便走走"},
        "travel_date": "2026-11-01",
    }
    r = client.post("/api/companions/publish", json=payload_noloc, headers=headers)
    print("无地点帖:", r.status_code)
    assert r.status_code == 400, "无地点帖应被拒绝"

    # 6. 读取图片型详情，确认字段完整
    r = client.get(f"/api/companions/{cid_img}")
    print("读取图片型详情:", r.status_code)
    assert r.status_code == 200
    data = r.json()["data"]
    route = data["route"]
    assert route["route_type"] == "custom", "route_type 丢失"
    assert route["custom_images"] == [img_url], "图片 URL 丢失"
    assert route["custom_text"], "文案丢失"
    assert data["duration_days"] == 3, f"天数兜底应=城市数3, 实际={data['duration_days']}"
    assert data["seeking"]["people_min"] == 1, "seeking 兜底失败"
    print("  ✓ route_type/custom_images/custom_text/天数兜底/seeking兜底 全部正确")

    # 7. 旧模式（destination）回归：不带 route_type 照旧能发
    payload_old = {
        "route_json": {"cities": ["罗马", "佛罗伦萨"], "city_count": 2, "total_days": 5},
        "travel_date": "2026-09-01",
        "duration_days": 5,
        "seeking": {"people_min": 1, "people_max": 2, "gender": "不限"},
    }
    r = client.post("/api/companions/publish", json=payload_old, headers=headers)
    print("旧模式回归:", r.status_code, r.json())
    assert r.status_code == 200 and r.json()["success"], "旧模式回归失败"

    print("\n✅ 全部通过：上传/图片帖/文字帖/空内容拒绝/无地点拒绝/详情读取/旧模式回归")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
用户旅行名片 + 帖子留言功能测试

运行方式（本地无 harness 模块，测试内置 stub）：
    python3 test_profile_comments.py
或:
    pytest test_profile_comments.py -v
"""

import os
import sys
import types
from pathlib import Path

os.environ["DEV_AUTH"] = "1"  # 测试用 dev 模式登录
sys.path.insert(0, str(Path(__file__).parent))

# 测试用独立数据库
TEST_DB = Path(__file__).parent / "test_profile_comments.db"
if TEST_DB.exists():
    TEST_DB.unlink()

import database as _database_mod
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

_test_engine = create_engine(f"sqlite:///{TEST_DB}", connect_args={"check_same_thread": False})
_database_mod.engine = _test_engine
_database_mod.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_test_engine)
_database_mod.DATABASE_PATH = str(TEST_DB)


def _install_harness_stub():
    """本地无 harness 模块（只在生产服务器有），注入桩"""
    harness_pkg = types.ModuleType("harness")

    class _H:
        def on(self, event):
            def deco(fn):
                return fn
            return deco

        def api_guard(self, fn):
            return fn

        def record_violation(self, *a, **k):
            pass

        def validate_route_json(self, *a, **k):
            return []

        def validate_companion_data(self, *a, **k):
            return []

    harness_pkg.harness = _H()
    constraints = types.ModuleType("harness.constraints")

    class PermissionBoundary:
        pass

    constraints.PermissionBoundary = PermissionBoundary
    harness_pkg.constraints = constraints
    sys.modules["harness"] = harness_pkg
    sys.modules["harness.constraints"] = constraints


_install_harness_stub()

from fastapi.testclient import TestClient
import main

client = TestClient(main.app)


def _login(code: str) -> dict:
    """dev 模式登录（未配 WX_MINI_APPID 时任意 code 模拟 openid）"""
    res = client.post("/api/auth/wx-login", json={"code": code, "nickname": f"用户{code}"})
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["success"]
    return {"token": data["token"], "user_id": data["user"]["user_id"] if "user" in data else data.get("user_id")}


def _auth(token: str) -> dict:
    return {"Authorization": token}


def _publish_companion(token: str) -> int:
    """发一条搭子帖供留言测试"""
    res = client.post("/api/companions/publish", headers=_auth(token), json={
        "user_name": "测试用户",
        "route_json": {"cities": ["巴黎"], "itinerary": []},
        "travel_date": "2026-12-01",
        "duration_days": 10,
        "flexibility_days": 3,
        "seeking": {"people_min": 1, "people_max": 2, "gender": "不限"},
        "transport_mode": "自驾为主",
        "accommodation": "可拼房",
        "budget_level": "舒适",
        "good_at_photo": "擅长",
        "user_male_count": 1,
        "user_female_count": 0,
        "contact_wechat": "test_wx_001"
    })
    assert res.status_code == 200, res.text
    data = res.json()
    assert data.get("success"), data
    return data["data"]["companion_id"] if "data" in data else data["companion_id"]


# ==================== 名片资料 ====================

def test_update_and_read_profile_card():
    u = _login("alice")
    res = client.post("/api/auth/update-profile", headers=_auth(u["token"]), json={
        "bio": "爱旅行爱摄影，求靠谱搭子",
        "budget_level": "舒适",
        "good_at_photo": "大师",
        "accommodation_pref": "可拼房",
        "driving": "愿意当司机",
        "mbti": "INTJ",
        "zodiac": "天蝎座",
        "tags": "早起党,美食控,持国际驾照"
    })
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["bio"] == "爱旅行爱摄影，求靠谱搭子"
    assert data["driving"] == "愿意当司机"
    assert data["mbti"] == "INTJ"
    assert data["zodiac"] == "天蝎座"
    assert data["tags"] == ["早起党", "美食控", "持国际驾照"]

    # /me 读回
    res = client.get("/api/auth/me", headers=_auth(u["token"]))
    assert res.status_code == 200
    me = res.json()
    assert me["budget_level"] == "舒适"
    assert me["mbti"] == "INTJ"
    assert me["zodiac"] == "天蝎座"
    assert me["tags"] == ["早起党", "美食控", "持国际驾照"]


def test_mbti_zodiac_invalid_rejected():
    u = _login("mbti_bad")
    res = client.post("/api/auth/update-profile", headers=_auth(u["token"]),
                      json={"mbti": "XXXX"})
    assert res.status_code == 400
    res = client.post("/api/auth/update-profile", headers=_auth(u["token"]),
                      json={"zodiac": "蛇夫座"})
    assert res.status_code == 400


def test_mbti_zodiac_clear_field():
    u = _login("mbti_clear")
    client.post("/api/auth/update-profile", headers=_auth(u["token"]),
                json={"mbti": "ENFP", "zodiac": "白羊座"})
    res = client.post("/api/auth/update-profile", headers=_auth(u["token"]),
                      json={"mbti": "", "zodiac": ""})
    assert res.status_code == 200
    assert res.json()["mbti"] is None
    assert res.json()["zodiac"] is None


def test_profile_invalid_option_rejected():
    u = _login("bob")
    res = client.post("/api/auth/update-profile", headers=_auth(u["token"]),
                      json={"budget_level": "土豪"})
    assert res.status_code == 400


def test_profile_clear_field():
    u = _login("carol")
    client.post("/api/auth/update-profile", headers=_auth(u["token"]), json={"driving": "不会开车"})
    res = client.post("/api/auth/update-profile", headers=_auth(u["token"]), json={"driving": ""})
    assert res.status_code == 200
    assert res.json()["driving"] is None


def test_bio_too_long_rejected():
    u = _login("dave")
    res = client.post("/api/auth/update-profile", headers=_auth(u["token"]),
                      json={"bio": "长" * 201})
    assert res.status_code == 400


def test_public_profile_no_login():
    u = _login("eve")
    client.post("/api/auth/update-profile", headers=_auth(u["token"]),
                json={"bio": "公开主页测试", "budget_level": "轻奢"})
    me = client.get("/api/auth/me", headers=_auth(u["token"])).json()

    res = client.get(f"/api/users/{me['user_id']}/profile")  # 不带token
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["bio"] == "公开主页测试"
    assert data["budget_level"] == "轻奢"
    assert "companion_count" in data
    # 公开主页不应泄露 openid
    assert "openid" not in data


def test_public_profile_404():
    res = client.get("/api/users/999999/profile")
    assert res.status_code == 404


# ==================== 留言 ====================

def test_comment_crud_flow():
    author = _login("author1")
    cid = _publish_companion(author["token"])

    visitor = _login("visitor1")

    # 未登录不能发
    res = client.post(f"/api/companions/{cid}/comments", json={"content": "你好"})
    assert res.status_code in (401, 403, 422)

    # 登录后发留言
    res = client.post(f"/api/companions/{cid}/comments", headers=_auth(visitor["token"]),
                      json={"content": "行程能调整一天吗？"})
    assert res.status_code == 200, res.text
    comment = res.json()["data"]
    assert comment["content"] == "行程能调整一天吗？"
    assert comment["is_mine"] is True

    # 列表公开可见（未登录），is_mine 为 False
    res = client.get(f"/api/companions/{cid}/comments")
    assert res.status_code == 200
    items = res.json()["data"]
    assert len(items) == 1
    assert items[0]["is_mine"] is False
    assert items[0]["nickname"] == "用户visitor1"

    # 作者视角 is_mine 也是 False（不是自己的留言）
    res = client.get(f"/api/companions/{cid}/comments", headers=_auth(author["token"]))
    assert res.json()["data"][0]["is_mine"] is False

    # 留言者视角 is_mine = True
    res = client.get(f"/api/companions/{cid}/comments", headers=_auth(visitor["token"]))
    assert res.json()["data"][0]["is_mine"] is True

    comment_id = items[0]["comment_id"]

    # 别人不能删
    res = client.delete(f"/api/comments/{comment_id}", headers=_auth(author["token"]))
    assert res.status_code == 403

    # 本人能删
    res = client.delete(f"/api/comments/{comment_id}", headers=_auth(visitor["token"]))
    assert res.status_code == 200
    assert client.get(f"/api/companions/{cid}/comments").json()["total"] == 0


def test_comment_validation():
    u = _login("frank")
    cid = _publish_companion(u["token"])

    # 空留言
    res = client.post(f"/api/companions/{cid}/comments", headers=_auth(u["token"]),
                      json={"content": "   "})
    assert res.status_code == 400

    # 超长
    res = client.post(f"/api/companions/{cid}/comments", headers=_auth(u["token"]),
                      json={"content": "字" * 501})
    assert res.status_code == 400

    # 不存在的帖子
    res = client.post("/api/companions/999999/comments", headers=_auth(u["token"]),
                      json={"content": "hello"})
    assert res.status_code == 404


def test_comment_sec_check_rejected(monkeypatch=None):
    """msgSecCheck 不通过时留言被拒"""
    u = _login("grace")
    cid = _publish_companion(u["token"])

    import main as main_mod
    original = main_mod.msg_sec_check
    main_mod.msg_sec_check = lambda content, openid, scene=2: {"pass": False, "label": "100"}
    try:
        res = client.post(f"/api/companions/{cid}/comments", headers=_auth(u["token"]),
                          json={"content": "测试违规内容被拦截"})
        assert res.status_code == 400
        assert "违规" in res.json()["detail"]
    finally:
        main_mod.msg_sec_check = original


# ==================== 详情页 author ====================

def test_detail_includes_author_card():
    u = _login("henry")
    client.post("/api/auth/update-profile", headers=_auth(u["token"]),
                json={"budget_level": "舒适", "driving": "愿意当司机"})
    cid = _publish_companion(u["token"])

    res = client.get(f"/api/companions/{cid}")
    assert res.status_code == 200
    author = res.json()["data"]["author"]
    assert author is not None
    assert author["budget_level"] == "舒适"
    assert author["driving"] == "愿意当司机"
    assert "openid" not in author


def _run_all():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed = failed = 0
    for fn in fns:
        try:
            fn()
            print(f"✅ {fn.__name__}")
            passed += 1
        except Exception as e:
            import traceback
            print(f"❌ {fn.__name__}: {e}")
            traceback.print_exc()
            failed += 1
    print(f"\n{'🎉' if failed == 0 else '💥'} {passed} passed, {failed} failed")
    return failed


if __name__ == "__main__":
    code = _run_all()
    if TEST_DB.exists():
        TEST_DB.unlink()
    sys.exit(code)

#!/usr/bin/env python3
"""
交换微信申请制测试

运行方式（本地无 harness 模块，测试内置 stub）：
    python3 test_contact_exchange.py
或:
    pytest test_contact_exchange.py -v
"""

import os
import sys
import types
from pathlib import Path

os.environ["DEV_AUTH"] = "1"  # 测试用 dev 模式登录
sys.path.insert(0, str(Path(__file__).parent))

# 测试用独立数据库
TEST_DB = Path(__file__).parent / "test_contact_exchange.db"
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


def _set_wechat(token: str, wechat: str):
    res = client.post("/api/auth/update-profile", headers=_auth(token), json={"wechat_id": wechat})
    assert res.status_code == 200, res.text


def _publish(token: str) -> int:
    res = client.post("/api/companions/publish", headers=_auth(token), json={
        "user_name": "帖主",
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
        "user_female_count": 0
    })
    assert res.status_code == 200, res.text
    data = res.json()
    return data["data"]["companion_id"] if "data" in data else data["companion_id"]


def _comment(token: str, companion_id: int):
    res = client.post(f"/api/companions/{companion_id}/comments", headers=_auth(token),
                      json={"content": "我也想去，求拼"})
    assert res.status_code == 200, res.text


def _setup_pair(owner_code: str, commenter_code: str):
    """帖主发帖 + 留言者留言，双方都填了微信号"""
    owner = _login(owner_code)
    commenter = _login(commenter_code)
    _set_wechat(owner["token"], f"wx_{owner_code}")
    _set_wechat(commenter["token"], f"wx_{commenter_code}")
    cid = _publish(owner["token"])
    _comment(commenter["token"], cid)
    return owner, commenter, cid


# ==================== 微信号私密性 ====================

def test_wechat_id_saved_and_visible_to_self_only():
    u = _login("wx_self")
    _set_wechat(u["token"], "my_secret_wx")
    me = client.get("/api/auth/me", headers=_auth(u["token"])).json()
    assert me["wechat_id"] == "my_secret_wx"
    # 公开主页不泄露
    res = client.get(f"/api/users/{u['user_id']}/profile")
    assert res.status_code == 200
    assert "wechat_id" not in res.text


def test_detail_no_longer_returns_contact():
    owner, commenter, cid = _setup_pair("d_owner", "d_commenter")
    res = client.get(f"/api/companions/{cid}", headers=_auth(commenter["token"]))
    assert res.status_code == 200
    data = res.json()["data"]
    assert "contact_wechat" not in data
    assert "has_contact" not in data


def test_publish_with_contact_falls_back_to_user_field():
    """老版本客户端发帖带微信号 → 存入 users.wechat_id，帖子上不展示"""
    u = _login("old_client")
    res = client.post("/api/companions/publish", headers=_auth(u["token"]), json={
        "user_name": "老客户端",
        "route_json": {"cities": ["罗马"], "itinerary": []},
        "travel_date": "2026-12-01",
        "duration_days": 10,
        "flexibility_days": 3,
        "seeking": {"people_min": 1, "people_max": 2, "gender": "不限"},
        "transport_mode": "不限",
        "accommodation": "不限",
        "budget_level": "经济",
        "good_at_photo": "一般",
        "user_male_count": 1,
        "user_female_count": 0,
        "contact_wechat": "legacy_wx_123"
    })
    assert res.status_code == 200, res.text
    me = client.get("/api/auth/me", headers=_auth(u["token"])).json()
    assert me["wechat_id"] == "legacy_wx_123"


# ==================== 发起申请 ====================

def test_commenter_can_request_owner():
    owner, commenter, cid = _setup_pair("o1", "c1")
    res = client.post("/api/exchanges", headers=_auth(commenter["token"]),
                      json={"companion_id": cid, "to_user_id": owner["user_id"], "message": "聊得来，加个微信？"})
    assert res.status_code == 200, res.text
    data = res.json()["data"]
    assert data["status"] == "pending"
    assert data["other_wechat_id"] is None  # pending 时不泄露


def test_owner_can_request_commenter():
    owner, commenter, cid = _setup_pair("o2", "c2")
    res = client.post("/api/exchanges", headers=_auth(owner["token"]),
                      json={"companion_id": cid, "to_user_id": commenter["user_id"]})
    assert res.status_code == 200, res.text
    assert res.json()["data"]["status"] == "pending"


def test_request_requires_own_wechat():
    owner = _login("o3")
    commenter = _login("c3")
    _set_wechat(owner["token"], "wx_o3")
    cid = _publish(owner["token"])
    _comment(commenter["token"], cid)
    # commenter 没填微信号
    res = client.post("/api/exchanges", headers=_auth(commenter["token"]),
                      json={"companion_id": cid, "to_user_id": owner["user_id"]})
    assert res.status_code == 400
    assert "微信号" in res.json()["detail"]


def test_stranger_cannot_request():
    """没留言的路人不能发起申请"""
    owner, _, cid = _setup_pair("o4", "c4")
    stranger = _login("s4")
    _set_wechat(stranger["token"], "wx_s4")
    res = client.post("/api/exchanges", headers=_auth(stranger["token"]),
                      json={"companion_id": cid, "to_user_id": owner["user_id"]})
    assert res.status_code == 400
    assert "留言" in res.json()["detail"]


def test_cannot_request_self():
    owner, _, cid = _setup_pair("o5", "c5")
    res = client.post("/api/exchanges", headers=_auth(owner["token"]),
                      json={"companion_id": cid, "to_user_id": owner["user_id"]})
    assert res.status_code == 400


def test_duplicate_pending_blocked_both_directions():
    owner, commenter, cid = _setup_pair("o6", "c6")
    res = client.post("/api/exchanges", headers=_auth(commenter["token"]),
                      json={"companion_id": cid, "to_user_id": owner["user_id"]})
    assert res.status_code == 200
    # 同方向重发
    res = client.post("/api/exchanges", headers=_auth(commenter["token"]),
                      json={"companion_id": cid, "to_user_id": owner["user_id"]})
    assert res.status_code == 400
    # 反方向也被挡（提示去处理已有申请）
    res = client.post("/api/exchanges", headers=_auth(owner["token"]),
                      json={"companion_id": cid, "to_user_id": commenter["user_id"]})
    assert res.status_code == 400
    assert "处理" in res.json()["detail"]


# ==================== 同意 / 拒绝 ====================

def _request(from_u, to_u, cid) -> int:
    res = client.post("/api/exchanges", headers=_auth(from_u["token"]),
                      json={"companion_id": cid, "to_user_id": to_u["user_id"]})
    assert res.status_code == 200, res.text
    return res.json()["data"]["exchange_id"]


def test_accept_reveals_both_wechat():
    owner, commenter, cid = _setup_pair("o7", "c7")
    ex_id = _request(commenter, owner, cid)

    # 同意前：发起方查状态拿不到微信号
    res = client.get(f"/api/exchanges/status?companion_id={cid}&other_user_id={owner['user_id']}",
                     headers=_auth(commenter["token"]))
    assert res.json()["status"] == "pending"
    assert res.json()["data"]["other_wechat_id"] is None

    # 帖主同意
    res = client.post(f"/api/exchanges/{ex_id}/handle", headers=_auth(owner["token"]), json={"action": "accept"})
    assert res.status_code == 200, res.text
    data = res.json()["data"]
    assert data["status"] == "accepted"
    assert data["other_wechat_id"] == "wx_c7"  # 帖主看到留言者微信

    # 发起方也能看到帖主微信
    res = client.get(f"/api/exchanges/status?companion_id={cid}&other_user_id={owner['user_id']}",
                     headers=_auth(commenter["token"]))
    assert res.json()["data"]["other_wechat_id"] == "wx_o7"


def test_reject_reveals_nothing_and_cooldown():
    owner, commenter, cid = _setup_pair("o8", "c8")
    ex_id = _request(commenter, owner, cid)
    res = client.post(f"/api/exchanges/{ex_id}/handle", headers=_auth(owner["token"]), json={"action": "reject"})
    assert res.status_code == 200
    assert res.json()["data"]["other_wechat_id"] is None
    # 被拒后冷却期内不能再发
    res = client.post("/api/exchanges", headers=_auth(commenter["token"]),
                      json={"companion_id": cid, "to_user_id": owner["user_id"]})
    assert res.status_code == 400
    assert "天后" in res.json()["detail"]


def test_only_receiver_can_handle():
    owner, commenter, cid = _setup_pair("o9", "c9")
    ex_id = _request(commenter, owner, cid)
    # 发起方自己不能同意
    res = client.post(f"/api/exchanges/{ex_id}/handle", headers=_auth(commenter["token"]), json={"action": "accept"})
    assert res.status_code == 403
    # 无关第三人也不能
    third = _login("t9")
    res = client.post(f"/api/exchanges/{ex_id}/handle", headers=_auth(third["token"]), json={"action": "accept"})
    assert res.status_code == 403


def test_handle_twice_blocked():
    owner, commenter, cid = _setup_pair("o10", "c10")
    ex_id = _request(commenter, owner, cid)
    assert client.post(f"/api/exchanges/{ex_id}/handle", headers=_auth(owner["token"]),
                       json={"action": "accept"}).status_code == 200
    res = client.post(f"/api/exchanges/{ex_id}/handle", headers=_auth(owner["token"]), json={"action": "reject"})
    assert res.status_code == 400


# ==================== 我的交换列表 ====================

def test_my_exchanges_grouping():
    owner, commenter, cid = _setup_pair("o11", "c11")
    ex_id = _request(commenter, owner, cid)

    # 帖主视角：收到 1 条待处理
    res = client.get("/api/exchanges/my", headers=_auth(owner["token"])).json()
    assert len(res["received"]) == 1
    assert res["received"][0]["other"]["nickname"] == "用户c11"

    # 发起方视角：发出 1 条
    res = client.get("/api/exchanges/my", headers=_auth(commenter["token"])).json()
    assert len(res["sent"]) == 1

    # 同意后双方都在 accepted 里且互见微信
    client.post(f"/api/exchanges/{ex_id}/handle", headers=_auth(owner["token"]), json={"action": "accept"})
    res = client.get("/api/exchanges/my", headers=_auth(owner["token"])).json()
    assert len(res["accepted"]) == 1
    assert res["accepted"][0]["other_wechat_id"] == "wx_c11"
    res = client.get("/api/exchanges/my", headers=_auth(commenter["token"])).json()
    assert res["accepted"][0]["other_wechat_id"] == "wx_o11"


def test_exchanges_require_login():
    assert client.get("/api/exchanges/my").status_code == 401
    assert client.post("/api/exchanges", json={"companion_id": 1, "to_user_id": 1}).status_code == 401


if __name__ == "__main__":
    fns = [(name, fn) for name, fn in sorted(globals().items()) if name.startswith("test_") and callable(fn)]
    passed = failed = 0
    for name, fn in fns:
        try:
            fn()
            print(f"✅ {name}")
            passed += 1
        except Exception as e:
            print(f"❌ {name}: {e}")
            failed += 1
    print(f"\n{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)

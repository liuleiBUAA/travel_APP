#!/usr/bin/env python3
"""
组队 + 社交化功能测试（申请加入 / 队长同意-踢人 / 机票状态 / 浏览 / 点赞）

运行方式：
    python3 test_team_social.py
或:
    pytest test_team_social.py -v
"""

import os
import sys
import types
from pathlib import Path

os.environ["DEV_AUTH"] = "1"
sys.path.insert(0, str(Path(__file__).parent))

TEST_DB = Path(__file__).parent / "test_team_social.db"
if TEST_DB.exists():
    TEST_DB.unlink()

import database as _database_mod
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

_test_engine = create_engine(f"sqlite:///{TEST_DB}", connect_args={"check_same_thread": False})
_database_mod.engine = _test_engine
_database_mod.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_test_engine)
_database_mod.DATABASE_PATH = str(TEST_DB)
# 显式在测试引擎上建表（保证与其他测试文件同进程运行时也有表）
import models as _models  # noqa: F401  注册所有模型到 Base.metadata
_database_mod.Base.metadata.create_all(bind=_test_engine)


def _install_harness_stub():
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


# ==================== 辅助 ====================

def _login(code: str) -> dict:
    res = client.post("/api/auth/wx-login", json={"code": code, "nickname": f"用户{code}"})
    assert res.status_code == 200, res.text
    data = res.json()
    return {"token": data["token"], "user_id": data["user"]["user_id"] if "user" in data else data.get("user_id")}


def _auth(token: str) -> dict:
    return {"Authorization": token}


def _set_wechat(token: str, wx: str):
    res = client.post("/api/auth/update-profile", headers=_auth(token), json={"wechat_id": wx})
    assert res.status_code == 200, res.text


def _publish(token: str, people_max: int = 2) -> int:
    res = client.post("/api/companions/publish", headers=_auth(token), json={
        "user_name": "队长",
        "route_json": {"cities": ["巴黎"], "itinerary": []},
        "travel_date": "2026-12-01",
        "duration_days": 10,
        "flexibility_days": 3,
        "seeking": {"people_min": 1, "people_max": people_max, "gender": "不限"},
        "transport_mode": "自驾为主",
        "accommodation": "可拼房",
        "budget_level": "舒适",
        "good_at_photo": "擅长",
        "user_male_count": 1,
        "user_female_count": 0,
        "contact_wechat": "leader_wx"
    })
    assert res.status_code == 200, res.text
    data = res.json()
    return data["data"]["companion_id"] if "data" in data else data["companion_id"]


def _comment(token: str, cid: int, text: str = "想加入，有问题问下"):
    res = client.post(f"/api/companions/{cid}/comments", headers=_auth(token), json={"content": text})
    assert res.status_code == 200, res.text


# ==================== 组队主流程 ====================

def test_team_leader_auto_created():
    """发帖后队长自动成为 leader，team_size = people_max+1，状态 recruiting"""
    leader = _login("t_leader1")
    cid = _publish(leader["token"], people_max=2)
    res = client.get(f"/api/companions/{cid}/team", headers=_auth(leader["token"]))
    assert res.status_code == 200, res.text
    team = res.json()["data"]
    assert team["team_size"] == 3       # 2 + 队长
    assert team["joined_count"] == 1    # 仅队长
    assert team["open_slots"] == 2
    assert team["team_status"] == "recruiting"
    assert team["is_leader"] is True
    assert len(team["members"]) == 1
    assert team["members"][0]["role"] == "leader"


def test_apply_requires_comment_and_wechat():
    leader = _login("t_leader2")
    cid = _publish(leader["token"])
    applicant = _login("t_app2")

    # 没填微信 -> 拒
    res = client.post(f"/api/companions/{cid}/team/apply", headers=_auth(applicant["token"]), json={})
    assert res.status_code == 400
    assert "微信" in res.json()["detail"]

    # 填了微信但没留言 -> 拒
    _set_wechat(applicant["token"], "app2_wx")
    res = client.post(f"/api/companions/{cid}/team/apply", headers=_auth(applicant["token"]), json={})
    assert res.status_code == 400
    assert "留言" in res.json()["detail"]

    # 留言后可申请
    _comment(applicant["token"], cid)
    res = client.post(f"/api/companions/{cid}/team/apply", headers=_auth(applicant["token"]),
                      json={"message": "我也想去巴黎"})
    assert res.status_code == 200, res.text


def test_full_join_flow_and_wechat_unlock():
    """申请 -> 队长同意 -> 占位 + 微信互见"""
    leader = _login("t_leader3")
    _set_wechat(leader["token"], "leader3_wx")
    cid = _publish(leader["token"], people_max=1)  # team_size=2，只能加1人

    app1 = _login("t_app3a")
    _set_wechat(app1["token"], "app3a_wx")
    _comment(app1["token"], cid)
    r = client.post(f"/api/companions/{cid}/team/apply", headers=_auth(app1["token"]), json={})
    assert r.status_code == 200
    member_id = r.json()["member_id"]

    # 队长看到 pending
    team = client.get(f"/api/companions/{cid}/team", headers=_auth(leader["token"])).json()["data"]
    assert team["pending_count"] == 1
    # pending 时不解锁微信
    assert team["pending"][0]["wechat_id"] is None

    # 非队长不能审批
    other = _login("t_other3")
    r = client.post(f"/api/companions/{cid}/team/handle", headers=_auth(other["token"]),
                    json={"member_id": member_id, "action": "approve"})
    assert r.status_code == 403

    # 队长同意
    r = client.post(f"/api/companions/{cid}/team/handle", headers=_auth(leader["token"]),
                    json={"member_id": member_id, "action": "approve"})
    assert r.status_code == 200, r.text
    assert r.json()["team_status"] == "full"  # 2/2 满员

    # 成员视角能看到队长微信
    team = client.get(f"/api/companions/{cid}/team", headers=_auth(app1["token"])).json()["data"]
    assert team["joined_count"] == 2
    assert team["my_member"]["status"] == "approved"
    leader_member = [m for m in team["members"] if m["role"] == "leader"][0]
    assert leader_member["wechat_id"] == "leader3_wx"

    # 满员后新人不能申请
    app2 = _login("t_app3b")
    _set_wechat(app2["token"], "app3b_wx")
    _comment(app2["token"], cid)
    r = client.post(f"/api/companions/{cid}/team/apply", headers=_auth(app2["token"]), json={})
    assert r.status_code == 400
    assert "满员" in r.json()["detail"]


def test_kick_releases_slot_and_reopens():
    leader = _login("t_leader4")
    _set_wechat(leader["token"], "leader4_wx")
    cid = _publish(leader["token"], people_max=1)

    app1 = _login("t_app4")
    _set_wechat(app1["token"], "app4_wx")
    _comment(app1["token"], cid)
    r = client.post(f"/api/companions/{cid}/team/apply", headers=_auth(app1["token"]), json={})
    member_id = r.json()["member_id"]
    client.post(f"/api/companions/{cid}/team/handle", headers=_auth(leader["token"]),
                json={"member_id": member_id, "action": "approve"})

    # 满员
    team = client.get(f"/api/companions/{cid}/team", headers=_auth(leader["token"])).json()["data"]
    assert team["team_status"] == "full"

    # 队员视角拿到自己的 member_id 用于踢人参数（队长也可从 members 取）
    full_team = client.get(f"/api/companions/{cid}/team", headers=_auth(leader["token"])).json()["data"]
    member_row = [m for m in full_team["members"] if m["role"] == "member"][0]

    # 不能踢队长
    leader_row = [m for m in full_team["members"] if m["role"] == "leader"][0]
    r = client.post(f"/api/companions/{cid}/team/kick", headers=_auth(leader["token"]),
                    json={"member_id": leader_row["member_id"]})
    assert r.status_code == 400

    # 踢队员
    r = client.post(f"/api/companions/{cid}/team/kick", headers=_auth(leader["token"]),
                    json={"member_id": member_row["member_id"]})
    assert r.status_code == 200, r.text
    assert r.json()["team_status"] == "recruiting"  # 释放名额转回招募

    # 被踢者可以再申请（默认允许）
    r = client.post(f"/api/companions/{cid}/team/apply", headers=_auth(app1["token"]), json={})
    assert r.status_code == 200, r.text


def test_flight_status_self_only():
    leader = _login("t_leader5")
    _set_wechat(leader["token"], "leader5_wx")
    cid = _publish(leader["token"], people_max=2)

    app1 = _login("t_app5")
    _set_wechat(app1["token"], "app5_wx")
    _comment(app1["token"], cid)
    r = client.post(f"/api/companions/{cid}/team/apply", headers=_auth(app1["token"]), json={})
    mid = r.json()["member_id"]
    client.post(f"/api/companions/{cid}/team/handle", headers=_auth(leader["token"]),
                json={"member_id": mid, "action": "approve"})

    # 队员更新自己的机票状态
    r = client.post(f"/api/companions/{cid}/flight-status", headers=_auth(app1["token"]),
                    json={"flight_status": "booked"})
    assert r.status_code == 200, r.text
    assert r.json()["flight_status"] == "booked"

    # 非法值被拒
    r = client.post(f"/api/companions/{cid}/flight-status", headers=_auth(app1["token"]),
                    json={"flight_status": "xxx"})
    assert r.status_code == 400

    # 非队员（未入队）不能改
    outsider = _login("t_out5")
    r = client.post(f"/api/companions/{cid}/flight-status", headers=_auth(outsider["token"]),
                    json={"flight_status": "searching"})
    assert r.status_code == 403

    # 状态体现在成员墙
    team = client.get(f"/api/companions/{cid}/team", headers=_auth(leader["token"])).json()["data"]
    m = [x for x in team["members"] if x["role"] == "member"][0]
    assert m["flight_status"] == "booked"


def test_leader_cannot_apply_own():
    leader = _login("t_leader6")
    _set_wechat(leader["token"], "leader6_wx")
    cid = _publish(leader["token"])
    r = client.post(f"/api/companions/{cid}/team/apply", headers=_auth(leader["token"]), json={})
    assert r.status_code == 400
    assert "队长" in r.json()["detail"]


# ==================== 浏览 / 点赞 ====================

def test_view_count_dedup():
    leader = _login("t_leader7")
    cid = _publish(leader["token"])
    u = _login("t_viewer7")

    # 匿名浏览不计数
    r = client.post(f"/api/companions/{cid}/view")
    assert r.status_code == 200
    assert r.json()["view_count"] == 0

    # 登录浏览 +1
    r = client.post(f"/api/companions/{cid}/view", headers=_auth(u["token"]))
    assert r.json()["view_count"] == 1
    # 同人再浏览不重复计数
    r = client.post(f"/api/companions/{cid}/view", headers=_auth(u["token"]))
    assert r.json()["view_count"] == 1

    # 另一人 +1
    u2 = _login("t_viewer7b")
    r = client.post(f"/api/companions/{cid}/view", headers=_auth(u2["token"]))
    assert r.json()["view_count"] == 2


def test_like_toggle():
    leader = _login("t_leader8")
    cid = _publish(leader["token"])
    u = _login("t_liker8")

    # 未登录不能点赞
    r = client.post(f"/api/companions/{cid}/like")
    assert r.status_code in (401, 403, 422)

    # 点赞
    r = client.post(f"/api/companions/{cid}/like", headers=_auth(u["token"]))
    assert r.status_code == 200, r.text
    assert r.json()["liked"] is True
    assert r.json()["like_count"] == 1

    # 再点 = 取消
    r = client.post(f"/api/companions/{cid}/like", headers=_auth(u["token"]))
    assert r.json()["liked"] is False
    assert r.json()["like_count"] == 0

    # 详情页 liked_by_me 反映状态
    client.post(f"/api/companions/{cid}/like", headers=_auth(u["token"]))
    detail = client.get(f"/api/companions/{cid}", headers=_auth(u["token"])).json()["data"]
    assert detail["like_count"] == 1
    assert detail["liked_by_me"] is True
    assert detail["team"]["team_size"] >= 2


def test_list_includes_team_brief():
    leader = _login("t_leader9")
    cid = _publish(leader["token"])
    res = client.get("/api/companions/list")
    assert res.status_code == 200
    items = res.json()["data"]
    target = [x for x in items if x["companion_id"] == cid][0]
    assert "team" in target
    assert target["team"]["team_size"] >= 2
    assert "view_count" in target["team"]
    assert "like_count" in target["team"]


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
    sys.exit(1 if code else 0)

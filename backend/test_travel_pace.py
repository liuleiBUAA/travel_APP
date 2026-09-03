#!/usr/bin/env python3
"""旅游节奏 travel_pace 端到端测试

覆盖：
1. 名片可保存/读回 travel_pace，非法值被拒
2. 发布带 travel_pace，列表/详情能读回
3. 精确匹配：特种兵 vs 慢悠悠 被过滤掉；适中/不限 能匹配到
4. 打分：节奏相同 > 相邻 > 对立，不限/缺字段不惩罚

运行方式：
    pytest test_travel_pace.py -v
"""

import os
import sys
import types
from pathlib import Path

os.environ["DEV_AUTH"] = "1"
sys.path.insert(0, str(Path(__file__).parent))

# 测试用独立数据库
TEST_DB = Path(__file__).parent / "test_travel_pace.db"
if TEST_DB.exists():
    TEST_DB.unlink()

import database as _database_mod
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

_test_engine = create_engine(f"sqlite:///{TEST_DB}", connect_args={"check_same_thread": False})
_database_mod.engine = _test_engine
_database_mod.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_test_engine)
_database_mod.DATABASE_PATH = str(TEST_DB)

# 必须建表：pytest 一次收集多个测试文件时，模块级 engine 覆盖是全局生效的，
# 只换 engine 不建表会让同 session 的其他测试全部撞到空库（no such table）。
import models  # noqa: F401,E402  确保所有模型已注册到 Base.metadata
_database_mod.Base.metadata.create_all(bind=_test_engine)


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

from fastapi.testclient import TestClient  # noqa: E402
import main  # noqa: E402
from services.match_service import MatchService  # noqa: E402

client = TestClient(main.app)

ROUTE = {"cities": ["巴黎", "里昂"], "itinerary": []}


def _login(code: str) -> str:
    res = client.post("/api/auth/wx-login", json={"code": code, "nickname": f"用户{code}"})
    assert res.status_code == 200, res.text
    return res.json()["token"]


def _auth(token: str) -> dict:
    return {"Authorization": token}


def _publish(token: str, pace, date="2027-05-01") -> int:
    payload = {
        "user_name": "节奏测试",
        "route_json": ROUTE,
        "travel_date": date,
        "duration_days": 6,
        "flexibility_days": 3,
        "seeking": {"people_min": 1, "people_max": 2, "gender": "不限"},
        "transport_mode": "不限",
        "accommodation": "不限",
        "budget_level": "经济",
        "good_at_photo": "不限",
        "user_male_count": 1,
        "user_female_count": 0,
    }
    if pace is not None:
        payload["travel_pace"] = pace
    res = client.post("/api/companions/publish", headers=_auth(token), json=payload)
    assert res.status_code == 200, res.text
    data = res.json()
    assert data.get("success"), data
    return data["data"]["companion_id"] if "data" in data else data["companion_id"]


# ---------- 1. 名片 ----------

def test_profile_card_travel_pace_saved():
    token = _login("pace_card_1")
    res = client.post("/api/auth/update-profile", headers=_auth(token), json={"travel_pace": "特种兵"})
    assert res.status_code == 200, res.text

    me = client.get("/api/auth/me", headers=_auth(token)).json()
    card = me.get("profile_card") or me
    assert card.get("travel_pace") == "特种兵", me


def test_profile_card_travel_pace_invalid_rejected():
    token = _login("pace_card_2")
    res = client.post("/api/auth/update-profile", headers=_auth(token), json={"travel_pace": "飞一样"})
    assert res.status_code == 400, res.text


def test_profile_card_travel_pace_clearable():
    token = _login("pace_card_3")
    client.post("/api/auth/update-profile", headers=_auth(token), json={"travel_pace": "慢悠悠"})
    res = client.post("/api/auth/update-profile", headers=_auth(token), json={"travel_pace": ""})
    assert res.status_code == 200, res.text
    me = client.get("/api/auth/me", headers=_auth(token)).json()
    card = me.get("profile_card") or me
    assert not card.get("travel_pace")


# ---------- 2. 发布 / 读回 ----------

def test_publish_and_readback_travel_pace():
    token = _login("pace_pub_1")
    cid = _publish(token, "慢悠悠")

    detail = client.get(f"/api/companions/{cid}").json()
    d = detail.get("detail") or detail.get("data") or detail
    assert d["travel_pace"] == "慢悠悠", detail

    lst = client.get("/api/companions/list").json()
    rows = lst.get("data") or lst.get("companions") or []
    got = [c for c in rows if c["companion_id"] == cid]
    assert got and got[0]["travel_pace"] == "慢悠悠"


def test_publish_without_travel_pace_defaults_unlimited():
    token = _login("pace_pub_2")
    cid = _publish(token, None)
    detail = client.get(f"/api/companions/{cid}").json()
    d = detail.get("detail") or detail.get("data") or detail
    assert d["travel_pace"] == "不限", detail


# ---------- 3. 精确匹配硬筛 ----------

def _match(pace):
    res = client.post("/api/companions/match", json={
        "route_json": ROUTE,
        "travel_date": "2027-06-10",
        "time_flexibility_days": 7,
        "match_mode": "precise",
        "transport_mode": "不限",
        "accommodation": "不限",
        "budget_level": "经济",
        "travel_pace": pace,
    })
    assert res.status_code == 200, res.text
    data = res.json()
    return data.get("matches") or data.get("data", {}).get("matches") or []


def test_precise_match_filters_conflicting_pace():
    token = _login("pace_match_owner")
    cid = _publish(token, "特种兵", date="2027-06-10")

    # 慢悠悠的人搜 → 这条特种兵应被筛掉
    assert cid not in [m["companion_id"] for m in _match("慢悠悠")]
    # 适中 / 不限 → 能看到
    assert cid in [m["companion_id"] for m in _match("适中")]
    assert cid in [m["companion_id"] for m in _match("不限")]
    assert cid in [m["companion_id"] for m in _match("特种兵")]


def test_fuzzy_match_ignores_pace():
    token = _login("pace_fuzzy_owner")
    cid = _publish(token, "特种兵", date="2027-07-10")
    res = client.post("/api/companions/match", json={
        "route_json": ROUTE,
        "travel_date": "2027-07-10",
        "time_flexibility_days": 7,
        "match_mode": "fuzzy",
        "travel_pace": "慢悠悠",
    })
    assert res.status_code == 200, res.text
    data = res.json()
    matches = data.get("matches") or data.get("data", {}).get("matches") or []
    # 模糊模式只看时间+地点，节奏冲突也应出现
    assert cid in [m["companion_id"] for m in matches]


# ---------- 4. 打分 ----------

def test_preference_score_pace_ordering():
    ms = MatchService()
    base = {"transport_mode": "不限", "accommodation": "不限",
            "budget_level": "经济", "good_at_photo": "不限"}

    def score(p1, p2):
        return ms.calculate_preference_match(
            {**base, "travel_pace": p1}, {**base, "travel_pace": p2})

    same = score("特种兵", "特种兵")
    adjacent = score("特种兵", "适中")
    opposite = score("特种兵", "慢悠悠")
    unlimited = score("特种兵", "不限")

    assert same > adjacent > opposite
    assert unlimited == same
    # 缺字段不惩罚
    assert ms.calculate_preference_match(dict(base), dict(base)) == same

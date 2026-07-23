"""多渠道团队管理改造 —— 专项测试。

测试对象：``app/routers/channel_mgmt.py`` 下的团队管理接口（前缀 ``/api/channels``）。
约定（与 test_channel_mgmt.py 一致）：
- 使用 ``TestClient(app)`` 直接对接共享开发库（``MORPHIX_DEV=1`` 默认注入 ``team-initial``）。
- 自建团队均在测试内创建并在 ``finally`` 中清理，避免污染共享库。
- 不依赖条件种子账号（``acc-zhulu`` 等仅在 ``MORPHIX_SEED_CHANNEL_DEMO=1`` 注入）。
- 成员解析依赖 ``organization.find_auth_user`` 读取内存 ``_auth_users``；
  种子授权用户 ``auth-1``..``auth-5`` 始终可用，故 happy-path 用 ``auth-1``。
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

# 始终可解析的授权用户（organization_schemas.SEED_AUTH_USERS）。
SEED_AUTH_USER_ID = "auth-1"
SEED_AUTH_USER_ACCOUNT = "admin@morphix"
SEED_AUTH_USER_NICKNAME = "谷一莹"
SEED_AUTH_USER_ROLE = "管理员"


# --------------------------------------------------------------------------- #
# 工具函数
# --------------------------------------------------------------------------- #
def _create_team(name: str, **kwargs) -> dict:
    """创建团队并返回响应体（断言 200）。"""
    payload = {"name": name, **kwargs}
    resp = client.post("/api/channels/teams", json=payload)
    assert resp.status_code == 200, resp.text
    return resp.json()


def _delete_team(tid: str) -> int:
    """尽力删除团队（清理用，不抛错）。返回状态码。"""
    resp = client.delete(f"/api/channels/teams/{tid}")
    return resp.status_code


# --------------------------------------------------------------------------- #
# 1) 团队列表
# --------------------------------------------------------------------------- #
def test_list_teams_basic():
    resp = client.get("/api/channels/teams")
    assert resp.status_code == 200
    data = resp.json()
    # 响应体为 list（非封套）；不依赖特定种子团队，以兼容用户已有数据
    assert isinstance(data, list)
    # DTO 字段对齐（snake_case DB -> camelCase）
    for team in data:
        assert set(team.keys()) >= {"id", "name", "seatsLeft", "energyValue", "description"}


# --------------------------------------------------------------------------- #
# 2) 创建团队（默认 seats/energy/description 回落 + 显式值）
# --------------------------------------------------------------------------- #
def test_create_team_defaults_fallback():
    team = _create_team("QA-默认回落团队")
    try:
        assert team["name"] == "QA-默认回落团队"
        assert team["id"].startswith("team_")
        # 回落：seatsLeft=1, energyValue=0, description=""
        assert team["seatsLeft"] == 1
        assert team["energyValue"] == 0
        assert team["description"] == ""
    finally:
        _delete_team(team["id"])


def test_create_team_explicit_values():
    team = _create_team(
        "QA-显式值团队",
        seatsLeft=5,
        energyValue=120,
        description="专项测试团队",
    )
    try:
        assert team["name"] == "QA-显式值团队"
        assert team["seatsLeft"] == 5
        assert team["energyValue"] == 120
        assert team["description"] == "专项测试团队"
    finally:
        _delete_team(team["id"])


def test_create_team_seats_zero_allowed():
    """seatsLeft=0 是合法显式值（仅 None 才回落为 1）。"""
    team = _create_team("QA-零席位团队", seatsLeft=0, energyValue=0)
    try:
        assert team["seatsLeft"] == 0
        assert team["energyValue"] == 0
    finally:
        _delete_team(team["id"])


# --------------------------------------------------------------------------- #
# 3) 更新团队（部分更新 + 404）
# --------------------------------------------------------------------------- #
def test_update_team_partial():
    team = _create_team("QA-待更新团队", description="旧简介")
    try:
        # 仅更新 name
        resp = client.put(
            f"/api/channels/teams/{team['id']}",
            json={"name": "QA-已改名团队"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["name"] == "QA-已改名团队"
        assert body["description"] == "旧简介"  # 未传字段沿用原值
        assert body["id"] == team["id"]

        # 仅更新 description
        resp2 = client.put(
            f"/api/channels/teams/{team['id']}",
            json={"description": "新简介<=20字"},
        )
        assert resp2.status_code == 200
        body2 = resp2.json()
        assert body2["name"] == "QA-已改名团队"
        assert body2["description"] == "新简介<=20字"
    finally:
        _delete_team(team["id"])


def test_update_team_not_found():
    resp = client.put(
        "/api/channels/teams/team-not-exist-qax",
        json={"name": "幽灵团队"},
    )
    assert resp.status_code == 404
    assert resp.json().get("detail") == "团队不存在"


# --------------------------------------------------------------------------- #
# 4) 删除团队守卫（最后一个团队 400 + 普通删除 200 + 404）
# --------------------------------------------------------------------------- #
def test_delete_last_team_guard():
    """只剩一个团队时禁止删除，返回 400。

    为避免误删用户数据，仅在开发库当前仅剩一个团队时执行；
    否则跳过（共享开发库可能已积累用户创建的其它团队）。
    """
    teams = client.get("/api/channels/teams").json()
    if len(teams) != 1:
        pytest.skip(
            f"开发库当前有 {len(teams)} 个团队，无法安全验证末团队守卫（避免删除用户数据）"
        )
    only_team = teams[0]
    resp = client.delete(f"/api/channels/teams/{only_team['id']}")
    assert resp.status_code == 400
    assert resp.json().get("message") == "当前团队为最后一个团队，无法删除"
    # 该团队必须仍然存在（未被删除）
    still = client.get("/api/channels/teams").json()
    assert any(t["id"] == only_team["id"] for t in still)


def test_delete_team_normal():
    """普通删除：存在多个团队时删除其一应成功返回 {deleted:true,id}。"""
    team = _create_team("QA-待删除团队")
    resp = client.delete(f"/api/channels/teams/{team['id']}")
    assert resp.status_code == 200
    body = resp.json()
    assert body.get("deleted") is True
    assert body.get("id") == team["id"]
    # 再次查询应已不存在
    assert client.get(f"/api/channels/teams/{team['id']}/members").status_code == 404


def test_delete_team_not_found():
    resp = client.delete("/api/channels/teams/team-not-exist-qax")
    assert resp.status_code == 404
    assert resp.json().get("detail") == "团队不存在"


# --------------------------------------------------------------------------- #
# 5) 成员列表（含 404）
# --------------------------------------------------------------------------- #
def test_list_team_members_empty():
    """自建空团队的成员列表应为空，且 DTO 字段对齐。"""
    team = _create_team("QA-空成员团队")
    try:
        resp = client.get(f"/api/channels/teams/{team['id']}/members")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list) and len(data) == 0
    finally:
        _delete_team(team["id"])


def test_list_team_members_not_found():
    resp = client.get("/api/channels/teams/team-not-exist-qax/members")
    assert resp.status_code == 404
    assert resp.json().get("detail") == "团队不存在"


# --------------------------------------------------------------------------- #
# 6) 添加成员（happy-path + 优雅跳过 + 去重 + 404）
# --------------------------------------------------------------------------- #
def test_add_team_members_happy_path():
    """happy-path：解析种子授权用户 auth-1 后冗余落库，返回 added>=1。"""
    team = _create_team("QA-成员团队-happy")
    try:
        resp = client.post(
            f"/api/channels/teams/{team['id']}/members",
            json={"userIds": [SEED_AUTH_USER_ID]},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["added"] == 1
        assert len(body["members"]) == 1
        m = body["members"][0]
        assert m["userId"] == SEED_AUTH_USER_ID
        assert m["account"] == SEED_AUTH_USER_ACCOUNT
        assert m["nickname"] == SEED_AUTH_USER_NICKNAME
        assert m["role"] == SEED_AUTH_USER_ROLE
        assert m["teamId"] == team["id"]
    finally:
        _delete_team(team["id"])  # 级联删除其成员，保证可重复运行


def test_add_team_members_graceful_skip_unknown():
    """优雅跳过：传入不存在的 uid，解析失败被跳过，返回 added==0, members==[]。"""
    team = _create_team("QA-成员团队-skip")
    try:
        resp = client.post(
            f"/api/channels/teams/{team['id']}/members",
            json={"userIds": ["auth-does-not-exist-qax"]},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["added"] == 0
        assert body["members"] == []
    finally:
        _delete_team(team["id"])


def test_add_team_members_dedup():
    """去重：同一 uid 连续两次添加，第二次 added 不增长。"""
    team = _create_team("QA-成员团队-dedup")
    try:
        first = client.post(
            f"/api/channels/teams/{team['id']}/members",
            json={"userIds": [SEED_AUTH_USER_ID]},
        )
        assert first.status_code == 200
        assert first.json()["added"] == 1

        second = client.post(
            f"/api/channels/teams/{team['id']}/members",
            json={"userIds": [SEED_AUTH_USER_ID]},
        )
        assert second.status_code == 200
        assert second.json()["added"] == 0  # 已存在，去重跳过
        assert second.json()["members"] == []

        # 混合：新用户 + 已存在用户 -> 仅新用户被新增
        mixed = client.post(
            f"/api/channels/teams/{team['id']}/members",
            json={"userIds": [SEED_AUTH_USER_ID, "auth-2"]},
        )
        assert mixed.status_code == 200
        assert mixed.json()["added"] == 1
        assert mixed.json()["members"][0]["userId"] == "auth-2"
    finally:
        _delete_team(team["id"])


def test_add_team_members_team_not_found():
    resp = client.post(
        "/api/channels/teams/team-not-exist-qax/members",
        json={"userIds": [SEED_AUTH_USER_ID]},
    )
    assert resp.status_code == 404
    assert resp.json().get("detail") == "团队不存在"


if __name__ == "__main__":
    import sys

    sys.exit(pytest.main([__file__, "-v"]))

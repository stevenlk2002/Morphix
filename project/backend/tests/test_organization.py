"""组织管理 API 验收测试。

覆盖端点：
- GET /api/org/info
- PUT /api/org/info
- GET /api/org/auth-users
- POST /api/org/auth-users
- PUT /api/org/auth-users/{id}
- DELETE /api/org/auth-users/{id}
- GET /api/org/roles
- POST /api/org/roles
- PUT /api/org/roles/{id}
- DELETE /api/org/roles/{id}
"""
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


# ---- 组织信息 ----

def test_get_org_info_returns_200():
    """GET /api/org/info → 200，返回种子数据。"""
    resp = client.get("/api/org/info")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["orgName"] == "Morphix"
    assert data["contactName"] == "谷一莹"
    assert data["contactPhone"] == "18054265130"


def test_put_org_info_updates_name():
    """PUT /api/org/info → 更新组织名。"""
    resp = client.put("/api/org/info", json={"orgName": "新组织"})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["orgName"] == "新组织"
    # 其他字段不变
    assert data["contactName"] == "谷一莹"


def test_put_org_info_partial_update():
    """PUT /api/org/info 支持部分更新。"""
    resp = client.put("/api/org/info", json={"contactPhone": "13800138000"})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["contactPhone"] == "13800138000"


# ---- 授权用户 ----

def test_list_auth_users_returns_5():
    """GET /api/org/auth-users → 返回 5 条种子数据。"""
    resp = client.get("/api/org/auth-users")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == 5


def test_list_auth_users_filter_account():
    """按 account 筛选。"""
    resp = client.get("/api/org/auth-users?account=admin")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert len(data) == 1
    assert data[0]["account"] == "admin@morphix"


def test_list_auth_users_filter_nickname():
    """按 nickname 筛选。"""
    resp = client.get("/api/org/auth-users?nickname=谷")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert len(data) >= 1


def test_create_auth_user():
    """POST /api/org/auth-users → 创建用户。"""
    resp = client.post("/api/org/auth-users", json={
        "account": "test@morphix",
        "nickname": "测试用户",
        "role": "普通成员",
    })
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["account"] == "test@morphix"
    assert data["nickname"] == "测试用户"
    assert "id" in data


def test_delete_auth_user():
    """DELETE /api/org/auth-users/{id} → 删除用户。"""
    # 先创建一个
    resp = client.post("/api/org/auth-users", json={
        "account": "todelete@morphix",
        "nickname": "待删除",
        "role": "普通成员",
    })
    uid = resp.json()["id"]
    resp2 = client.delete(f"/api/org/auth-users/{uid}")
    assert resp2.status_code == 200, resp2.text
    assert resp2.json()["deleted"] is True


# ---- 角色 ----

def test_list_roles_returns_3():
    """GET /api/org/roles → 返回 3 条种子数据。"""
    resp = client.get("/api/org/roles")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert len(data) == 3


def test_list_roles_filter_keyword():
    """按 keyword 搜索角色。"""
    resp = client.get("/api/org/roles?keyword=管理")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert len(data) >= 1
    assert data[0]["name"] == "管理员"


def test_create_role():
    """POST /api/org/roles → 创建角色。"""
    resp = client.post("/api/org/roles", json={
        "name": "测试角色",
        "description": "测试用",
        "color": "info",
    })
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["name"] == "测试角色"

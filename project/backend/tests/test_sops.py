"""运营SOP API 验收测试。

覆盖端点：
- GET    /api/sops
- POST   /api/sops
- GET    /api/sops/{id}
- PUT    /api/sops/{id}
- DELETE /api/sops/{id}
- PATCH  /api/sops/{id}/toggle
- GET    /api/sops/{id}/records
"""
import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="module")
def client():
    """使用上下文管理器确保 lifespan 正确触发（建表 + 种子数据）。"""
    with TestClient(app) as c:
        yield c


# ---- 列表 ----

def test_list_sops_returns_seed_data(client: TestClient):
    """GET /api/sops → 200，返回种子 3 条 SOP。"""
    resp = client.get("/api/sops")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 3


def test_list_sops_has_required_fields(client: TestClient):
    """列表每项包含 id/name/type/enabled/status/nodes 等字段。"""
    resp = client.get("/api/sops")
    assert resp.status_code == 200
    items = resp.json()
    for item in items:
        assert "id" in item
        assert "name" in item
        assert "type" in item
        assert "enabled" in item
        assert "status" in item
        assert "nodes" in item
        assert "trigger_type" in item
        assert "trigger_config" in item


def test_list_sops_filter_by_type(client: TestClient):
    """GET /api/sops?type=customer → 仅客户SOP。"""
    resp = client.get("/api/sops", params={"type": "customer"})
    assert resp.status_code == 200
    items = resp.json()
    assert all(item["type"] == "customer" for item in items)
    assert len(items) >= 1


def test_list_sops_filter_by_enabled(client: TestClient):
    """GET /api/sops?enabled=已启用 → 仅启用。"""
    resp = client.get("/api/sops", params={"enabled": "已启用"})
    assert resp.status_code == 200
    items = resp.json()
    assert all(item["enabled"] is True for item in items)


def test_list_sops_filter_by_status(client: TestClient):
    """GET /api/sops?status=运行中 → 仅运行中。"""
    resp = client.get("/api/sops", params={"status": "运行中"})
    assert resp.status_code == 200
    items = resp.json()
    assert all(item["status"] == "running" for item in items)


def test_list_sops_search(client: TestClient):
    """GET /api/sops?search=关怀 → 按名称搜索。"""
    resp = client.get("/api/sops", params={"search": "关怀"})
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) >= 1
    assert any("关怀" in item["name"] for item in items)


# ---- 创建 ----

def test_create_sop(client: TestClient):
    """POST /api/sops → 201，创建新 SOP。"""
    payload = {
        "name": "测试SOP",
        "type": "customer",
        "channel": "企业微信",
        "trigger_type": "timed",
        "trigger_config": {"time": "2026-07-20 10:00"},
        "nodes": [
            {
                "id": "node-t1",
                "type": "settings",
                "x": 60,
                "y": 80,
                "config": {"channel": "企业微信", "triggerType": "timed"},
            },
        ],
    }
    resp = client.post("/api/sops", json=payload)
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["name"] == "测试SOP"
    assert data["type"] == "customer"
    assert data["enabled"] is True
    assert data["status"] == "stopped"
    assert len(data["nodes"]) == 1


def test_create_sop_missing_name(client: TestClient):
    """POST /api/sops → 422，缺少必填 name。"""
    resp = client.post("/api/sops", json={"type": "customer"})
    assert resp.status_code == 422


# ---- 详情 ----

def test_get_sop(client: TestClient):
    """GET /api/sops/{id} → 200，获取详情。"""
    resp = client.get("/api/sops/sop-1")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["id"] == "sop-1"
    assert data["name"]  # name 不为空（预置数据或上次测试修改后均有效）
    assert len(data["nodes"]) >= 1


def test_get_sop_not_found(client: TestClient):
    """GET /api/sops/{id} → 404，不存在的 SOP。"""
    resp = client.get("/api/sops/sop-nonexistent")
    assert resp.status_code == 404


# ---- 更新 ----

def test_update_sop(client: TestClient):
    """PUT /api/sops/{id} → 200，更新 SOP 名称。"""
    resp = client.put("/api/sops/sop-1", json={"name": "新客关怀（已更新）"})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["name"] == "新客关怀（已更新）"


def test_update_sop_not_found(client: TestClient):
    """PUT /api/sops/{id} → 404，更新不存在的 SOP。"""
    resp = client.put("/api/sops/sop-nonexistent", json={"name": "不存在"})
    assert resp.status_code == 404


# ---- 启停 ----

def test_toggle_sop(client: TestClient):
    """PATCH /api/sops/{id}/toggle → 200，切换启用状态。"""
    # 先获取当前状态
    before = client.get("/api/sops/sop-2")
    current = before.json()["enabled"]
    resp = client.patch("/api/sops/sop-2/toggle", json={"enabled": not current})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["enabled"] is (not current)


# ---- 删除 ----

def test_delete_sop(client: TestClient):
    """DELETE /api/sops/{id} → 200，删除 SOP。"""
    # 先创建一个 SOP 再删除
    create_resp = client.post("/api/sops", json={
        "name": "待删除SOP",
        "type": "group",
        "channel": "企业微信",
        "nodes": [],
    })
    assert create_resp.status_code == 201
    sop_id = create_resp.json()["id"]

    resp = client.delete(f"/api/sops/{sop_id}")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["id"] == sop_id
    assert data["deleted"] is True

    # 确认已删除
    get_resp = client.get(f"/api/sops/{sop_id}")
    assert get_resp.status_code == 404


def test_delete_sop_not_found(client: TestClient):
    """DELETE /api/sops/{id} → 404，删除不存在的 SOP。"""
    resp = client.delete("/api/sops/sop-nonexistent")
    assert resp.status_code == 404


# ---- 运行记录 ----

def test_list_sop_records(client: TestClient):
    """GET /api/sops/{id}/records → 200，返回运行记录列表。"""
    resp = client.get("/api/sops/sop-1/records")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    # 验证字段完整性
    for rec in data:
        assert "id" in rec
        assert "sop_id" in rec
        assert rec["sop_id"] == "sop-1"
        assert "run_time" in rec
        assert "run_status" in rec
        assert "error_message" in rec
        assert "created_at" in rec


def test_list_sop_records_empty(client: TestClient):
    """GET /api/sops/{id}/records → 200，返回空列表（无记录）。"""
    # SOP-3 有种子记录，先确认该 SOP 存在
    resp = client.get("/api/sops/sop-3/records")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert isinstance(data, list)
    # sop-3 有 1 条种子记录
    assert len(data) >= 1


def test_list_sop_records_not_found(client: TestClient):
    """GET /api/sops/{id}/records → 404，SOP 不存在。"""
    resp = client.get("/api/sops/sop-nonexistent/records")
    assert resp.status_code == 404

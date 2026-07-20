"""客户管理模块接口测试。

使用 TestClient(app) 直接对接后端。
种子数据由 ``MORPHIX_DEV=1`` 启动时写入。
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


# --------------------------------------------------------------------------- #
# 客户列表聚合
# --------------------------------------------------------------------------- #
def test_customers_list_basic():
    """GET /api/customers 返回分页聚合列表。"""
    resp = client.get("/api/customers", params={"page": 1, "pageSize": 10})
    assert resp.status_code == 200
    body = resp.json()
    assert "items" in body
    assert "total" in body
    assert "page" in body
    assert "pageSize" in body
    assert "hasMore" in body
    assert isinstance(body["items"], list)
    assert body["page"] == 1
    assert body["pageSize"] == 10


def test_customers_list_external():
    """type=external 筛选外部客户。"""
    resp = client.get("/api/customers", params={"type": "external", "pageSize": 50})
    assert resp.status_code == 200
    body = resp.json()
    # 至少有 5 个外部客户（种子扩展后 ~30）
    assert len(body["items"]) >= 5
    for item in body["items"]:
        assert item["type"] == "customer"


def test_customers_list_internal():
    """type=internal 筛选内部成员。"""
    resp = client.get("/api/customers", params={"type": "internal", "pageSize": 50})
    assert resp.status_code == 200
    body = resp.json()
    # 至少有 1 个内部成员（种子老数据包含内部成员）
    assert len(body["items"]) >= 1
    for item in body["items"]:
        assert item["type"] == "internal"


def test_customers_list_keyword():
    """keyword 搜索客户名。"""
    resp = client.get("/api/customers", params={"keyword": "通天草", "pageSize": 20})
    assert resp.status_code == 200
    body = resp.json()
    items = body["items"]
    # 至少匹配通天草-林瞰（外部客户）
    assert any("通天草" in it.get("name", "") for it in items)


def test_customers_list_tags_in_item():
    """客户列表项包含 tags 数组（含 groupId/groupName）。"""
    resp = client.get("/api/customers", params={"pageSize": 100})
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["items"]) > 0
    first = body["items"][0]
    assert "tags" in first
    assert isinstance(first["tags"], list)


# --------------------------------------------------------------------------- #
# 客户详情（复用 /api/channels/contacts/{id}）
# --------------------------------------------------------------------------- #
def test_customers_detail():
    """GET /api/channels/contacts/{id} 返回聚合详情。"""
    resp = client.get("/api/channels/contacts/c-cloud")
    assert resp.status_code == 200
    body = resp.json()
    assert "contact" in body
    assert "profile" in body
    assert "communications" in body
    assert "attributes" in body
    # aiSummaryEnabled 应在 profile 中
    profile = body.get("profile") or {}
    assert "aiSummaryEnabled" in profile


# --------------------------------------------------------------------------- #
# 客户档案更新
# --------------------------------------------------------------------------- #
def test_channels_update_profile():
    """PUT /api/channels/contacts/{id}/profile 更新档案。"""
    payload = {
        "remark": "接口测试备注",
        "aiSummaryEnabled": True,
    }
    resp = client.put("/api/channels/contacts/c-cloud/profile", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body.get("remark") == "接口测试备注"
    assert body.get("aiSummaryEnabled") is True

    # 恢复原值
    client.put("/api/channels/contacts/c-cloud/profile", json={
        "remark": "重点跟进客户",
        "aiSummaryEnabled": False,
    })


# --------------------------------------------------------------------------- #
# 标签分组
# --------------------------------------------------------------------------- #
def test_tag_groups_list():
    """GET /api/customer-tag-groups 返回标签组列表。"""
    resp = client.get("/api/customer-tag-groups")
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, list)
    assert len(body) >= 3  # 种子 3 组
    first = body[0]
    assert "id" in first
    assert "name" in first
    assert "isHot" in first
    assert "tags" in first
    assert isinstance(first["tags"], list)


def test_tag_groups_create_and_delete():
    """标签组 CRUD 完整流程。"""
    # Create
    payload = {
        "name": "测试标签组",
        "isHot": False,
        "tags": [{"name": "测试标签A", "color": "blue"}, {"name": "测试标签B", "color": "green"}],
    }
    resp = client.post("/api/customer-tag-groups", json=payload)
    assert resp.status_code == 200
    created = resp.json()
    assert created["name"] == "测试标签组"
    assert created["isHot"] is False
    assert len(created["tags"]) == 2
    gid = created["id"]

    # Update
    resp = client.put(f"/api/customer-tag-groups/{gid}", json={"name": "测试标签组-改", "isHot": True})
    assert resp.status_code == 200

    # Delete
    resp = client.delete(f"/api/customer-tag-groups/{gid}")
    assert resp.status_code == 200
    assert resp.json()["deleted"] is True


# --------------------------------------------------------------------------- #
# 客户分组
# --------------------------------------------------------------------------- #
def test_customer_groups_list():
    """GET /api/customer-groups 返回分组列表。"""
    resp = client.get("/api/customer-groups")
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, list)
    assert len(body) >= 4  # 种子 4 组

    first = body[0]
    assert "id" in first
    assert "name" in first
    assert "type" in first
    assert "count" in first


def test_customer_groups_create():
    """POST /api/customer-groups 新建分组。"""
    payload = {"name": "接口测试分组", "type": "custom"}
    resp = client.post("/api/customer-groups", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "接口测试分组"
    assert body["type"] == "custom"


# --------------------------------------------------------------------------- #
# 沟通记录与自定义属性
# --------------------------------------------------------------------------- #
def test_customers_communications():
    """POST /api/customers/{id}/communications 新增沟通记录。"""
    # 用已有的 customer_profiles id (cp-cloud 对应 c-cloud)
    resp = client.post("/api/customers/cp-cloud/communications", json={
        "content": "接口测试沟通记录",
    })
    assert resp.status_code == 200
    body = resp.json()
    assert "id" in body


def test_customers_attributes():
    """POST /api/customers/{id}/attributes 新增自定义属性。"""
    resp = client.post("/api/customers/cp-cloud/attributes", json={
        "name": "接口测试属性",
        "value": "接口测试值",
    })
    assert resp.status_code == 200
    body = resp.json()
    assert "id" in body


# --------------------------------------------------------------------------- #
# 批量操作
# --------------------------------------------------------------------------- #
def test_batch_ai_summary():
    """PUT /api/customers/batch/ai-summary 批量 AI 总结开关。"""
    payload = {"contactIds": ["c-cloud"], "enabled": True}
    resp = client.put("/api/customers/batch/ai-summary", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body["updated"] >= 1

    # 恢复
    client.put("/api/customers/batch/ai-summary", json={"contactIds": ["c-cloud"], "enabled": False})


def test_batch_tags_add():
    """PUT /api/customers/batch/tags mode=add 批量打标签。"""
    # 先获取一个有效的 tag_id
    tg_resp = client.get("/api/customer-tag-groups")
    tag_groups = tg_resp.json()
    if not tag_groups or not tag_groups[0].get("tags"):
        return  # 无标签可测

    tid = tag_groups[0]["tags"][0]["id"]
    # batch_update_tags 使用 customer_profiles.id（如 "cp-cloud"）
    payload = {"contactIds": ["cp-cloud"], "tagIds": [tid], "mode": "add"}
    resp = client.put("/api/customers/batch/tags", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body["updated"] >= 1

    # 清理
    client.put("/api/customers/batch/tags", json={"contactIds": ["cp-cloud"], "tagIds": [tid], "mode": "remove"})


def test_batch_tags_remove():
    """PUT /api/customers/batch/tags mode=remove 批量移除标签。"""
    tg_resp = client.get("/api/customer-tag-groups")
    tag_groups = tg_resp.json()
    if not tag_groups or not tag_groups[0].get("tags"):
        return
    tid = tag_groups[0]["tags"][0]["id"]

    # 先 add 再 remove
    client.put("/api/customers/batch/tags", json={"contactIds": ["cp-cloud"], "tagIds": [tid], "mode": "add"})
    resp = client.put("/api/customers/batch/tags", json={"contactIds": ["cp-cloud"], "tagIds": [tid], "mode": "remove"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["updated"] >= 1


def test_customer_groups_create_with_members():
    """POST /api/customer-groups/with-members 创建分组含成员。"""
    payload = {"name": "批量测试分组", "type": "custom", "memberIds": ["cp-cloud"]}
    resp = client.post("/api/customer-groups/with-members", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "批量测试分组"
    assert body["count"] == 1
    gid = body["id"]

    # 验证详情含 members
    detail_resp = client.get(f"/api/customer-groups/{gid}")
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert "members" in detail
    assert len(detail["members"]) >= 1


def test_add_members_to_group():
    """POST /api/customer-groups/{id}/members 批量添加成员。"""
    # 先创建一个分组
    create_resp = client.post("/api/customer-groups/with-members", json={
        "name": "添加成员测试分组", "type": "custom", "memberIds": []
    })
    assert create_resp.status_code == 200
    gid = create_resp.json()["id"]

    # 添加成员
    resp = client.post(f"/api/customer-groups/{gid}/members", json={
        "contactIds": ["cp-cloud"]
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] >= 1

    # 获取详情验证
    detail = client.get(f"/api/customer-groups/{gid}").json()
    assert len(detail["members"]) >= 1


# --------------------------------------------------------------------------- #
# 批量删除客户分组
# --------------------------------------------------------------------------- #
def test_customer_groups_batch_delete():
    """POST /api/customer-groups/batch-delete 批量删除分组（级联删除 members）。"""
    # 创建两个测试分组
    resp1 = client.post("/api/customer-groups/with-members", json={
        "name": "批量删除测试A", "type": "custom", "memberIds": ["cp-cloud"]
    })
    resp2 = client.post("/api/customer-groups/with-members", json={
        "name": "批量删除测试B", "type": "custom", "memberIds": ["cp-cloud"]
    })
    assert resp1.status_code == 200
    assert resp2.status_code == 200
    gid1 = resp1.json()["id"]
    gid2 = resp2.json()["id"]

    # 验证分组存在
    assert client.get(f"/api/customer-groups/{gid1}").status_code == 200
    assert client.get(f"/api/customer-groups/{gid2}").status_code == 200

    # 批量删除
    resp = client.post("/api/customer-groups/batch-delete", json={
        "group_ids": [gid1, gid2]
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["deleted"] == 2
    assert body["groupIds"] == [gid1, gid2]

    # 验证分组已删除
    assert client.get(f"/api/customer-groups/{gid1}").status_code == 404
    assert client.get(f"/api/customer-groups/{gid2}").status_code == 404

    # 验证级联删除：customer_group_members 行也应被清理
    # （无直接 members 查询端点，通过 detail 404 间接验证）

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_dashboard_shape():
    response = client.get("/api/dashboard")
    assert response.status_code == 200
    data = response.json()
    # 实际契约（见 app/routers/meta.py dashboard）：gauges/robots/channels/unread
    assert "gauges" in data and "robots" in data and "channels" in data
    assert data["robots"]["created"] >= 1
    assert data["channels"]["added"] >= 1
    assert isinstance(data["gauges"].get("sessionRate", {}).get("percent", 0), int)


def test_handoff_records_status():
    response = client.post("/api/conversations/s-1/handoff", json={"operator": "tester", "reason": "case"})
    assert response.status_code == 200
    assert response.json()["handoffStatus"] == "human"


def test_conversation_messages():
    response = client.get("/api/conversations/s-1/messages?page=2")
    assert response.status_code == 200
    data = response.json()
    assert data["conversationId"] == "s-1"
    assert len(data["items"]) >= 3


def test_workflow_detail():
    response = client.get("/api/workflows/w-1")
    assert response.status_code == 200
    assert "definition" in response.json()


def test_create_sop():
    response = client.post("/api/sops", json={"name": "高意向预约演示", "trigger": "tag=high"})
    assert response.status_code == 200
    assert response.json()["status"] == "enabled"


def test_create_and_train_bot():
    response = client.post("/api/bots", json={"name": "测试训练助手", "project": "QA", "workflow": "测试流程", "tone": "严谨", "trainingPrompt": "只回答测试问题"})
    assert response.status_code == 200
    bot_id = response.json()["id"]
    train_response = client.post(f"/api/bots/{bot_id}/train")
    assert train_response.status_code == 200
    assert train_response.json()["status"] == "online"


def test_channel_accounts_and_tags():
    channel_response = client.post("/api/channel-accounts", json={"channel": "企业微信", "accountName": "测试账号", "boundBot": "测试训练助手", "dailyQuota": 80})
    assert channel_response.status_code == 200
    assert channel_response.json()["status"] == "online"
    tag_response = client.post("/api/customer-tags", json={"name": "测试标签", "color": "green", "rule": "消息包含测试"})
    assert tag_response.status_code == 200
    assert tag_response.json()["name"] == "测试标签"


def test_update_workflow_node():
    response = client.patch("/api/workflows/w-1/nodes/wn-2", json={"label": "客户分层筛选", "nodeType": "condition", "config": {"field": "level"}})
    assert response.status_code == 200
    assert response.json()["label"] == "客户分层筛选"


# ---- 编排工作流持久化测试 ----


def test_orchestration_save_workflow():
    """PUT 保存编排工作流 → 200"""
    payload = {
        "botId": "yefengqiu",
        "version": 1,
        "lastEdited": "2026-07-19T12:00:00.000Z",
        "nodes": [{"id": "n1", "type": "trigger", "position": {"x": 0, "y": 0}, "data": {}}],
        "edges": [{"id": "e1", "source": "n1", "target": "n2", "sourceHandle": "out", "targetHandle": "in"}],
    }
    response = client.put("/api/orchestration/workflows/yefengqiu", json=payload)
    assert response.status_code == 200
    assert response.json()["botId"] == "yefengqiu"
    assert response.json()["saved"] is True


def test_orchestration_load_workflow():
    """GET 加载刚保存的工作流 → 200，data 完整恢复"""
    # 先保存
    payload = {
        "botId": "testbot",
        "version": 2,
        "lastEdited": "2026-07-19T14:00:00.000Z",
        "nodes": [{"id": "n1", "type": "action", "position": {"x": 100, "y": 200}, "data": {"label": "step1"}}],
        "edges": [],
    }
    client.put("/api/orchestration/workflows/testbot", json=payload)

    # 再加载
    response = client.get("/api/orchestration/workflows/testbot")
    assert response.status_code == 200
    data = response.json()
    assert data["botId"] == "testbot"
    assert data["version"] == 2
    assert data["lastEdited"] == "2026-07-19T14:00:00.000Z"
    assert len(data["nodes"]) == 1
    assert data["nodes"][0]["id"] == "n1"
    assert data["nodes"][0]["data"]["label"] == "step1"
    assert "updatedAt" in data


def test_orchestration_load_not_found():
    """GET 不存在的工作流 → 404"""
    response = client.get("/api/orchestration/workflows/nonexistent")
    assert response.status_code == 404


def test_orchestration_delete_workflow():
    """DELETE 删除已存在工作流 → 200"""
    # 先保存
    payload = {
        "botId": "todelete",
        "version": 1,
        "lastEdited": "2026-07-19T10:00:00.000Z",
        "nodes": [],
        "edges": [],
    }
    client.put("/api/orchestration/workflows/todelete", json=payload)

    # 再删除
    response = client.delete("/api/orchestration/workflows/todelete")
    assert response.status_code == 200
    assert response.json()["botId"] == "todelete"
    assert response.json()["deleted"] is True

    # 再次 GET 应返回 404
    get_response = client.get("/api/orchestration/workflows/todelete")
    assert get_response.status_code == 404


def test_orchestration_delete_not_found():
    """DELETE 不存在的工作流 → 404"""
    response = client.delete("/api/orchestration/workflows/nonexistent")
    assert response.status_code == 404


# ---- 训练模块：total_count 持久化回归测试 ----
# 覆盖 create_message 的 recompute 分支（此前 14 用例均未走到该路径，掩盖了 Bug）。


def test_training_message_total_count_persist():
    """POST user+ai 消息后，GET records 读到的 totalCount 应持久化为 1（仅统计 role='ai'）。

    顺带覆盖 _recompute_record_counts 在 create_message 后被调用（不再 500 / AttributeError）。
    """
    # 1) 新建训练记录（totalCount 初始为 0）
    rec = client.post("/api/bots/yefengqiu/training/records", json={"title": "回归测试-totalCount"})
    assert rec.status_code == 200, rec.text
    record_id = rec.json()["id"]
    assert rec.json()["totalCount"] == 0

    try:
        # 2) 写入 1 条 user + 1 条 ai 消息
        u = client.post(
            f"/api/training/records/{record_id}/messages",
            json={"role": "user", "content": "你好"},
        )
        assert u.status_code == 200, u.text
        a = client.post(
            f"/api/training/records/{record_id}/messages",
            json={"role": "ai", "content": "您好", "recordRef": "ref-1"},
        )
        assert a.status_code == 200, a.text

        # 3) 刷新 GET records → totalCount 持久化为 1，good/bad 仍为 0
        recs = client.get(f"/api/bots/yefengqiu/training/records").json()
        target = next(r for r in recs if r["id"] == record_id)
        assert target["totalCount"] == 1, target
        assert target["goodCount"] == 0 and target["badCount"] == 0, target
    finally:
        # 4) 清理：删除该记录，避免污染种子库
        client.delete(f"/api/training/records/{record_id}")

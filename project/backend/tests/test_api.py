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
    assert data["stats"]["activeProjects"] >= 1
    assert len(data["bots"]) >= 1
    assert len(data["sessions"]) >= 1


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

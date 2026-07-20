from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_message_logs_list_yefengqiu():
    """GET /api/bots/yefengqiu/message-logs → 3 条，含两个 demo id。"""
    resp = client.get("/api/bots/yefengqiu/message-logs")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 3
    assert data["page"] == 1
    assert data["hasMore"] is False
    ids = {it["id"] for it in data["items"]}
    assert "AI2075172858125025280" in ids
    assert "AI2075167178402115584" in ids


def test_message_logs_detail_demo_nodes():
    """demo id 详情：三段节点，顺序正确，input/output/code 均非空。"""
    resp = client.get("/api/bots/yefengqiu/message-logs/AI2075172858125025280")
    assert resp.status_code == 200
    d = resp.json()
    assert d["robot"] == "野风秋大健康机器人"
    assert [n["name"] for n in d["nodes"]] == ["用户输入", "对话记录获取", "AI对话"]
    assert d["nodes"][0]["runtime"] == "0.005s"
    assert d["nodes"][2]["runtime"] == "2.956s"
    for n in d["nodes"]:
        assert n["input"] and n["output"] and n["code"]


def test_message_logs_detail_not_found():
    """不存在的 ai_reply_id → 404。"""
    resp = client.get("/api/bots/yefengqiu/message-logs/MISSING")
    assert resp.status_code == 404


def test_message_logs_wrong_bot_scope():
    """demo id 属于 yefengqiu，用 fanfuni 查 → 404（bot 作用域隔离）。"""
    resp = client.get("/api/bots/fanfuni/message-logs/AI2075172858125025280")
    assert resp.status_code == 404


def test_message_logs_fanfuni_four_nodes():
    """fanfuni 日志详情：四节点工作流（用户输入/知识库搜索/AI对话/消息输出）。"""
    resp = client.get("/api/bots/fanfuni/message-logs/AI2075001234567890001")
    assert resp.status_code == 200
    d = resp.json()
    assert [n["name"] for n in d["nodes"]] == ["用户输入", "知识库搜索", "AI对话", "消息输出"]
    assert d["nodes"][1]["icon"] == "search"


def test_message_logs_status_filter():
    """fanfuni 按 status=失败 筛选 → 仅 1 条。"""
    resp = client.get("/api/bots/fanfuni/message-logs", params={"status": "失败"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["status"] == "失败"

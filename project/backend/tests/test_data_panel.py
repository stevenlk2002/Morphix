"""数据面板 API 验收测试。

覆盖端点：
- GET /api/data-panel/metrics
- GET /api/data-panel/filter-options
"""
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


# ---- GET /api/data-panel/metrics ----


def test_get_metrics_returns_200_with_total_and_daily():
    """GET /api/data-panel/metrics → 200，返回 total 和 daily 字段。"""
    resp = client.get("/api/data-panel/metrics")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "total" in data
    assert "daily" in data


def test_get_metrics_daily_has_7_days():
    """每日数据包含 7 天记录。"""
    resp = client.get("/api/data-panel/metrics")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["daily"]) == 7


def test_get_metrics_total_matches_prototype_seed():
    """总数与原型 chart mock 数据加和一致。"""
    resp = client.get("/api/data-panel/metrics")
    assert resp.status_code == 200
    total = resp.json()["total"]
    # 原型 chart mock 数据逐日加和：
    # 新增: 1+0+1+0+0+0+3=5, 托管: 0+0+0+0+0+1+2=3, 处理: 0+0+0+0+0+0+1=1
    # 总消息: 0+0+0+0+0+1+4=5, 机器人消息: 0+0+0+0+0+1+2=3, 转人工: 0
    assert total["new_sessions"] == 5
    assert total["hosted_sessions"] == 3
    assert total["bot_processed_sessions"] == 1
    assert total["total_messages"] == 5
    assert total["bot_processed_messages"] == 3
    assert total["bot_transfers"] == 0


def test_get_metrics_daily_has_required_fields():
    """每日记录包含所有必要字段（与前端类型一致）。"""
    resp = client.get("/api/data-panel/metrics")
    assert resp.status_code == 200
    for item in resp.json()["daily"]:
        assert "date" in item
        assert "new_sessions" in item
        assert "hosted_sessions" in item
        assert "bot_processed_sessions" in item
        assert "total_messages" in item
        assert "bot_processed_messages" in item
        assert "bot_transfers" in item
        assert "msg_rate" in item
        assert "session_rate" in item
        assert "transfer_rate" in item


def test_get_metrics_with_filter_params():
    """带筛选参数请求仍返回 200（P0 忽略参数但不应报错）。"""
    resp = client.get(
        "/api/data-panel/metrics",
        params={
            "start": "2026-07-03",
            "end": "2026-07-09",
            "channel": "企业微信",
            "account": "竹绿-健康",
            "bot": "野风秋大健康机器人",
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert len(data["daily"]) == 7


# ---- GET /api/data-panel/filter-options ----


def test_get_filter_options_returns_200():
    """GET /api/data-panel/filter-options → 200，返回三个选项列表。"""
    resp = client.get("/api/data-panel/filter-options")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "channels" in data
    assert "accounts" in data
    assert "bots" in data
    assert len(data["channels"]) >= 3
    assert len(data["accounts"]) >= 2
    assert len(data["bots"]) >= 2

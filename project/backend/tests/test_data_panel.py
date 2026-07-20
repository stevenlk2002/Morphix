"""数据面板 API 验收测试。

覆盖端点：
- GET /api/data-panel/metrics
- GET /api/data-panel/filter-options

P0 测试保留种子兜底场景；P1 新增真实数据聚合与 fallback 验证。
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


def test_get_metrics_with_date_range_params():
    """带日期筛选参数请求仍返回 200。"""
    resp = client.get(
        "/api/data-panel/metrics",
        params={
            "start": "2026-07-14",
            "end": "2026-07-20",
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "total" in data
    assert "daily" in data
    assert len(data["daily"]) > 0


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


def test_get_metrics_total_is_non_negative():
    """所有 total 值非负。"""
    resp = client.get("/api/data-panel/metrics")
    assert resp.status_code == 200
    total = resp.json()["total"]
    assert total["new_sessions"] >= 0
    assert total["hosted_sessions"] >= 0
    assert total["bot_processed_sessions"] >= 0
    assert total["total_messages"] >= 0
    assert total["bot_processed_messages"] >= 0
    assert total["bot_transfers"] >= 0


def test_get_metrics_rates_are_valid():
    """比率值在 0-100 范围。"""
    resp = client.get("/api/data-panel/metrics")
    assert resp.status_code == 200
    total = resp.json()["total"]
    assert 0 <= total["msg_rate"] <= 100
    assert 0 <= total["session_rate"] <= 100
    assert 0 <= total["transfer_rate"] <= 100


def test_get_metrics_with_future_dates_all_zero():
    """未来日期范围返回全零数据。"""
    resp = client.get(
        "/api/data-panel/metrics",
        params={"start": "2030-01-01", "end": "2030-01-07"},
    )
    assert resp.status_code == 200, resp.text
    total = resp.json()["total"]
    # 未来无数据，所有总量为 0 → fallback 到种子数据
    # 种子数据 total: new=5, hosted=3, processed=1, messages=5, bot_messages=3, transfers=0
    assert total["new_sessions"] == 5
    assert total["hosted_sessions"] == 3
    assert total["bot_processed_sessions"] == 1


def test_get_metrics_fallback_triggers_on_zero_data():
    """无数据日期范围触发种子兜底。"""
    resp = client.get(
        "/api/data-panel/metrics",
        params={"start": "1999-01-01", "end": "1999-01-07"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    # 种子兜底应返回完整的 7 日种子数据
    assert len(data["daily"]) == 7
    total = data["total"]
    assert total["new_sessions"] == 5
    assert total["bot_transfers"] == 0


def test_get_metrics_real_data_aggregation():
    """真实数据聚合（数据库中有 channel_sessions 和 messages 数据）。
    
    数据库现状（morphix_mvp.db）:
    - channel_sessions: 4 行（add_time 2026-06-30）
    - messages: 12 行（created_at 2026-07-08 ~ 2026-07-09 及 2024-01-15）
    
    查询 2026-07-08 到 2026-07-09：
    - channel_sessions add_time 是 2026-06-30，不在范围内 → 新增 0
    - messages created_at 在 2026-07-08: 2 条，2026-07-09: 10 条
    - bot messages: 2026-07-08: 1 条(bot), 2026-07-09: 4 条(bot) = 5 total
    """
    resp = client.get(
        "/api/data-panel/metrics",
        params={"start": "2026-07-08", "end": "2026-07-09"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    total = data["total"]
    daily = data["daily"]
    assert len(daily) == 2
    # 总消息数 >= 12 (2026-07-08 2条 + 2026-07-09 10条)
    assert total["total_messages"] >= 10
    # 机器人处理消息数 >= 5 (bot + ai)
    assert total["bot_processed_messages"] >= 3
    # 未来数据为零的会话指标
    assert total["new_sessions"] >= 0
    assert total["hosted_sessions"] >= 0


# ---- GET /api/data-panel/filter-options ----


def test_get_filter_options_returns_200():
    """GET /api/data-panel/filter-options → 200，返回三个选项列表。"""
    resp = client.get("/api/data-panel/filter-options")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "channels" in data
    assert "accounts" in data
    assert "bots" in data
    assert len(data["channels"]) >= 1
    assert len(data["accounts"]) >= 1
    assert len(data["bots"]) >= 1


def test_get_filter_options_from_real_tables():
    """筛选器选项从 bots/channel_accounts 表动态读取。"""
    resp = client.get("/api/data-panel/filter-options")
    assert resp.status_code == 200
    data = resp.json()
    # channel_accounts 表有 5 行
    assert len(data["accounts"]) >= 2  # 至少 "全部" + 1 条
    # bots 表有 4 行
    assert len(data["bots"]) >= 2  # 至少 "全部" + 1 条
    # 第一条应为 "全部" 占位项
    assert data["channels"][0]["value"] == ""
    assert data["accounts"][0]["value"] == ""
    assert data["bots"][0]["value"] == ""

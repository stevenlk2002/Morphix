"""数据面板路由。

端点：
- GET /api/data-panel/metrics        → 指标聚合（total + daily）
- GET /api/data-panel/filter-options  → 筛选器下拉选项

P0 阶段返回种子 mock 数据（与原型完全一致）。
后续接入真实表时替换 _query_metrics() 实现即可。
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Query

from ..data_panel_schemas import (
    DailyMetric,
    DataPanelFilterOptionsResponse,
    DataPanelMetricsResponse,
    FilterOption,
    MetricsTotal,
)

router = APIRouter(prefix="/data-panel", tags=["data-panel"])

# ---------- 种子数据（与原型 index.html 5103-5111 行完全一致） ----------

_SEED_DAILY: list[dict] = [
    {"date": "2026-07-03", "新增会话数": 1, "托管会话数": 0, "机器人处理会话数": 0, "总消息数": 0, "机器人处理消息数": 0, "机器人转人工数": 0},
    {"date": "2026-07-04", "新增会话数": 0, "托管会话数": 0, "机器人处理会话数": 0, "总消息数": 0, "机器人处理消息数": 0, "机器人转人工数": 0},
    {"date": "2026-07-05", "新增会话数": 1, "托管会话数": 0, "机器人处理会话数": 0, "总消息数": 0, "机器人处理消息数": 0, "机器人转人工数": 0},
    {"date": "2026-07-06", "新增会话数": 0, "托管会话数": 0, "机器人处理会话数": 0, "总消息数": 0, "机器人处理消息数": 0, "机器人转人工数": 0},
    {"date": "2026-07-07", "新增会话数": 0, "托管会话数": 0, "机器人处理会话数": 0, "总消息数": 0, "机器人处理消息数": 0, "机器人转人工数": 0},
    {"date": "2026-07-08", "新增会话数": 0, "托管会话数": 1, "机器人处理会话数": 0, "总消息数": 1, "机器人处理消息数": 1, "机器人转人工数": 0},
    {"date": "2026-07-09", "新增会话数": 3, "托管会话数": 2, "机器人处理会话数": 1, "总消息数": 4, "机器人处理消息数": 2, "机器人转人工数": 0},
]


def _compute_rates(d: dict) -> dict:
    """根据原型 JS 公式计算三个比率（保留 1 位小数）。"""
    total_msg: int = d.get("总消息数", 0)
    hosted: int = d.get("托管会话数", 0)
    bot_msg: int = d.get("机器人处理消息数", 0)
    bot_sessions: int = d.get("机器人处理会话数", 0)
    transfers: int = d.get("机器人转人工数", 0)

    msg_rate: float = round((bot_msg / total_msg) * 100, 1) if total_msg > 0 else 0.0
    session_rate: float = round((bot_sessions / hosted) * 100, 1) if hosted > 0 else 0.0
    transfer_rate: float = round((transfers / bot_msg) * 100, 1) if bot_msg > 0 else 0.0

    return {
        "msg_rate": msg_rate,
        "session_rate": session_rate,
        "transfer_rate": transfer_rate,
    }


def _query_metrics(
    start: Optional[str] = None,
    end: Optional[str] = None,
    channel: Optional[str] = None,
    account: Optional[str] = None,
    bot: Optional[str] = None,
) -> DataPanelMetricsResponse:
    """查询指标数据。

    P0：返回种子 mock。后续替换为真实 SQL 查询。
    """
    # 保留参数以便后续接入真实数据源
    _ = (start, end, channel, account, bot)

    daily: list[DailyMetric] = []
    for raw in _SEED_DAILY:
        rates = _compute_rates(raw)
        daily.append(
            DailyMetric(
                date=raw["date"],
                new_sessions=raw["新增会话数"],
                hosted_sessions=raw["托管会话数"],
                bot_processed_sessions=raw["机器人处理会话数"],
                total_messages=raw["总消息数"],
                bot_processed_messages=raw["机器人处理消息数"],
                bot_transfers=raw["机器人转人工数"],
                msg_rate=rates["msg_rate"],
                session_rate=rates["session_rate"],
                transfer_rate=rates["transfer_rate"],
            )
        )

    # 聚合 total
    total_new = sum(d["新增会话数"] for d in _SEED_DAILY)
    total_hosted = sum(d["托管会话数"] for d in _SEED_DAILY)
    total_processed = sum(d["机器人处理会话数"] for d in _SEED_DAILY)
    total_messages = sum(d["总消息数"] for d in _SEED_DAILY)
    total_bot_messages = sum(d["机器人处理消息数"] for d in _SEED_DAILY)
    total_transfers = sum(d["机器人转人工数"] for d in _SEED_DAILY)

    total_msg_rate: float = round((total_bot_messages / total_messages) * 100, 1) if total_messages > 0 else 0.0
    total_session_rate: float = round((total_processed / total_hosted) * 100, 1) if total_hosted > 0 else 0.0
    total_transfer_rate: float = round((total_transfers / total_bot_messages) * 100, 1) if total_bot_messages > 0 else 0.0

    total = MetricsTotal(
        new_sessions=total_new,
        hosted_sessions=total_hosted,
        bot_processed_sessions=total_processed,
        total_messages=total_messages,
        bot_processed_messages=total_bot_messages,
        bot_transfers=total_transfers,
        msg_rate=total_msg_rate,
        session_rate=total_session_rate,
        transfer_rate=total_transfer_rate,
    )

    return DataPanelMetricsResponse(total=total, daily=daily)


# ---------- 路由 ----------


@router.get("/metrics", response_model=DataPanelMetricsResponse)
async def get_metrics(
    start: Optional[str] = Query(None, description="开始日期 YYYY-MM-DD"),
    end: Optional[str] = Query(None, description="结束日期 YYYY-MM-DD"),
    channel: Optional[str] = Query(None, description="渠道类型：企业微信/微信/WhatsApp"),
    account: Optional[str] = Query(None, description="托管账号 ID"),
    bot: Optional[str] = Query(None, description="托管机器人 ID"),
) -> DataPanelMetricsResponse:
    """获取数据面板指标（聚合 total + 每日 daily）。

    当前 P0 返回种子 mock 数据，与原型完全一致。
    后续接入真实数据表时替换 _query_metrics() 实现。
    """
    return _query_metrics(
        start=start,
        end=end,
        channel=channel,
        account=account,
        bot=bot,
    )


# ---------- 筛选器选项（预留） ----------

_SEED_CHANNELS: list[FilterOption] = [
    FilterOption(value="", label="全部"),
    FilterOption(value="企业微信", label="企业微信"),
    FilterOption(value="微信", label="微信"),
    FilterOption(value="WhatsApp", label="WhatsApp"),
]

_SEED_ACCOUNTS: list[FilterOption] = [
    FilterOption(value="", label="全部"),
    FilterOption(value="竹绿-健康", label="竹绿-健康"),
    FilterOption(value="恒康倍力", label="恒康倍力"),
]

_SEED_BOTS: list[FilterOption] = [
    FilterOption(value="", label="全部"),
    FilterOption(value="野风秋大健康机器人", label="野风秋大健康机器人"),
    FilterOption(value="AI客服-1", label="AI客服-1"),
]


@router.get("/filter-options", response_model=DataPanelFilterOptionsResponse)
async def get_filter_options() -> DataPanelFilterOptionsResponse:
    """获取筛选器下拉选项（渠道/账号/机器人）。

    P0 返回种子数据。后续可接入 /api/channels/accounts 等真实端点。
    """
    return DataPanelFilterOptionsResponse(
        channels=_SEED_CHANNELS,
        accounts=_SEED_ACCOUNTS,
        bots=_SEED_BOTS,
    )

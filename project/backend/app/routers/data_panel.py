"""数据面板路由。

端点：
- GET /api/data-panel/metrics        → 指标聚合（total + daily）
- GET /api/data-panel/filter-options  → 筛选器下拉选项

P1 阶段：从真实数据库（channel_sessions/hosting_sessions/messages）聚合数据。
若所有指标为 0，fallback 到种子数据。
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Query

from ..data_panel_schemas import (
    DailyMetric,
    DataPanelFilterOptionsResponse,
    DataPanelMetricsResponse,
    FilterOption,
    MetricsTotal,
)
from ..database import get_backend

router = APIRouter(prefix="/data-panel", tags=["data-panel"])

# ---------- 种子兜底数据 ----------

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


def _build_where(field: str, start: str, end: str, extra: dict[str, str]) -> str:
    """构建公共日期筛选 + 可选渠道/账号/机器人条件的 WHERE 子句。"""
    clauses = [f"date({field}) BETWEEN ? AND ?"]
    for col, val in extra.items():
        if val:
            clauses.append(f"{col} = ?")
    return " AND ".join(clauses)


def _build_params(start: str, end: str, extra: dict[str, str]) -> tuple:
    """构建对应 _build_where 的参数元组。"""
    params: list = [start, end]
    for val in extra.values():
        if val:
            params.append(val)
    return tuple(params)


def _query_seed(start: str, end: str) -> DataPanelMetricsResponse:
    """回退到种子数据。"""
    _ = (start, end)

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


def _query_metrics(
    start: Optional[str] = None,
    end: Optional[str] = None,
    channel: Optional[str] = None,
    account: Optional[str] = None,
    bot: Optional[str] = None,
) -> DataPanelMetricsResponse:
    """从真实数据库聚合指标数据。

    默认日期范围：最近 7 天（含今天）。
    若所有聚合值均为 0，fallback 到种子数据。
    """
    backend = get_backend()

    # 默认日期范围
    today = date.today().isoformat()
    week_ago = (date.today() - timedelta(days=6)).isoformat()
    start = start or week_ago
    end = end or today

    # 构建筛选条件（channel → channel 字段，account → account_id 字段，bot → hosted_bot_id 字段）
    session_filters: dict[str, str] = {}
    msg_filters: dict[str, str] = {}
    if channel:
        session_filters["channel"] = channel
    if account:
        session_filters["account_id"] = account
    if bot:
        session_filters["hosted_bot_id"] = bot

    # ---- 总数查询 ----
    # 1) 新增会话数
    where_sess = _build_where("add_time", start, end, session_filters)
    params_sess = _build_params(start, end, session_filters)
    rows = backend.query(
        f"SELECT COUNT(*) AS cnt FROM channel_sessions WHERE {where_sess}",
        params_sess,
    )
    total_new_sessions = rows[0]["cnt"] if rows else 0

    # 2) 托管会话数（hosted_status='hosted' 的会话）
    params_hosted = _build_params(start, end, {**session_filters, "hosted_status": "hosted"})
    where_hosted = _build_where("add_time", start, end, {**session_filters, "hosted_status": "hosted"})
    rows = backend.query(
        f"SELECT COUNT(*) AS cnt FROM channel_sessions WHERE {where_hosted}",
        params_hosted,
    )
    total_hosted_sessions = rows[0]["cnt"] if rows else 0

    # 3) 机器人处理会话数（hosted_bot_id IS NOT NULL）
    # Note: bot filter already sets hosted_bot_id, so skip bot from non-null condition
    bot_non_null_filters = dict(session_filters)
    bot_non_null_filters["hosted_bot_id IS NOT NULL"] = ""
    # Rebuild where without the bot filter value interfering
    bot_null_clauses = [f"date(add_time) BETWEEN ? AND ?"]
    bot_null_params: list = [start, end]
    if channel:
        bot_null_clauses.append("channel = ?")
        bot_null_params.append(channel)
    if account:
        bot_null_clauses.append("account_id = ?")
        bot_null_params.append(account)
    bot_null_clauses.append("hosted_bot_id IS NOT NULL")
    rows = backend.query(
        f"SELECT COUNT(*) AS cnt FROM channel_sessions WHERE {' AND '.join(bot_null_clauses)}",
        tuple(bot_null_params),
    )
    total_bot_sessions = rows[0]["cnt"] if rows else 0

    # 4) 总消息数
    rows = backend.query(
        f"SELECT COUNT(*) AS cnt FROM messages WHERE date(created_at) BETWEEN ? AND ?",
        (start, end),
    )
    total_messages = rows[0]["cnt"] if rows else 0

    # 5) 机器人处理消息数（sender_type IN ('bot', 'ai')）
    rows = backend.query(
        f"SELECT COUNT(*) AS cnt FROM messages WHERE date(created_at) BETWEEN ? AND ? AND sender_type IN ('bot', 'ai')",
        (start, end),
    )
    total_bot_messages = rows[0]["cnt"] if rows else 0

    # 6) 机器人转人工数（sender_type='system' AND content LIKE '%转人工%'）
    rows = backend.query(
        f"SELECT COUNT(*) AS cnt FROM messages WHERE date(created_at) BETWEEN ? AND ? AND sender_type = 'system' AND content LIKE ?",
        (start, end, "%转人工%"),
    )
    total_transfers = rows[0]["cnt"] if rows else 0

    # ---- 每日聚合（GROUP BY date）----
    # 使用子查询或逐日查询构建 daily 数组
    # 生成日期范围列表
    date_list: list[str] = []
    d = date.fromisoformat(start)
    d_end = date.fromisoformat(end)
    while d <= d_end:
        date_list.append(d.isoformat())
        d += timedelta(days=1)

    # 逐日查询（SQLite GROUP BY date 在无数据日会缺行，手动补齐）
    daily: list[DailyMetric] = []
    for day in date_list:
        # 新增会话数
        params_d = tuple([day] + list(params_sess[1:]))
        where_d = _build_where("add_time", day, day, session_filters)
        rows = backend.query(
            f"SELECT COUNT(*) AS cnt FROM channel_sessions WHERE {where_d}",
            params_d,
        )
        new_sess = rows[0]["cnt"] if rows else 0

        # 托管会话数
        params_dh = tuple([day] + list(params_hosted[1:]))
        where_dh = _build_where("add_time", day, day, {**session_filters, "hosted_status": "hosted"})
        rows = backend.query(
            f"SELECT COUNT(*) AS cnt FROM channel_sessions WHERE {where_dh}",
            params_dh,
        )
        hosted_sess = rows[0]["cnt"] if rows else 0

        # 机器人处理会话数
        rows = backend.query(
            f"SELECT COUNT(*) AS cnt FROM channel_sessions WHERE {' AND '.join(bot_null_clauses)}",
            tuple([day] + bot_null_params[1:]),
        )
        bot_sess = rows[0]["cnt"] if rows else 0

        # 总消息数
        rows = backend.query(
            f"SELECT COUNT(*) AS cnt FROM messages WHERE date(created_at) BETWEEN ? AND ?",
            (day, day),
        )
        day_msgs = rows[0]["cnt"] if rows else 0

        # 机器人处理消息数
        rows = backend.query(
            f"SELECT COUNT(*) AS cnt FROM messages WHERE date(created_at) BETWEEN ? AND ? AND sender_type IN ('bot', 'ai')",
            (day, day),
        )
        day_bot_msgs = rows[0]["cnt"] if rows else 0

        # 机器人转人工数
        rows = backend.query(
            f"SELECT COUNT(*) AS cnt FROM messages WHERE date(created_at) BETWEEN ? AND ? AND sender_type = 'system' AND content LIKE ?",
            (day, day, "%转人工%"),
        )
        day_transfers = rows[0]["cnt"] if rows else 0

        raw = {
            "日期": day,
            "新增会话数": new_sess,
            "托管会话数": hosted_sess,
            "机器人处理会话数": bot_sess,
            "总消息数": day_msgs,
            "机器人处理消息数": day_bot_msgs,
            "机器人转人工数": day_transfers,
        }
        rates = _compute_rates(raw)
        daily.append(
            DailyMetric(
                date=day,
                new_sessions=new_sess,
                hosted_sessions=hosted_sess,
                bot_processed_sessions=bot_sess,
                total_messages=day_msgs,
                bot_processed_messages=day_bot_msgs,
                bot_transfers=day_transfers,
                msg_rate=rates["msg_rate"],
                session_rate=rates["session_rate"],
                transfer_rate=rates["transfer_rate"],
            )
        )

    # ---- 种子兜底：若所有总数均为 0 ----
    all_zero = (
        total_new_sessions == 0
        and total_hosted_sessions == 0
        and total_bot_sessions == 0
        and total_messages == 0
        and total_bot_messages == 0
        and total_transfers == 0
    )
    if all_zero:
        return _query_seed(start, end)

    # ---- 比率计算 ----
    total_msg_rate: float = round((total_bot_messages / total_messages) * 100, 1) if total_messages > 0 else 0.0
    total_session_rate: float = round((total_bot_sessions / total_hosted_sessions) * 100, 1) if total_hosted_sessions > 0 else 0.0
    total_transfer_rate: float = round((total_transfers / total_bot_messages) * 100, 1) if total_bot_messages > 0 else 0.0

    total = MetricsTotal(
        new_sessions=total_new_sessions,
        hosted_sessions=total_hosted_sessions,
        bot_processed_sessions=total_bot_sessions,
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
    channel: Optional[str] = Query(None, description="渠道类型：企业微信/微信/邮箱"),
    account: Optional[str] = Query(None, description="托管账号 ID"),
    bot: Optional[str] = Query(None, description="托管机器人 ID"),
) -> DataPanelMetricsResponse:
    """获取数据面板指标（聚合 total + 每日 daily）。"""
    return _query_metrics(
        start=start,
        end=end,
        channel=channel,
        account=account,
        bot=bot,
    )


# ---------- 筛选器选项 ----------


@router.get("/filter-options", response_model=DataPanelFilterOptionsResponse)
async def get_filter_options() -> DataPanelFilterOptionsResponse:
    """获取筛选器下拉选项（渠道/账号/机器人），从真实表动态读取。"""
    backend = get_backend()

    # 渠道：从 channel_accounts 表取 distinct channel
    rows = backend.query("SELECT DISTINCT channel FROM channel_accounts WHERE channel != ''")
    channels: list[FilterOption] = [FilterOption(value="", label="全部")]
    for r in rows:
        ch = r["channel"]
        if ch:
            channels.append(FilterOption(value=ch, label=ch))

    # 账号：从 channel_accounts 表读取
    rows = backend.query("SELECT id, account_name FROM channel_accounts")
    accounts: list[FilterOption] = [FilterOption(value="", label="全部")]
    for r in rows:
        accounts.append(FilterOption(value=r["id"], label=r["account_name"]))

    # 机器人：从 bots 表读取
    rows = backend.query("SELECT id, name FROM bots")
    bots: list[FilterOption] = [FilterOption(value="", label="全部")]
    for r in rows:
        bots.append(FilterOption(value=r["id"], label=r["name"]))

    return DataPanelFilterOptionsResponse(
        channels=channels,
        accounts=accounts,
        bots=bots,
    )

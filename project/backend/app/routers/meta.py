"""元信息路由：health / metrics / dashboard / audit。"""
from __future__ import annotations

from fastapi import APIRouter

from ..config import settings
from ..database import get_backend
from ..fixtures import dashboard_static
from ..observability import metrics_store
from ..repositories import AuditRepository, BotRepository, ChannelRepository

router = APIRouter(tags=["meta"])


@router.get("/health")
def health():
    """健康检查（增强版）。

    MVP 仅检查数据库连通性；升级时可扩展：
    - 依赖服务状态（Redis / MQ / pgvector）
    - 磁盘空间
    - 队列积压
    """
    backend = get_backend()
    try:
        backend.query_one("SELECT 1 AS ok")
    except Exception as e:
        return {
            "status": "unhealthy",
            "service": "morphix-backend",
            "error": str(e),
        }
    return {
        "status": "healthy",
        "service": "morphix-backend",
        "database": str(settings.sqlite_path),
    }


@router.get("/metrics")
def metrics():
    """P99 性能指标（性能落地要求之一）。

    返回全局与各路由的 P50/P95/P99/max，用于观测接口耗时分布。
    慢请求阈值由配置控制（默认 3000ms）。
    """
    return metrics_store.snapshot()


@router.get("/dashboard")
def dashboard():
    """首页概览数据。

    返回前端 Home.jsx 约定的契约结构：
    - gauges: 三档会话处理占比（来自真实 sessions 数据）
    - robots: 机器人汇总（created/online/activeTemplates 来自 bots 表）
    - channels: 渠道汇总（added/online/distribution 来自 channel_accounts 表）
    - unread: 由审计事件派生的未读通知（真实数据）

    后端暂无「托管会话/有效期/可用坐席/在线会话」等源数据，
    相关字段以占位值返回，前端按空态渲染，待后续落库再补全。
    """
    backend = get_backend()
    bot_repo = BotRepository(backend)
    channel_repo = ChannelRepository(backend)
    audit_repo = AuditRepository(backend)
    static = dashboard_static()

    bots = bot_repo.list_all()
    channels = channel_repo.list_all()

    # ---- gauges：基于真实会话状态统计 AI 接管占比 ----
    sessions = static["sessions"]
    total_sessions = len(sessions)
    if total_sessions:
        ai_managed = sum(1 for s in sessions if s.get("state") == "AI托管")
        human_handled = sum(1 for s in sessions if s.get("state") == "人工接管")
        bot_ratio = round(ai_managed / total_sessions * 100)
        human_ratio = round(human_handled / total_sessions * 100)
        idle_ratio = max(0, 100 - bot_ratio - human_ratio)
    else:
        bot_ratio = human_ratio = idle_ratio = 0
    gauges = [
        {"label": "AI 接管占比", "value": bot_ratio, "color": "var(--accent)"},
        {"label": "人工接管占比", "value": human_ratio, "color": "var(--warning)"},
        {"label": "空闲占比", "value": idle_ratio, "color": "var(--muted)"},
    ]

    # 前端 Home.jsx 约定 gauges 为对象：sessionRate / messageRate 各含 percent 与 delta。
    # 真实可计算的是「AI 接管会话占比」；消息占比暂无源数据，先用会话口径占位，delta 暂无环比源数据置 0。
    gauges_obj = {
        "sessionRate": {"percent": bot_ratio, "delta": 0},
        "messageRate": {"percent": bot_ratio, "delta": 0},
        "_breakdown": gauges,
    }

    # ---- robots：来自真实 bots 表 ----
    total_bots = len(bots)
    online_bots = sum(1 for b in bots if b.get("status") == "online")
    active_templates = sum(1 for b in bots if (b.get("workflow") or "").strip())
    robots = {
        "created": total_bots,
        "online": online_bots,
        "activeTemplates": active_templates,
        "hostedSessions": "—",
        "expireAt": "—",
    }

    # ---- channels：来自真实 channel_accounts 表 ----
    total_channels = len(channels)
    online_channels = sum(1 for c in channels if c.get("status") == "online")
    distribution: dict[str, int] = {}
    for c in channels:
        distribution[c.get("channel", "未知")] = distribution.get(c.get("channel", "未知"), 0) + 1
    channels_summary = {
        "added": total_channels,
        "online": online_channels,
        "seatsLeft": "—",
        "distribution": distribution,
        "onlineSessions": "—",
    }

    # ---- unread：由审计事件派生（真实数据）----
    unread = audit_repo.recent_unread(limit=8)

    return {
            "gauges": gauges_obj,
        "robots": robots,
        "channels": channels_summary,
        "unread": unread,
    }


@router.get("/audit-events")
def audit_events(limit: int = 50):
    """最近审计事件（保持原 /api/audit-events 路径不变）。

    MVP 返回最近 N 条；升级时支持时间范围过滤 + 分页。
    """
    backend = get_backend()
    audit_repo = AuditRepository(backend)
    return audit_repo.recent(limit)

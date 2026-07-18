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

    合并 DB 数据（bots / channels）与静态演示数据（stats / sessions / customers / workflows）。
    """
    backend = get_backend()
    bot_repo = BotRepository(backend)
    channel_repo = ChannelRepository(backend)
    static = dashboard_static()
    return {
        "stats": static["stats"],
        "bots": bot_repo.list_all(),
        "sessions": static["sessions"],
        "customers": static["customers"],
        "workflows": static["workflows"],
    }


@router.get("/audit-events")
def audit_events(limit: int = 50):
    """最近审计事件（保持原 /api/audit-events 路径不变）。

    MVP 返回最近 N 条；升级时支持时间范围过滤 + 分页。
    """
    backend = get_backend()
    audit_repo = AuditRepository(backend)
    return audit_repo.recent(limit)

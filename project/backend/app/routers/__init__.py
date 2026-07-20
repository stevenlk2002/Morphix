"""API 路由包。

按领域拆分路由，统一挂载到主应用。所有路由保持原 main.py 的
路径与响应结构不变，确保对外 contract 稳定。
"""
from __future__ import annotations

from fastapi import APIRouter

from . import (
    bots,
    channels,
    channel_mgmt,
    conversations,
    customers,
    data_panel,
    knowledge,
    llm_config,
    materials,
    messages,
    message_logs,
    meta,
    operations,
    orchestration,
    organization,
    sops,
    tags,
    training,
    workflows,
)

api_router = APIRouter(prefix="/api")
api_router.include_router(meta.router)
api_router.include_router(bots.router)
api_router.include_router(channels.router)
api_router.include_router(channel_mgmt.router)
api_router.include_router(tags.router)
api_router.include_router(customers.router)
api_router.include_router(customers._customer_groups_router)
api_router.include_router(conversations.router)
api_router.include_router(workflows.router)
api_router.include_router(orchestration.router)
api_router.include_router(sops.router)
api_router.include_router(knowledge.router)
api_router.include_router(llm_config.router)
api_router.include_router(materials.router)
api_router.include_router(training.router)
api_router.include_router(message_logs.router)
api_router.include_router(data_panel.router)
api_router.include_router(messages.router)
api_router.include_router(operations.router)
api_router.include_router(organization.router)

__all__ = ["api_router"]

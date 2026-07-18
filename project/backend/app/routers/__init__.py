"""API 路由包。

按领域拆分路由，统一挂载到主应用。所有路由保持原 main.py 的
路径与响应结构不变，确保对外 contract 稳定。
"""
from __future__ import annotations

from fastapi import APIRouter

from . import bots, channels, conversations, knowledge, materials, meta, sops, tags, workflows

api_router = APIRouter(prefix="/api")
api_router.include_router(meta.router)
api_router.include_router(bots.router)
api_router.include_router(channels.router)
api_router.include_router(tags.router)
api_router.include_router(conversations.router)
api_router.include_router(workflows.router)
api_router.include_router(sops.router)
api_router.include_router(knowledge.router)
api_router.include_router(materials.router)

__all__ = ["api_router"]

"""机器人路由：列表 / 创建 / 训练。

保持原路径：
- GET  /api/bots
- POST /api/bots
- POST /api/bots/{bot_id}/train
新增（可选分页，不影响原 contract）：
- GET  /api/bots/paged?page=&pageSize=
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter

from ..database import get_backend
from ..pagination import make_id, normalize_pagination, paginate_result
from ..repositories import AuditRepository, BotRepository
from ..schemas import BotCreateRequest

router = APIRouter(tags=["bots"])


@router.get("/bots")
def list_bots():
    """机器人全量列表（保持原 contract：直接返回数组）。"""
    return BotRepository(get_backend()).list_all()


@router.get("/bots/paged")
def list_bots_paged(page: int = 1, pageSize: Optional[int] = None):
    """机器人分页列表（新增能力，规范化分页 + 索引支撑）。"""
    pagination = normalize_pagination(page, pageSize)
    items, total = BotRepository(get_backend()).list_paged(pagination)
    return paginate_result(items, total, pagination)


@router.post("/bots")
def create_bot(payload: BotCreateRequest):
    backend = get_backend()
    bot_id = make_id("bot")
    with backend.transaction() as tx:
        bot_repo = BotRepository(tx)
        created = bot_repo.create(
            bot_id,
            payload.name,
            payload.project,
            payload.workflow,
            payload.tone,
            payload.trainingPrompt,
        )
        AuditRepository(tx).record("create_bot", bot_id, payload.name)
    return created


@router.post("/bots/{bot_id}/train")
def train_bot(bot_id: str):
    backend = get_backend()
    with backend.transaction() as tx:
        BotRepository(tx).mark_trained(bot_id)
        AuditRepository(tx).record("train_bot", bot_id, "training completed")
    return {"id": bot_id, "status": "online", "message": "训练完成"}

"""渠道账号路由。

保持原路径：
- GET  /api/channel-accounts
- POST /api/channel-accounts
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter

from ..database import get_backend
from ..pagination import make_id, normalize_pagination, paginate_result
from ..repositories import AuditRepository, ChannelRepository
from ..schemas import ChannelAccountCreateRequest

router = APIRouter(tags=["channels"])


@router.get("/channel-accounts")
def list_channel_accounts():
    """渠道账号全量列表（保持原 contract：直接返回数组）。"""
    return ChannelRepository(get_backend()).list_all()


@router.get("/channel-accounts/paged")
def list_channel_accounts_paged(page: int = 1, pageSize: Optional[int] = None):
    """渠道账号分页列表（新增能力）。"""
    pagination = normalize_pagination(page, pageSize)
    items, total = ChannelRepository(get_backend()).list_paged(pagination)
    return paginate_result(items, total, pagination)


@router.post("/channel-accounts")
def create_channel_account(payload: ChannelAccountCreateRequest):
    backend = get_backend()
    channel_id = make_id("ch")
    with backend.transaction() as tx:
        created = ChannelRepository(tx).create(
            channel_id,
            payload.channel,
            payload.accountName,
            payload.boundBot,
            payload.dailyQuota,
        )
        AuditRepository(tx).record("create_channel_account", channel_id, payload.accountName)
    return created

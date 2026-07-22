"""iPad 实时回调接收路由（P2-4）。

路径前缀 `/wxwork`（区别于资源域 `/api`），公网可达端点：
- `POST /wxwork/callback`  接收 iPad 协议服务推送的新消息，幂等落库 + 更新会话未读。

回调负载形态（待联调，做兼容）：`{uuid, json, type}`，其中 `json` 为实际消息数据；
缺失 `json` 时回退到整个 payload 解析。始终返回 200，避免回调方重试风暴。
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Request

from .. import ipad_sync

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/wxwork", tags=["channel-callback"])


@router.post("/callback")
async def channel_callback(request: Request) -> dict:
    """接收 iPad 实时回调推送（POST /wxwork/callback）。

    尽力解析 `{uuid, json, type}`，按 (conversation_id, server_id) 幂等落库新消息；
    同时更新对应会话未读。始终返回 200（业务异常仅记日志，不触发回调方重试）。
    """
    try:
        payload = await request.json()
    except Exception:  # noqa: BLE001
        logger.warning("回调负载解析失败，忽略")
        return {"ok": False, "upserted": 0, "message": "invalid payload"}
    if not isinstance(payload, dict):
        return {"ok": False, "upserted": 0, "message": "payload not object"}

    uuid = str(payload.get("uuid") or "")
    type_ = str(payload.get("type") or "")
    data = payload.get("json")
    if data is None:
        # 兼容无 json 包裹的回调形态（整包即消息数据）
        data = payload
    return ipad_sync.handle_callback(uuid, data, type_)

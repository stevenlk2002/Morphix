"""托管消息日志路由。

路径（由 api_router 挂载 /api 前缀）：
- GET /api/bots/{bot_id}/message-logs
- GET /api/bots/{bot_id}/message-logs/{ai_reply_id}
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..database import get_backend
from ..repositories import MessageLogRepository
from ..schemas import MessageLogDetail, MessageLogListResponse

router = APIRouter(tags=["message_logs"])


@router.get("/bots/{bot_id}/message-logs", response_model=MessageLogListResponse)
def list_message_logs(
    bot_id: str,
    aiReplyId: str = None,
    question: str = None,
    session: str = None,
    status: str = None,
    start: str = None,
    end: str = None,
    page: int = 1,
    pageSize: int = 20,
):
    """分页 + 筛选获取托管消息日志（按 bot_id 作用域）。"""
    return MessageLogRepository(get_backend()).list_logs(
        bot_id, aiReplyId, question, session, status, start, end, page, pageSize
    )


@router.get("/bots/{bot_id}/message-logs/{ai_reply_id}", response_model=MessageLogDetail)
def get_message_log_detail(bot_id: str, ai_reply_id: str):
    """获取单条日志详情（含编排节点追踪）。bot_id+ai_reply_id 不匹配返回 404。"""
    detail = MessageLogRepository(get_backend()).get_log_with_nodes(bot_id, ai_reply_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="message log not found")
    return detail

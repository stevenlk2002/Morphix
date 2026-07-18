"""会话路由。

保持原路径：
- GET  /api/conversations
- GET  /api/conversations/{conversation_id}
- GET  /api/conversations/{conversation_id}/messages
- POST /api/conversations/{conversation_id}/handoff

⚠️ DEPRECATED（工程收敛）：资源域会话（裸 SQL 表 conversations）仅服务即将退役的
project/frontend。Canonical 会话以统一契约路径为准：
    GET /api/control/conversations
    GET /api/control/conversations/{id}
    GET /api/control/conversations/{id}/messages
    GET /api/control/conversations/{id}/runtime
请在响应头 X-Deprecated: canonical=/api/control/conversations 指引下迁移到契约路径。
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from ..database import get_backend
from ..fixtures import conversation_messages_static, sessions_static
from ..repositories import AuditRepository, ConversationRepository
from ..schemas import HandoffRequest

router = APIRouter(tags=["conversations"])


@router.get("/conversations")
def conversations(page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=200)):
    backend = get_backend()
    repo = ConversationRepository(backend)
    # 确保静态会话已同步到 DB（兼容历史数据）
    for session in sessions_static():
        repo.upsert_for_session(session)
    items, total = repo.list_paged(page=page, page_size=page_size)
    if not items:
        return {"items": sessions_static(), "total": len(sessions_static()), "page": page, "pageSize": page_size}
    return {"items": items, "total": total, "page": page, "pageSize": page_size}


@router.get("/conversations/{conversation_id}")
def conversation_detail(conversation_id: str):
    backend = get_backend()
    repo = ConversationRepository(backend)
    for session in sessions_static():
        repo.upsert_for_session(session)
    rows = backend.query("SELECT id FROM conversations WHERE id = ?", (conversation_id,))
    if not rows:
        # 静态 fallback：从原始会话数据中查找（保持旧 contract）
        for session in sessions_static():
            if session["id"] == conversation_id:
                return repo.row_to_conversation(session)
        return {"id": conversation_id, "name": "未知会话", "state": "unknown"}
    conv = backend.query(
        "SELECT id, name, channel, bot_id, state, intent, last_message, last_time, created_at "
        "FROM conversations WHERE id = ?",
        (conversation_id,),
    )[0]
    return repo.row_to_conversation(conv)


@router.get("/conversations/{conversation_id}/messages")
def conversation_messages(conversation_id: str, page: int = 1, page_size: int = Query(50, ge=1, le=200)):
    backend = get_backend()
    repo = ConversationRepository(backend)
    result = repo.get_messages(conversation_id, page=page, page_size=page_size)
    if not result["items"]:
        # 静态 fallback（保持旧 contract）
        return conversation_messages_static(conversation_id, page)
    return result


@router.post("/conversations/{conversation_id}/handoff")
def handoff(conversation_id: str, payload: HandoffRequest):
    backend = get_backend()
    with backend.transaction() as tx:
        AuditRepository(tx).record("handoff", conversation_id, f"{payload.operator}:{payload.reason}")
    return {"conversationId": conversation_id, "handoffStatus": "human", "operator": payload.operator}

"""会话路由。

保持原路径：
- GET  /api/conversations
- GET  /api/conversations/{conversation_id}
- GET  /api/conversations/{conversation_id}/messages
- POST /api/conversations/{conversation_id}/handoff
"""
from __future__ import annotations

from fastapi import APIRouter

from ..database import get_backend
from ..fixtures import conversation_messages_static, sessions_static
from ..repositories import AuditRepository
from ..schemas import HandoffRequest

router = APIRouter(tags=["conversations"])


@router.get("/conversations")
def conversations():
    return sessions_static()


@router.get("/conversations/{conversation_id}")
def conversation_detail(conversation_id: str):
    session = next((item for item in sessions_static() if item["id"] == conversation_id), None)
    return session or {"id": conversation_id, "name": "未知会话", "state": "unknown"}


@router.get("/conversations/{conversation_id}/messages")
def conversation_messages(conversation_id: str, page: int = 1):
    return conversation_messages_static(conversation_id, page)


@router.post("/conversations/{conversation_id}/handoff")
def handoff(conversation_id: str, payload: HandoffRequest):
    backend = get_backend()
    with backend.transaction() as tx:
        AuditRepository(tx).record("handoff", conversation_id, f"{payload.operator}:{payload.reason}")
    return {"conversationId": conversation_id, "handoffStatus": "human", "operator": payload.operator}

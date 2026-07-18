"""知识库路由。

路径：
- GET    /api/bots/{bot_id}/knowledge
- POST   /api/bots/{bot_id}/knowledge
- PUT    /api/knowledge/{knowledge_id}
- DELETE /api/knowledge/{knowledge_id}
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..database import get_backend
from ..pagination import make_id
from ..repositories import AuditRepository, KnowledgeRepository
from ..schemas import KnowledgeCreateRequest, KnowledgeUpdateRequest

router = APIRouter(tags=["knowledge"])


@router.get("/bots/{bot_id}/knowledge")
def list_knowledge(bot_id: str):
    """获取指定机器人的所有知识条目。"""
    return KnowledgeRepository(get_backend()).list_by_bot(bot_id)


@router.post("/bots/{bot_id}/knowledge")
def create_knowledge(bot_id: str, payload: KnowledgeCreateRequest):
    """创建知识条目。"""
    backend = get_backend()
    knowledge_id = make_id("know")
    with backend.transaction() as tx:
        created = KnowledgeRepository(tx).create(
            knowledge_id,
            bot_id,
            payload.question,
            payload.answer,
            payload.tags,
            payload.source,
        )
        AuditRepository(tx).record("create_knowledge", knowledge_id, payload.question)
    return created


@router.put("/knowledge/{knowledge_id}")
def update_knowledge(knowledge_id: str, payload: KnowledgeUpdateRequest):
    """更新知识条目。"""
    backend = get_backend()
    with backend.transaction() as tx:
        repo = KnowledgeRepository(tx)
        existing = repo.get(knowledge_id)
        if not existing:
            raise HTTPException(status_code=404, detail="知识条目不存在")
        repo.update(knowledge_id, payload.question, payload.answer, payload.tags, payload.source)
        AuditRepository(tx).record("update_knowledge", knowledge_id, payload.question)
    return {"id": knowledge_id, "message": "更新成功"}


@router.delete("/knowledge/{knowledge_id}")
def delete_knowledge(knowledge_id: str):
    """删除知识条目。"""
    backend = get_backend()
    with backend.transaction() as tx:
        repo = KnowledgeRepository(tx)
        existing = repo.get(knowledge_id)
        if not existing:
            raise HTTPException(status_code=404, detail="知识条目不存在")
        repo.delete(knowledge_id)
        AuditRepository(tx).record("delete_knowledge", knowledge_id, existing["question"])
    return {"id": knowledge_id, "message": "删除成功"}

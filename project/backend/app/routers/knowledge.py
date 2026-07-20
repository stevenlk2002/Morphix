"""知识库路由。

路径：
- GET    /api/bots/{bot_id}/knowledge            ?kind=&search=
- POST   /api/bots/{bot_id}/knowledge            {question, answer, tags, source, kind, creator}
- PUT    /api/knowledge/{knowledge_id}           {question, answer, tags, source, kind?, creator?}
- DELETE /api/knowledge/{knowledge_id}
- DELETE /api/bots/{bot_id}/knowledge/batch      {ids: string[]}
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..database import get_backend
from ..pagination import make_id
from ..repositories import AuditRepository, KnowledgeRepository
from ..schemas import BatchDeleteRequest, KnowledgeCreateRequest, KnowledgeUpdateRequest

router = APIRouter(tags=["knowledge"])


@router.get("/bots/{bot_id}/knowledge")
def list_knowledge(bot_id: str, kind: str = None, search: str = None):
    """获取指定机器人的知识条目，支持按 kind 与关键词筛选。"""
    return KnowledgeRepository(get_backend()).list_by_bot(bot_id, kind, search)


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
            payload.kind,
            payload.creator,
        )
        AuditRepository(tx).record("create_knowledge", knowledge_id, payload.question)
    return created


@router.put("/knowledge/{knowledge_id}")
def update_knowledge(knowledge_id: str, payload: KnowledgeUpdateRequest):
    """更新知识条目（kind/creator 可选）。"""
    backend = get_backend()
    with backend.transaction() as tx:
        repo = KnowledgeRepository(tx)
        existing = repo.get(knowledge_id)
        if not existing:
            raise HTTPException(status_code=404, detail="知识条目不存在")
        repo.update(
            knowledge_id,
            payload.question,
            payload.answer,
            payload.tags,
            payload.source,
            payload.kind,
            payload.creator,
        )
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


@router.delete("/bots/{bot_id}/knowledge/batch")
def batch_delete_knowledge(bot_id: str, payload: BatchDeleteRequest):
    """按 bot_id 作用域批量删除知识条目。"""
    backend = get_backend()
    with backend.transaction() as tx:
        deleted = KnowledgeRepository(tx).delete_by_bot_and_ids(bot_id, payload.ids)
        AuditRepository(tx).record("batch_delete_knowledge", bot_id, f"删除了 {deleted} 条知识")
    return {"deleted": deleted}


@router.delete("/bots/{bot_id}/knowledge/base/{kind}")
def delete_knowledge_base(bot_id: str, kind: str):
    """侧栏「删除知识库」：按 bot_id + kind 删除整库（真实硬删）。"""
    backend = get_backend()
    with backend.transaction() as tx:
        deleted = KnowledgeRepository(tx).delete_by_bot_and_kind(bot_id, kind)
        AuditRepository(tx).record(
            "delete_knowledge_base", bot_id, f"删除了 {kind} 知识库 {deleted} 条"
        )
    return {"deleted": deleted, "kind": kind}

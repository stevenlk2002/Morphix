"""客户标签路由。

保持原路径：
- GET  /api/customer-tags
- POST /api/customer-tags
"""
from __future__ import annotations

from fastapi import APIRouter

from ..database import get_backend
from ..pagination import make_id
from ..repositories import AuditRepository, TagRepository
from ..schemas import TagCreateRequest

router = APIRouter(tags=["tags"])


@router.get("/customer-tags")
def list_customer_tags():
    return TagRepository(get_backend()).list_all()


@router.post("/customer-tags")
def create_customer_tag(payload: TagCreateRequest):
    backend = get_backend()
    tag_id = make_id("tag")
    with backend.transaction() as tx:
        created = TagRepository(tx).upsert(tag_id, payload.name, payload.color, payload.rule)
        AuditRepository(tx).record("create_customer_tag", payload.name, payload.rule)
    return created

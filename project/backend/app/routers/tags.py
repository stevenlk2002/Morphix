"""客户标签路由。

保持原路径：
- GET  /api/customer-tags
- POST /api/customer-tags

扩展标签分组模型：
- GET    /api/customer-tag-groups
- POST   /api/customer-tag-groups
- PUT    /api/customer-tag-groups/{id}
- DELETE /api/customer-tag-groups/{id}
"""
from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from ..database import get_backend
from ..pagination import make_id
from ..repositories import AuditRepository, CustomerRepository, TagRepository
from ..schemas import TagCreateRequest, TagGroupCreateRequest, TagGroupUpdateRequest

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


@router.put("/customer-tags/{tag_id}")
def update_customer_tag(tag_id: str, payload: TagCreateRequest):
    backend = get_backend()
    with backend.transaction() as tx:
        TagRepository(tx).update(tag_id, payload.name, payload.color, payload.rule)
        AuditRepository(tx).record("update_customer_tag", payload.name, payload.rule)
    return {"id": tag_id, "name": payload.name, "color": payload.color, "rule": payload.rule}


@router.delete("/customer-tags/{tag_id}")
def delete_customer_tag(tag_id: str):
    backend = get_backend()
    with backend.transaction() as tx:
        TagRepository(tx).delete(tag_id)
        AuditRepository(tx).record("delete_customer_tag", tag_id, "")
    return {"id": tag_id, "deleted": True}


# ---- 标签分组 CRUD（扩展） ----

@router.get("/customer-tag-groups")
def list_tag_groups():
    """标签组列表（含组内标签）。"""
    return CustomerRepository(get_backend()).list_tag_groups()


@router.post("/customer-tag-groups")
def create_tag_group(payload: TagGroupCreateRequest):
    """新建标签组（名称+标签列表）。"""
    return CustomerRepository(get_backend()).create_tag_group(
        payload.name, payload.isHot, payload.tags
    )


@router.put("/customer-tag-groups/{group_id}")
def update_tag_group(group_id: str, payload: TagGroupUpdateRequest):
    """编辑标签组（名称+标签增删改）。"""
    result = CustomerRepository(get_backend()).update_tag_group(
        group_id, payload.name, payload.isHot, payload.tags
    )
    if result is None:
        return JSONResponse(status_code=404, content={"detail": "标签组不存在"})
    return result


@router.delete("/customer-tag-groups/{group_id}")
def delete_tag_group(group_id: str):
    """删除标签组（级联删除组内标签+关系）。"""
    ok = CustomerRepository(get_backend()).delete_tag_group(group_id)
    if not ok:
        return JSONResponse(status_code=404, content={"detail": "标签组不存在"})
    return {"id": group_id, "deleted": True}

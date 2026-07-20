"""素材库路由。

路径：
- GET    /api/bots/{bot_id}/materials        ?name=&startDate=&endDate=&source=&page=&pageSize=
- POST   /api/bots/{bot_id}/materials        {name, type, size, category, url?, source}
- DELETE /api/materials/{material_id}
- DELETE /api/bots/{bot_id}/materials/batch  {ids: string[]}
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..database import get_backend
from ..pagination import make_id
from ..repositories import AuditRepository, MaterialRepository
from ..schemas import BatchDeleteRequest, MaterialCreateRequest

router = APIRouter(tags=["materials"])


@router.get("/bots/{bot_id}/materials")
def list_materials(
    bot_id: str,
    name: str = None,
    startDate: str = None,
    endDate: str = None,
    source: str = None,
    page: int = 1,
    pageSize: int = 20,
):
    """分页 + 筛选获取素材，返回 {items, total, page, pageSize, hasMore}。"""
    return MaterialRepository(get_backend()).list_paged(
        bot_id, name, startDate, endDate, source, page, pageSize
    )


@router.post("/bots/{bot_id}/materials")
def create_material(bot_id: str, payload: MaterialCreateRequest):
    """创建素材（仅落元数据，url 可空）。"""
    backend = get_backend()
    material_id = make_id("mat")
    with backend.transaction() as tx:
        created = MaterialRepository(tx).create(
            material_id,
            bot_id,
            payload.name,
            payload.type,
            payload.size,
            payload.category,
            payload.url,
            payload.source,
        )
        AuditRepository(tx).record("create_material", material_id, payload.name)
    return created


@router.delete("/materials/{material_id}")
def delete_material(material_id: str):
    """删除素材。"""
    backend = get_backend()
    with backend.transaction() as tx:
        repo = MaterialRepository(tx)
        existing = repo.get(material_id)
        if not existing:
            raise HTTPException(status_code=404, detail="素材不存在")
        repo.delete(material_id)
        AuditRepository(tx).record("delete_material", material_id, existing["name"])
    return {"id": material_id, "message": "删除成功"}


@router.delete("/bots/{bot_id}/materials/batch")
def batch_delete_material(bot_id: str, payload: BatchDeleteRequest):
    """按 bot_id 作用域批量删除素材。"""
    backend = get_backend()
    with backend.transaction() as tx:
        deleted = MaterialRepository(tx).delete_by_bot_and_ids(bot_id, payload.ids)
        AuditRepository(tx).record("batch_delete_material", bot_id, f"删除了 {deleted} 条素材")
    return {"deleted": deleted}

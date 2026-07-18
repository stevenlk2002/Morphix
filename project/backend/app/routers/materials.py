"""素材库路由。

路径：
- GET    /api/bots/{bot_id}/materials
- POST   /api/bots/{bot_id}/materials
- DELETE /api/materials/{material_id}
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..database import get_backend
from ..pagination import make_id
from ..repositories import AuditRepository, MaterialRepository
from ..schemas import MaterialCreateRequest

router = APIRouter(tags=["materials"])


@router.get("/bots/{bot_id}/materials")
def list_materials(bot_id: str):
    """获取指定机器人的所有素材。"""
    return MaterialRepository(get_backend()).list_by_bot(bot_id)


@router.post("/bots/{bot_id}/materials")
def create_material(bot_id: str, payload: MaterialCreateRequest):
    """创建素材。"""
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

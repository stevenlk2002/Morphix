"""SOP 路由。

端点：
- GET    /api/sops              → SOP 列表（支持筛选 + 排序）
- POST   /api/sops              → 创建 SOP
- GET    /api/sops/{id}         → SOP 详情
- PUT    /api/sops/{id}         → 更新 SOP
- DELETE /api/sops/{id}         → 删除 SOP
- PATCH  /api/sops/{id}/toggle  → 启停切换
"""
from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from ..database import get_backend
from ..sop_repository import OperationSopRepository, _generate_id
from ..sop_schemas import (
    SopCreateRequest,
    SopDeleteResponse,
    SopDetailResponse,
    SopRecordResponse,
    SopResponse,
    SopToggleRequest,
    SopUpdateRequest,
)

router = APIRouter(tags=["sops"])


def _repo() -> OperationSopRepository:
    return OperationSopRepository(get_backend())


# ---- 列表 ----

@router.get("/sops", response_model=list[SopResponse])
def list_sops(
    search: Optional[str] = Query(None, description="搜索 SOP 名称"),
    type: Optional[str] = Query(None, alias="type", description="类型筛选：客户SOP | 群聊SOP"),
    enabled: Optional[str] = Query(None, description="启用状态：已启用 | 已停用"),
    status: Optional[str] = Query(None, alias="status", description="运行状态：运行中 | 未运行"),
    sortBy: Optional[str] = Query("最近创建", alias="sortBy", description="排序：最近创建 | 最近更新"),
):
    """SOP 列表，支持筛选 + 排序。"""
    type_map = {"客户SOP": "customer", "群聊SOP": "group"}
    type_val = type_map.get(type or "", type)
    # 如果 type 不是已知映射值且不是"全部"，直接按原值传递
    if type and type not in ("全部",) and type not in type_map:
        type_val = type
    elif type == "全部":
        type_val = None

    return _repo().list_all(
        type_=type_val,
        enabled=enabled,
        status=status,
        search=search,
        sort_by=sortBy or "最近创建",
    )


# ---- 创建 ----

@router.post("/sops", response_model=SopResponse, status_code=201)
def create_sop(payload: SopCreateRequest):
    """创建 SOP。"""
    sop_id = _generate_id("sop")
    nodes_dicts = [n.model_dump() for n in payload.nodes]
    return _repo().create(
        sop_id=sop_id,
        name=payload.name,
        type_=payload.type,
        channel=payload.channel,
        trigger_type=payload.trigger_type,
        trigger_config=payload.trigger_config,
        nodes=nodes_dicts,
    )


# ---- 详情 ----

@router.get("/sops/{sop_id}", response_model=SopDetailResponse)
def get_sop(sop_id: str):
    """获取 SOP 详情（含完整流程节点）。"""
    result = _repo().get(sop_id)
    if result is None:
        raise HTTPException(status_code=404, detail="SOP 不存在")
    return result


# ---- 更新 ----

@router.put("/sops/{sop_id}", response_model=SopResponse)
def update_sop(sop_id: str, payload: SopUpdateRequest):
    """更新 SOP（部分更新）。"""
    fields = payload.model_dump(exclude_unset=True)
    if "nodes" in fields and fields["nodes"]:
        fields["nodes"] = [n.model_dump() if hasattr(n, 'model_dump') else n for n in fields["nodes"]]
    result = _repo().update(sop_id, fields)
    if result is None:
        raise HTTPException(status_code=404, detail="SOP 不存在")
    return result


# ---- 删除 ----

@router.delete("/sops/{sop_id}", response_model=SopDeleteResponse)
def delete_sop(sop_id: str):
    """删除 SOP。"""
    deleted = _repo().delete(sop_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="SOP 不存在")
    return {"id": sop_id, "deleted": True}


# ---- 启停 ----

@router.patch("/sops/{sop_id}/toggle", response_model=SopResponse)
def toggle_sop(sop_id: str, payload: SopToggleRequest):
    """切换 SOP 启用状态。"""
    result = _repo().toggle(sop_id, payload.enabled)
    if result is None:
        raise HTTPException(status_code=404, detail="SOP 不存在")
    return result


# ---- 运行记录 ----

@router.get("/sops/{sop_id}/records", response_model=list[SopRecordResponse])
def list_sop_records(sop_id: str):
    """获取 SOP 的运行记录列表（按运行时间倒序）。"""
    repo = _repo()
    if repo.get(sop_id) is None:
        raise HTTPException(status_code=404, detail="SOP 不存在")
    return repo.list_records(sop_id)

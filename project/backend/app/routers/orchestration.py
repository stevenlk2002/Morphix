"""编排工作流 REST 端点（持久化存储）。"""
from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException

from ..database import get_backend
from ..repositories import OrchestrationWorkflowRepository
from ..schemas import OrchestrationWorkflowSave

router = APIRouter(prefix="/orchestration", tags=["orchestration"])


@router.put("/workflows/{bot_id}")
def save_workflow(bot_id: str, payload: OrchestrationWorkflowSave):
    """保存或更新编排工作流。"""
    backend = get_backend()
    data_json = json.dumps(payload.model_dump(), ensure_ascii=False)
    OrchestrationWorkflowRepository(backend).save(bot_id, data_json)
    return {"botId": bot_id, "saved": True}


@router.get("/workflows/{bot_id}")
def load_workflow(bot_id: str):
    """加载指定 bot 的编排工作流。"""
    backend = get_backend()
    row = OrchestrationWorkflowRepository(backend).load(bot_id)
    if not row:
        raise HTTPException(status_code=404, detail="workflow not found")
    data = json.loads(row["data"])
    data["updatedAt"] = row["updated_at"]
    return data


@router.delete("/workflows/{bot_id}")
def delete_workflow(bot_id: str):
    """删除指定 bot 的编排工作流。"""
    backend = get_backend()
    deleted = OrchestrationWorkflowRepository(backend).delete(bot_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="workflow not found")
    return {"botId": bot_id, "deleted": True}

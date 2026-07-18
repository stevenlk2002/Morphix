"""工作流路由。

保持原路径：
- GET   /api/workflows
- GET   /api/workflows/{workflow_id}
- PATCH /api/workflows/{workflow_id}/nodes/{node_id}
"""
from __future__ import annotations

import json

from fastapi import APIRouter

from ..database import get_backend
from ..fixtures import workflows_static
from ..repositories import AuditRepository, WorkflowRepository
from ..schemas import WorkflowNodeUpdateRequest

router = APIRouter(tags=["workflows"])


@router.get("/workflows")
def workflows():
    return workflows_static()


@router.get("/workflows/{workflow_id}")
def workflow_detail(workflow_id: str):
    backend = get_backend()
    workflow = next((item for item in workflows_static() if item["id"] == workflow_id), None)
    return {
        **(workflow or {"id": workflow_id, "name": "临时工作流", "nodes": 0, "status": "草稿", "updatedAt": "刚刚"}),
        "definition": WorkflowRepository(backend).node_rows(workflow_id),
    }


@router.patch("/workflows/{workflow_id}/nodes/{node_id}")
def update_workflow_node(workflow_id: str, node_id: str, payload: WorkflowNodeUpdateRequest):
    backend = get_backend()
    config_json = json.dumps(payload.config, ensure_ascii=False)
    with backend.transaction() as tx:
        repo = WorkflowRepository(tx)
        existing = repo.get_node(workflow_id, node_id)
        if existing:
            repo.update_node(workflow_id, node_id, payload.label, payload.nodeType, config_json)
        else:
            repo.insert_node(workflow_id, node_id, payload.label, payload.nodeType, config_json)
        AuditRepository(tx).record("update_workflow_node", node_id, payload.label)
    return {
        "id": node_id,
        "workflowId": workflow_id,
        "label": payload.label,
        "nodeType": payload.nodeType,
        "config": payload.config,
    }

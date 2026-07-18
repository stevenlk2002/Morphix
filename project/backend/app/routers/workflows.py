"""工作流路由。

保持原路径：
- GET   /api/workflows
- GET   /api/workflows/{workflow_id}
- PATCH /api/workflows/{workflow_id}/nodes/{node_id}

⚠️ DEPRECATED（工程收敛）：资源域运行（裸 SQL 表 workflow_runs）仅服务即将退役的
project/frontend。Canonical 工作流运行以统一契约路径为准：
    POST /api/control/workflow-runs
    GET  /api/control/workflow-runs/{id}
    GET  /api/control/workflow-runs/{id}/node-executions
    POST /api/control/workflow-runs/{id}/interrupt|resume|cancel
"""
from __future__ import annotations

import json

from fastapi import APIRouter

from fastapi import APIRouter, HTTPException, Query

from ..database import get_backend
from ..fixtures import workflows_static
from ..repositories import AuditRepository, WorkflowRepository, WorkflowRunRepository
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


@router.get("/workflows/{workflow_id}/runs")
def list_workflow_runs(workflow_id: str, conversation_id: str = Query(...)):
    backend = get_backend()
    return WorkflowRunRepository(backend).list_by_conversation(conversation_id)


@router.post("/workflows/{workflow_id}/runs")
def create_workflow_run(
    workflow_id: str,
    conversation_id: str = Query(...),
    trigger: str = Query("manual"),
):
    backend = get_backend()
    workflow = next((item for item in workflows_static() if item["id"] == workflow_id), None)
    if not workflow:
        raise HTTPException(status_code=404, detail="workflow not found")
    run = WorkflowRunRepository(backend).create(
        conversation_id=conversation_id,
        workflow_id=workflow_id,
        trigger=trigger,
    )
    return run


@router.get("/workflows/{workflow_id}/runs/{run_id}")
def get_workflow_run(workflow_id: str, run_id: str):
    backend = get_backend()
    rows = backend.query("SELECT * FROM workflow_runs WHERE id = ? AND workflow_id = ?", (run_id, workflow_id))
    if not rows:
        raise HTTPException(status_code=404, detail="run not found")
    return WorkflowRunRepository(backend)._row_to_run(rows[0])


@router.patch("/workflows/{workflow_id}/runs/{run_id}")
def update_workflow_run(workflow_id: str, run_id: str, status: str = Query(...)):
    backend = get_backend()
    repo = WorkflowRunRepository(backend)
    rows = backend.query("SELECT id FROM workflow_runs WHERE id = ? AND workflow_id = ?", (run_id, workflow_id))
    if not rows:
        raise HTTPException(status_code=404, detail="run not found")
    repo.update_status(run_id, status)
    return {"id": run_id, "status": status}

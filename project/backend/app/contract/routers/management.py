"""Management CRUD (contract-TBD).

The unified contract does not yet define Project / Bot / WorkflowVersion
management endpoints; these are derived from the data model and flagged
contract-TBD. They exist so the runtime can be driven (projects/bots/published
workflows must exist before inbound events trigger runs) and so the control
console has something to manage.

Write operations enforce the RBAC matrix (owner/admin/editor may write; viewer
gets 403 FORBIDDEN), filling one of the documented contract gaps.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Body, Depends, Header
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.contract.database import get_db
from app.contract.envelope import ApiError
from app.contract.responses import ok
from app.contract.security import require_role
from app.contract.models import Bot, Project, WorkflowVersion
from app.contract.schemas import (
    BotCreate,
    BotData,
    BotUpdate,
    ProjectCreate,
    ProjectData,
    ProjectUpdate,
    WorkflowVersionCreate,
    WorkflowVersionData,
)

router = APIRouter(prefix="/api/control", tags=["Management (contract-TBD)"])


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _project_data(p: Project) -> ProjectData:
    return ProjectData(
        id=p.id,
        name=p.name,
        description=p.description,
        status=p.status,
        created_at=p.created_at.isoformat() if isinstance(p.created_at, datetime) else str(p.created_at),
        updated_at=p.updated_at.isoformat() if isinstance(p.updated_at, datetime) else str(p.updated_at),
    )


def _bot_data(b: Bot) -> BotData:
    return BotData(
        id=b.id,
        project_id=b.project_id,
        name=b.name,
        description=b.description,
        inherited_workflow_version_id=b.inherited_workflow_version_id,
        status=b.status,
        created_at=b.created_at.isoformat() if isinstance(b.created_at, datetime) else str(b.created_at),
        updated_at=b.updated_at.isoformat() if isinstance(b.updated_at, datetime) else str(b.updated_at),
    )


def _wf_data(w: WorkflowVersion) -> WorkflowVersionData:
    return WorkflowVersionData(
        id=w.id,
        project_id=w.project_id,
        name=w.name,
        version=w.version,
        status=w.status,
        definition=w.definition or {},
        created_at=w.created_at.isoformat() if isinstance(w.created_at, datetime) else str(w.created_at),
        published_at=w.published_at.isoformat() if isinstance(w.published_at, datetime) else None,
    )


# ---------------- Projects ----------------

@router.post("/projects")
def create_project(
    req: ProjectCreate,
    db: Session = Depends(get_db),
    _role: str = Depends(require_role),
):
    p = Project(name=req.name, description=req.description, status="active")
    db.add(p)
    db.commit()
    return ok(_project_data(p), status_code=201)


@router.get("/projects")
def list_projects(db: Session = Depends(get_db)):
    rows = db.execute(select(Project).where(Project.deleted_at.is_(None)).order_by(Project.created_at)).scalars().all()
    return ok([_project_data(p) for p in rows])


@router.get("/projects/{project_id}")
def get_project(project_id: str, db: Session = Depends(get_db)):
    p = db.get(Project, project_id)
    if p is None or p.deleted_at is not None:
        raise ApiError(404, "NOT_FOUND", f"project {project_id} not found")
    return ok(_project_data(p))


@router.put("/projects/{project_id}")
def update_project(
    project_id: str,
    req: ProjectUpdate = Body(...),
    db: Session = Depends(get_db),
    _role: str = Depends(require_role),
):
    p = db.get(Project, project_id)
    if p is None or p.deleted_at is not None:
        raise ApiError(404, "NOT_FOUND", f"project {project_id} not found")
    if req.name is not None:
        p.name = req.name
    if req.description is not None:
        p.description = req.description
    if req.status is not None:
        p.status = req.status
    db.commit()
    return ok(_project_data(p))


@router.delete("/projects/{project_id}")
def archive_project(
    project_id: str,
    db: Session = Depends(get_db),
    _role: str = Depends(require_role),
):
    p = db.get(Project, project_id)
    if p is None or p.deleted_at is not None:
        raise ApiError(404, "NOT_FOUND", f"project {project_id} not found")
    p.status = "archived"
    p.deleted_at = _utcnow()
    db.commit()
    return ok(_project_data(p))


# ---------------- Bots ----------------

@router.post("/projects/{project_id}/bots")
def create_bot(
    project_id: str,
    req: BotCreate,
    db: Session = Depends(get_db),
    _role: str = Depends(require_role),
):
    p = db.get(Project, project_id)
    if p is None or p.deleted_at is not None:
        raise ApiError(404, "NOT_FOUND", f"project {project_id} not found")
    b = Bot(
        project_id=project_id,
        name=req.name,
        description=req.description,
        inherited_workflow_version_id=req.inherited_workflow_version_id,
        status="active",
    )
    db.add(b)
    db.commit()
    return ok(_bot_data(b), status_code=201)


@router.get("/projects/{project_id}/bots")
def list_bots(project_id: str, db: Session = Depends(get_db)):
    rows = db.execute(select(Bot).where(Bot.project_id == project_id, Bot.deleted_at.is_(None))).scalars().all()
    return ok([_bot_data(b) for b in rows])


@router.get("/projects/{project_id}/bots/{bot_id}")
def get_bot(project_id: str, bot_id: str, db: Session = Depends(get_db)):
    b = db.get(Bot, bot_id)
    if b is None or b.deleted_at is not None or b.project_id != project_id:
        raise ApiError(404, "NOT_FOUND", f"bot {bot_id} not found")
    return ok(_bot_data(b))


@router.put("/projects/{project_id}/bots/{bot_id}")
def update_bot(
    project_id: str,
    bot_id: str,
    req: BotUpdate,
    db: Session = Depends(get_db),
    _role: str = Depends(require_role),
):
    b = db.get(Bot, bot_id)
    if b is None or b.deleted_at is not None or b.project_id != project_id:
        raise ApiError(404, "NOT_FOUND", f"bot {bot_id} not found")
    if req.name is not None:
        b.name = req.name
    if req.description is not None:
        b.description = req.description
    if req.status is not None:
        b.status = req.status
    db.commit()
    return ok(_bot_data(b))


@router.delete("/projects/{project_id}/bots/{bot_id}")
def archive_bot(
    project_id: str,
    bot_id: str,
    db: Session = Depends(get_db),
    _role: str = Depends(require_role),
):
    b = db.get(Bot, bot_id)
    if b is None or b.deleted_at is not None or b.project_id != project_id:
        raise ApiError(404, "NOT_FOUND", f"bot {bot_id} not found")
    b.status = "archived"
    b.deleted_at = _utcnow()
    db.commit()
    return ok(_bot_data(b))


# ---------------- Workflow Versions ----------------

@router.post("/projects/{project_id}/workflow-versions")
def create_workflow_version(
    project_id: str,
    req: WorkflowVersionCreate,
    db: Session = Depends(get_db),
    _role: str = Depends(require_role),
):
    p = db.get(Project, project_id)
    if p is None or p.deleted_at is not None:
        raise ApiError(404, "NOT_FOUND", f"project {project_id} not found")
    definition = req.definition or {}
    nodes = definition.get("nodes")
    edges = definition.get("edges")
    if not isinstance(nodes, list) or not isinstance(edges, list):
        raise ApiError(422, "PAYLOAD_INVALID", "definition must contain nodes[] and edges[]")
    wfv = WorkflowVersion(project_id=project_id, name=req.name, version=1, status="draft", definition=definition)
    db.add(wfv)
    db.commit()
    return ok(_wf_data(wfv), status_code=201)


@router.get("/projects/{project_id}/workflow-versions")
def list_workflow_versions(project_id: str, db: Session = Depends(get_db)):
    rows = db.execute(select(WorkflowVersion).where(WorkflowVersion.project_id == project_id)).scalars().all()
    return ok([_wf_data(w) for w in rows])


@router.get("/projects/{project_id}/workflow-versions/{version_id}")
def get_workflow_version(project_id: str, version_id: str, db: Session = Depends(get_db)):
    w = db.get(WorkflowVersion, version_id)
    if w is None or w.project_id != project_id:
        raise ApiError(404, "NOT_FOUND", f"workflow version {version_id} not found")
    return ok(_wf_data(w))


@router.post("/projects/{project_id}/workflow-versions/{version_id}/publish")
def publish_workflow_version(
    project_id: str,
    version_id: str,
    db: Session = Depends(get_db),
    _role: str = Depends(require_role),
):
    w = db.get(WorkflowVersion, version_id)
    if w is None or w.project_id != project_id:
        raise ApiError(404, "NOT_FOUND", f"workflow version {version_id} not found")
    w.status = "published"
    w.published_at = _utcnow()
    db.commit()
    return ok(_wf_data(w))

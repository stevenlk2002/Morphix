"""Control-plane endpoints (no auth required per unified contract).

Covers: conversations (list/detail/messages/runtime), human handoff/return,
workflow runs (create/get/node-executions/interrupt/resume/cancel), and audit
listings (policy decisions / agent invocations).

NOTE: the unified contract does not attach a security scheme to /api/control/*
endpoints, so they accept requests without auth in the MVP. An optional
X-Control-Token / X-User-Id is read only for audit attribution.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.envelope import ApiError, new_request_id
from app.core.responses import ok
from app.models import (
    AgentInvocation,
    AuditLog,
    Bot,
    Conversation,
    Message,
    PolicyDecision,
    SessionRuntime,
    TakeoverRequest,
    WorkflowRun,
    WorkflowRunStep,
)
from app.schemas import (
    AgentInvocation as AgentInvocationDTO,
    AgentInvocationListData,
    BotSummary,
    CancelWorkflowRunRequest,
    ContactRef,
    ConversationDetail,
    ConversationListItem,
    ConversationListData,
    ConversationMessage,
    ConversationMessageListData,
    ConversationRuntime,
    CreateWorkflowRunRequest,
    CreateWorkflowRunResponseData,
    HandoffRequest,
    HandoffResponseData,
    HandoffReturnRequest,
    HandoffSnapshot,
    InterruptWorkflowRunRequest,
    NodeExecution,
    NodeExecutionListData,
    PolicyDecision as PolicyDecisionDTO,
    PolicyDecisionListData,
    ResumeWorkflowRunRequest,
    WorkflowRunDetail,
    WorkflowRunStateMutationData,
)
from app.services.orchestration import iso, start_manual_run

router = APIRouter(prefix="/api/control", tags=["Control Conversations", "Control Workflow Runs", "Audit"])


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _bot_summary(db: Session, bot_id: str | None) -> BotSummary | None:
    if not bot_id:
        return None
    bot = db.get(Bot, bot_id)
    if bot is None:
        return None
    return BotSummary(id=bot.id, name=bot.name)


def _latest_message_at(db: Session, conversation_id: str) -> str | None:
    msg = (
        db.execute(select(Message).where(Message.conversation_id == conversation_id).order_by(Message.sent_at.desc()))
        .scalars()
        .first()
    )
    if msg is None:
        return None
    return msg.sent_at.isoformat() if isinstance(msg.sent_at, datetime) else str(msg.sent_at)


def _to_list_item(db: Session, conv: Conversation) -> ConversationListItem:
    srt = db.execute(select(SessionRuntime).where(SessionRuntime.conversation_id == conv.id)).scalars().first()
    return ConversationListItem(
        conversation_id=conv.id,
        channel_account_id=conv.channel_account_id,
        conversation_type=conv.conversation_type,
        subject=conv.subject or "",
        session_state=srt.session_state if srt else "IDLE",
        handoff_status=conv.handoff_status or "none",
        current_bot=_bot_summary(db, conv.current_bot_id),
        last_message_at=_latest_message_at(db, conv.id),
    )


def _to_detail(db: Session, conv: Conversation) -> ConversationDetail:
    srt = db.execute(select(SessionRuntime).where(SessionRuntime.conversation_id == conv.id)).scalars().first()
    latest = (
        db.execute(select(TakeoverRequest).where(TakeoverRequest.conversation_id == conv.id).order_by(TakeoverRequest.requested_at.desc()))
        .scalars()
        .first()
    )
    handoff_snapshot = None
    if latest is not None:
        handoff_snapshot = HandoffSnapshot(
            operator_id=latest.operator_id,
            requested_at=iso(latest.requested_at),
            activated_at=iso(latest.activated_at),
            reason=latest.reason,
        )
    contact_dto = None
    if isinstance(conv.contact, dict):
        contact_dto = ContactRef(
            external_uid=conv.contact.get("externalUid"),
            display_name=conv.contact.get("displayName"),
            tags=conv.contact.get("tags"),
        )
    return ConversationDetail(
        conversation_id=conv.id,
        project_id=conv.project_id,
        channel_account_id=conv.channel_account_id,
        conversation_type=conv.conversation_type,
        subject=conv.subject or "",
        owner_type=conv.owner_type or "ai",
        handoff_status=conv.handoff_status or "none",
        current_bot=_bot_summary(db, conv.current_bot_id),
        current_workflow_version_id=conv.current_workflow_version_id,
        latest_handoff=handoff_snapshot,
        contact=contact_dto,
    )


# ---------------- Conversations ----------------

@router.get("/conversations")
def list_conversations(
    db: Session = Depends(get_db),
    project_id: str = Query(..., alias="projectId"),
    channel_account_id: str | None = Query(default=None, alias="channelAccountId"),
    bot_id: str | None = Query(default=None, alias="botId"),
    session_state: str | None = Query(default=None, alias="sessionState"),
    handoff_status: str | None = Query(default=None, alias="handoffStatus"),
    keyword: str | None = Query(default=None),
    updated_after: str | None = Query(default=None, alias="updatedAfter"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200, alias="pageSize"),
):
    q = select(Conversation).where(Conversation.deleted_at.is_(None), Conversation.project_id == project_id)
    if channel_account_id:
        q = q.where(Conversation.channel_account_id == channel_account_id)
    if bot_id:
        q = q.where(Conversation.current_bot_id == bot_id)
    if keyword:
        q = q.where(Conversation.subject.ilike(f"%{keyword}%"))
    if handoff_status:
        q = q.where(Conversation.handoff_status == handoff_status)
    total = len(db.execute(q).scalars().all())
    rows = db.execute(q.order_by(Conversation.updated_at.desc()).limit(page_size).offset((page - 1) * page_size)).scalars().all()
    items = [_to_list_item(db, c) for c in rows]
    return ok(ConversationListData(items=items, page=page, page_size=page_size, total=total))


@router.get("/conversations/{conversation_id}")
def get_conversation(conversation_id: str, db: Session = Depends(get_db)):
    conv = db.get(Conversation, conversation_id)
    if conv is None or conv.deleted_at is not None:
        raise ApiError(404, "NOT_FOUND", f"conversation {conversation_id} not found")
    return ok(_to_detail(db, conv))


@router.get("/conversations/{conversation_id}/messages")
def list_conversation_messages(
    conversation_id: str,
    db: Session = Depends(get_db),
    before_seq: int | None = Query(default=None, ge=1, alias="beforeSeq"),
    after_seq: int | None = Query(default=None, ge=1, alias="afterSeq"),
    limit: int = Query(default=50, ge=1, le=200),
):
    conv = db.get(Conversation, conversation_id)
    if conv is None or conv.deleted_at is not None:
        raise ApiError(404, "NOT_FOUND", f"conversation {conversation_id} not found")
    q = select(Message).where(Message.conversation_id == conversation_id)
    if before_seq is not None:
        q = q.where(Message.seq_no < before_seq)
    if after_seq is not None:
        q = q.where(Message.seq_no > after_seq)
    rows = db.execute(q.order_by(Message.seq_no.desc()).limit(limit)).scalars().all()
    items = [
        ConversationMessage(
            message_id=m.id,
            seq_no=m.seq_no,
            sender_type=m.sender_type,
            message_type=m.message_type,
            content_text=m.content_text,
            sent_at=m.sent_at.isoformat() if isinstance(m.sent_at, datetime) else str(m.sent_at),
            source_message_id=m.source_message_id,
        )
        for m in rows
    ]
    return ok(ConversationMessageListData(items=items, has_more=len(items) == limit, next_before_seq=items[-1].seq_no if items else None))


@router.get("/conversations/{conversation_id}/runtime")
def get_conversation_runtime(conversation_id: str, db: Session = Depends(get_db)):
    conv = db.get(Conversation, conversation_id)
    if conv is None or conv.deleted_at is not None:
        raise ApiError(404, "NOT_FOUND", f"conversation {conversation_id} not found")
    srt = db.execute(select(SessionRuntime).where(SessionRuntime.conversation_id == conversation_id)).scalars().first()
    if srt is None:
        raise ApiError(404, "NOT_FOUND", f"session runtime for {conversation_id} not found")
    return ok(
        ConversationRuntime(
            session_runtime_id=srt.id,
            hosting_status=srt.hosting_status,
            session_state=srt.session_state,
            handoff_status=srt.handoff_status,
            interrupt_policy=srt.interrupt_policy,
            current_bot_id=srt.current_bot_id,
            current_workflow_version_id=srt.current_workflow_version_id,
            active_run_id=srt.active_run_id,
            waiting_node_id=srt.waiting_node_id,
            locked_until=iso(srt.locked_until),
            last_policy_decision_id=srt.last_policy_decision_id,
            updated_at=iso(srt.updated_at) or _utcnow().isoformat(),
        )
    )


# ---------------- Handoff ----------------

@router.post("/conversations/{conversation_id}/handoff")
def handoff_conversation(
    conversation_id: str,
    req: HandoffRequest,
    db: Session = Depends(get_db),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    conv = db.get(Conversation, conversation_id)
    if conv is None or conv.deleted_at is not None:
        raise ApiError(404, "NOT_FOUND", f"conversation {conversation_id} not found")
    srt = db.execute(select(SessionRuntime).where(SessionRuntime.conversation_id == conversation_id)).scalars().first()
    if conv.handoff_status == "active":
        raise ApiError(409, "HANDOFF_STATE_INVALID", "conversation already in active human handoff")
    conv.handoff_status = "active"
    if srt is not None:
        srt.handoff_status = "active"
        srt.session_state = "HUMAN_HANDOFF"
    tk = TakeoverRequest(
        id=f"tk_{uuid.uuid4().hex}",
        conversation_id=conversation_id,
        project_id=conv.project_id,
        operator_id=req.operator_id,
        status="active",
        reason=req.reason,
        requested_at=_utcnow(),
        activated_at=_utcnow(),
    )
    db.add(tk)
    db.commit()
    return ok(
        HandoffResponseData(
            handoff_status=conv.handoff_status,
            session_state=srt.session_state if srt else "HUMAN_HANDOFF",
            affected_run_id=srt.active_run_id if srt else None,
        )
    )


@router.post("/conversations/{conversation_id}/handoff/return")
def return_conversation(
    conversation_id: str,
    req: HandoffReturnRequest,
    db: Session = Depends(get_db),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    conv = db.get(Conversation, conversation_id)
    if conv is None or conv.deleted_at is not None:
        raise ApiError(404, "NOT_FOUND", f"conversation {conversation_id} not found")
    if conv.handoff_status != "active":
        raise ApiError(409, "HANDOFF_STATE_INVALID", "conversation is not in active human handoff")
    srt = db.execute(select(SessionRuntime).where(SessionRuntime.conversation_id == conversation_id)).scalars().first()
    tk = db.execute(
        select(TakeoverRequest).where(TakeoverRequest.conversation_id == conversation_id, TakeoverRequest.status == "active")
    ).scalars().first()
    if tk is not None:
        tk.status = "resolved"
        tk.resolved_at = _utcnow()
    conv.handoff_status = "none"
    new_state = "AUTO_HOSTING" if req.resume_mode in ("continue", "replan") else "IDLE"
    if srt is not None:
        srt.handoff_status = "none"
        srt.session_state = new_state
    db.commit()
    return ok(
        HandoffResponseData(
            handoff_status=conv.handoff_status,
            session_state=srt.session_state if srt else new_state,
            affected_run_id=srt.active_run_id if srt else None,
        )
    )


# ---------------- Workflow Runs ----------------

@router.post("/workflow-runs")
def create_workflow_run(
    req: CreateWorkflowRunRequest,
    db: Session = Depends(get_db),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    detail = start_manual_run(db, req, idempotency_key)
    return ok(CreateWorkflowRunResponseData(run_id=detail.run_id, status=detail.status), status_code=201)


@router.get("/workflow-runs/{run_id}")
def get_workflow_run(run_id: str, db: Session = Depends(get_db)):
    run = db.get(WorkflowRun, run_id)
    if run is None:
        raise ApiError(404, "NOT_FOUND", f"run {run_id} not found")
    return ok(
        WorkflowRunDetail(
            run_id=run.id,
            project_id=run.project_id,
            conversation_id=run.conversation_id,
            workflow_version_id=run.workflow_version_id,
            status=run.status,
            trigger_type=run.trigger_type,
            current_node_id=run.current_node_id,
            started_at=iso(run.started_at),
            ended_at=iso(run.ended_at),
            error_code=run.error_code,
            error_message=run.error_message,
            result_summary=run.result_summary,
            parent_run_id=run.parent_run_id,
            root_run_id=run.root_run_id,
        )
    )


@router.get("/workflow-runs/{run_id}/node-executions")
def list_node_executions(run_id: str, db: Session = Depends(get_db)):
    run = db.get(WorkflowRun, run_id)
    if run is None:
        raise ApiError(404, "NOT_FOUND", f"run {run_id} not found")
    rows = db.execute(select(WorkflowRunStep).where(WorkflowRunStep.run_id == run_id).order_by(WorkflowRunStep.started_at)).scalars().all()
    items = [
        NodeExecution(
            node_execution_id=s.node_execution_id,
            node_id=s.node_id,
            node_type=s.node_type,
            status=s.status,
            attempt_no=s.attempt_no,
            duration_ms=s.duration_ms,
            error_code=s.error_code,
            executor_type=s.executor_type,
        )
        for s in rows
    ]
    return ok(NodeExecutionListData(items=items))


def _mutate_run(db: Session, run_id: str, new_status: str):
    run = db.get(WorkflowRun, run_id)
    if run is None:
        raise ApiError(404, "NOT_FOUND", f"run {run_id} not found")
    if run.status in ("completed", "cancelled", "failed"):
        raise ApiError(409, "RUN_ALREADY_COMPLETED", f"run {run_id} already in terminal state {run.status}")
    run.status = new_status
    if new_status in ("completed", "cancelled", "failed", "interrupted"):
        run.ended_at = _utcnow()
    db.commit()
    return WorkflowRunStateMutationData(run_id=run.id, status=run.status)


@router.post("/workflow-runs/{run_id}/interrupt")
def interrupt_workflow_run(
    run_id: str,
    req: InterruptWorkflowRunRequest,
    db: Session = Depends(get_db),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    return ok(_mutate_run(db, run_id, "interrupted"))


@router.post("/workflow-runs/{run_id}/resume")
def resume_workflow_run(
    run_id: str,
    req: ResumeWorkflowRunRequest,
    db: Session = Depends(get_db),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    new_status = "running" if req.resume_mode in ("continue", "replan") else "completed"
    return ok(_mutate_run(db, run_id, new_status))


@router.post("/workflow-runs/{run_id}/cancel")
def cancel_workflow_run(
    run_id: str,
    req: CancelWorkflowRunRequest,
    db: Session = Depends(get_db),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    return ok(_mutate_run(db, run_id, "cancelled"))


# ---------------- Audit listings ----------------

def _policy_decisions_data(db: Session, run_id: str | None, conversation_id: str | None, decision_type: str | None, page: int, page_size: int):
    q = select(PolicyDecision)
    if run_id:
        q = q.where(PolicyDecision.run_id == run_id)
    if conversation_id:
        q = q.where(PolicyDecision.conversation_id == conversation_id)
    if decision_type:
        q = q.where(PolicyDecision.decision_type == decision_type)
    total = len(db.execute(q).scalars().all())
    rows = db.execute(q.order_by(PolicyDecision.decided_at.desc()).limit(page_size).offset((page - 1) * page_size)).scalars().all()
    items = [
        PolicyDecisionDTO(
            policy_decision_id=p.id,
            decision_type=p.decision_type,
            decision=p.decision,
            reason_codes=p.reason_codes or [],
            decided_at=p.decided_at.isoformat() if isinstance(p.decided_at, datetime) else str(p.decided_at),
            model_profile=p.model_profile,
        )
        for p in rows
    ]
    return PolicyDecisionListData(items=items, page=page, page_size=page_size, total=total)


@router.get("/conversations/{conversation_id}/policy-decisions")
def list_conversation_policy_decisions(
    conversation_id: str,
    db: Session = Depends(get_db),
    decision_type: str | None = Query(default=None, alias="decisionType"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200, alias="pageSize"),
):
    return ok(_policy_decisions_data(db, None, conversation_id, decision_type, page, page_size))


@router.get("/workflow-runs/{run_id}/policy-decisions")
def list_workflow_run_policy_decisions(
    run_id: str,
    db: Session = Depends(get_db),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200, alias="pageSize"),
):
    return ok(_policy_decisions_data(db, run_id, None, None, page, page_size))


@router.get("/workflow-runs/{run_id}/agent-invocations")
def list_agent_invocations(run_id: str, db: Session = Depends(get_db)):
    run = db.get(WorkflowRun, run_id)
    if run is None:
        raise ApiError(404, "NOT_FOUND", f"run {run_id} not found")
    rows = db.execute(select(AgentInvocation).where(AgentInvocation.run_id == run_id).order_by(AgentInvocation.created_at)).scalars().all()
    items = [
        AgentInvocationDTO(
            agent_invocation_id=a.id,
            agent_type=a.agent_type,
            model_name=a.model_name,
            latency_ms=a.latency_ms,
            estimated_cost=a.estimated_cost,
            status=a.status,
            confidence=a.confidence,
        )
        for a in rows
    ]
    return ok(AgentInvocationListData(items=items))

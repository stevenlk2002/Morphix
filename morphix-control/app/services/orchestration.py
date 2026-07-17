"""Orchestration engine (MVP deterministic implementation).

Handles the core chain:
  inbound message -> Conversation + SessionRuntime -> WorkflowRun
  -> node-by-node stepping (agent invoke stub / device command / policy decision)
  -> DeviceCommand(s) pending on the device, or completed run.

Real LLM multi-Agent execution and the Policy Router are behind stubs
(agents.py / policy.py). The engine calls those services directly to avoid
HTTP self-calls.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.envelope import ApiError
from app.models import (
    AgentInvocation,
    AuditLog,
    Bot,
    Conversation,
    Device,
    DeviceCommand,
    Message,
    PolicyDecision,
    Project,
    SessionRuntime,
    WorkflowRun,
    WorkflowRunStep,
    WorkflowVersion,
)
from app.schemas import (
    AgentInvocation as AgentInvocationDTO,
    CreateWorkflowRunRequest,
    InboundMessageEventAcceptedData,
    InboundMessageEventRequest,
    PolicyDecision as PolicyDecisionDTO,
    WorkflowRunDetail,
)
from app.services import agents as agent_svc
from app.services import policy as policy_svc


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt) -> str:
    if dt is None:
        return None
    if isinstance(dt, datetime):
        return dt.isoformat()
    return str(dt)


def _find_start_node(nodes: list[dict], edges: list[dict]) -> dict | None:
    if not nodes:
        return None
    incoming = {n["id"]: 0 for n in nodes}
    for e in edges or []:
        incoming[e["target"]] = incoming.get(e["target"], 0) + 1
    for n in nodes:
        if n.get("type") == "start":
            return n
    for n in nodes:
        if incoming.get(n["id"], 0) == 0:
            return n
    return nodes[0]


def _published_workflow(db: Session, project_id: str) -> WorkflowVersion:
    wfv = (
        db.execute(
            select(WorkflowVersion)
            .where(WorkflowVersion.project_id == project_id, WorkflowVersion.status == "published")
            .order_by(WorkflowVersion.published_at.desc())
        )
        .scalars()
        .first()
    )
    if wfv is None:
        raise ApiError(404, "WORKFLOW_VERSION_NOT_FOUND", f"project {project_id} has no published workflow version")
    return wfv


def _default_bot_id(db: Session, project_id: str) -> str | None:
    bot = (
        db.execute(select(Bot).where(Bot.project_id == project_id).order_by(Bot.created_at))
        .scalars()
        .first()
    )
    return bot.id if bot else None


def _step_nodes(
    db: Session,
    *,
    run: WorkflowRun,
    conversation: Conversation,
    definition: dict,
    device_id: str,
    channel_account_id: str,
) -> bool:
    """Walk nodes start->end, recording steps + side effects. Returns True if a pending device command was emitted."""
    nodes = definition.get("nodes", []) or []
    edges = definition.get("edges", []) or []
    start = _find_start_node(nodes, edges)
    if start is None:
        return False

    has_pending_command = False
    current = start
    guard = 0
    while current and guard < 256:
        guard += 1
        node_id = current.get("id", f"n_{guard}")
        node_type = current.get("type", "task")
        data = current.get("data") or {}
        step = WorkflowRunStep(
            id=f"step_{uuid.uuid4().hex}",
            run_id=run.id,
            node_execution_id=f"ne_{uuid.uuid4().hex}",
            node_id=node_id,
            node_type=node_type,
            status="completed",
            attempt_no=1,
            duration_ms=5,
            executor_type="stub",
        )
        db.add(step)

        if node_type in ("agent",) or data.get("agentType"):
            agent_type = data.get("agentType") or "qa"
            result = agent_svc.invoke_agent(
                run_id=run.id,
                node_execution_id=step.node_execution_id,
                agent_type=agent_type,
                model_profile="stub",
                structured_input={"nodeId": node_id, "message": data},
            )
            inv = AgentInvocation(
                id=f"ai_{uuid.uuid4().hex}",
                run_id=run.id,
                node_execution_id=step.node_execution_id,
                agent_type=agent_type,
                model_name="stub",
                latency_ms=result["latencyMs"],
                estimated_cost=result["estimatedCost"],
                status="succeeded",
                confidence=result["confidence"],
            )
            db.add(inv)

        elif node_type in ("device_command", "send_message", "send_media") or data.get("commandType"):
            command_type = data.get("commandType", "send_message")
            payload = data.get("payload", {}) or {}
            cmd = DeviceCommand(
                id=f"cmd_{uuid.uuid4().hex}",
                project_id=conversation.project_id,
                device_id=device_id,
                channel_account_id=channel_account_id,
                conversation_id=conversation.id,
                run_id=run.id,
                command_type=command_type,
                payload=payload,
                status="pending",
            )
            db.add(cmd)
            has_pending_command = True
            policy_svc.publish_policy_decision(
                db,
                project_id=conversation.project_id,
                conversation_id=conversation.id,
                run_id=run.id,
                decision_type="bot_selection",
                decision="proactive_send",
                reason_codes=["rule:device_command_emitted"],
            )

        elif node_type == "policy":
            policy_svc.publish_policy_decision(
                db,
                project_id=conversation.project_id,
                conversation_id=conversation.id,
                run_id=run.id,
                decision_type="interrupt",
                decision="continue",
                reason_codes=["rule:policy_node_pass"],
            )

        # start / end / unknown -> no side effect

        nexts = [e["target"] for e in edges if e.get("source") == node_id]
        current = None
        for n in nodes:
            if n["id"] == (nexts[0] if nexts else None):
                current = n
                break

    run.status = "completed"
    run.ended_at = _utcnow()
    run.result_summary = "workflow completed (MVP stub)"
    return has_pending_command


def process_inbound_event(
    db: Session,
    req: InboundMessageEventRequest,
    idempotency_key: str | None = None,
) -> InboundMessageEventAcceptedData:
    """Create/update conversation + run from an inbound message (idempotent on sourceMessageId)."""
    # Dedupe on source message id (semantic duplicate detection a la TC-E01).
    dup = (
        db.execute(
            select(Message).where(Message.source_message_id == req.source_message_id)
        )
        .scalars()
        .first()
    )
    if dup is not None:
        conv = db.get(Conversation, dup.conversation_id)
        srt = (
            db.execute(select(SessionRuntime).where(SessionRuntime.conversation_id == conv.id))
            .scalars()
            .first()
        )
        return InboundMessageEventAcceptedData(
            conversation_id=conv.id,
            message_id=dup.id,
            session_runtime_id=srt.id if srt else conv.id,
            accepted=False,
            dispatch_mode="async_queue",
        )

    project = db.get(Project, req.project_id)
    if project is None:
        raise ApiError(404, "NOT_FOUND", f"project {req.project_id} not found")

    wfv = _published_workflow(db, req.project_id)
    bot_id = _default_bot_id(db, req.project_id)

    conv = Conversation(
        project_id=req.project_id,
        channel_account_id=req.channel_account_id,
        conversation_type=req.conversation_type,
        subject=req.contact.display_name or "对话",
        owner_type="ai",
        handoff_status="none",
        current_bot_id=bot_id,
        current_workflow_version_id=wfv.id,
        contact={
            "externalUid": req.contact.external_uid,
            "displayName": req.contact.display_name,
            "tags": req.contact.tags,
        },
    )
    db.add(conv)
    db.flush()

    msg = Message(
        conversation_id=conv.id,
        seq_no=1,
        sender_type="customer",
        message_type=req.message.message_type,
        content_text=req.message.content_text,
        source_message_id=req.source_message_id,
    )
    db.add(msg)
    db.flush()

    srt = SessionRuntime(conversation_id=conv.id, session_state="IDLE", hosting_status="enabled")
    db.add(srt)
    db.flush()

    run = WorkflowRun(
        project_id=req.project_id,
        conversation_id=conv.id,
        workflow_version_id=wfv.id,
        status="running",
        trigger_type="inbound_message",
    )
    db.add(run)
    db.flush()
    srt.active_run_id = run.id

    has_pending = _step_nodes(
        db,
        run=run,
        conversation=conv,
        definition=wfv.definition or {},
        device_id=req.device_id,
        channel_account_id=req.channel_account_id,
    )

    srt.session_state = "WAITING_DEVICE_ACK" if has_pending else "IDLE"

    policy_svc.publish_policy_decision(
        db,
        project_id=req.project_id,
        conversation_id=conv.id,
        run_id=run.id,
        decision_type="workflow_selection",
        decision=wfv.id,
        reason_codes=["rule:inbound_triggered"],
    )
    db.add(
        AuditLog(
            id=f"aud_{uuid.uuid4().hex}",
            event_type="inbound_message",
            resource_type="conversation",
            resource_id=conv.id,
            project_id=req.project_id,
            actor_id=req.device_id,
            detail={"sourceMessageId": req.source_message_id, "runId": run.id},
        )
    )
    db.commit()

    return InboundMessageEventAcceptedData(
        conversation_id=conv.id,
        message_id=msg.id,
        session_runtime_id=srt.id,
        accepted=True,
        dispatch_mode="sync_orchestrate",
    )


def start_manual_run(db: Session, req: CreateWorkflowRunRequest, idempotency_key: str | None = None) -> WorkflowRunDetail:
    """Manually start a workflow run for an existing conversation."""
    conv = db.get(Conversation, req.conversation_id)
    if conv is None:
        raise ApiError(404, "CONVERSATION_NOT_FOUND", f"conversation {req.conversation_id} not found")
    wfv = db.get(WorkflowVersion, req.workflow_version_id)
    if wfv is None:
        raise ApiError(404, "WORKFLOW_VERSION_NOT_FOUND", f"workflow version {req.workflow_version_id} not found")

    srt = (
        db.execute(select(SessionRuntime).where(SessionRuntime.conversation_id == conv.id))
        .scalars()
        .first()
    )
    run = WorkflowRun(
        project_id=req.project_id,
        conversation_id=conv.id,
        workflow_version_id=wfv.id,
        status="running",
        trigger_type=req.trigger_type,
    )
    db.add(run)
    db.flush()
    if srt is not None:
        srt.active_run_id = run.id

    # Device for command target: the conversation's most recent device via channel account.
    device = (
        db.execute(
            select(Device).where(
                Device.project_id == req.project_id,
                Device.channel_account_id == conv.channel_account_id,
            ).order_by(Device.created_at.desc())
        )
        .scalars()
        .first()
    )
    device_id = device.id if device else "dev_unknown"
    has_pending = _step_nodes(
        db,
        run=run,
        conversation=conv,
        definition=wfv.definition or {},
        device_id=device_id,
        channel_account_id=conv.channel_account_id,
    )
    if srt is not None:
        srt.session_state = "WAITING_DEVICE_ACK" if has_pending else "IDLE"
    db.commit()

    return WorkflowRunDetail(
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

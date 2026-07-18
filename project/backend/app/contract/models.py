import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.contract.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def gen_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


class Project(Base):
    __tablename__ = "projects"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: gen_id("prj"))
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Bot(Base):
    __tablename__ = "bots"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: gen_id("bot"))
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    inherited_workflow_version_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class WorkflowVersion(Base):
    __tablename__ = "workflow_versions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: gen_id("wfv"))
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(32), default="draft")  # draft|published|archived
    definition: Mapped[dict] = mapped_column(JSON, default=dict)  # {nodes, edges}
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Conversation(Base):
    __tablename__ = "conversations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: gen_id("conv"))
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    channel_account_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    conversation_type: Mapped[str] = mapped_column(String(32), default="direct")
    subject: Mapped[str] = mapped_column(String(300), default="")
    owner_type: Mapped[str] = mapped_column(String(16), default="ai")  # ai|human
    handoff_status: Mapped[str] = mapped_column(String(32), default="none")
    current_bot_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    current_workflow_version_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    contact: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class SessionRuntime(Base):
    __tablename__ = "session_runtimes"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: gen_id("srt"))
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"), nullable=False, unique=True, index=True)
    hosting_status: Mapped[str] = mapped_column(String(32), default="enabled")
    session_state: Mapped[str] = mapped_column(String(32), default="IDLE")
    handoff_status: Mapped[str] = mapped_column(String(32), default="none")

    __table_args__ = (
        CheckConstraint(
            text(
                "session_state IN ('IDLE','AUTO_HOSTING','WAITING_USER','WAITING_TIMER',"
                "'WAITING_DEVICE_ACK','HUMAN_HANDOFF','PAUSED_BY_POLICY','ERROR_REVIEW','CLOSED')"
            ),
            name="ck_session_runtime_session_state",
        ),
        CheckConstraint(
            text("hosting_status IN ('enabled','paused','disabled')"),
            name="ck_session_runtime_hosting_status",
        ),
    )
    interrupt_policy: Mapped[str] = mapped_column(String(32), default="DROP_NEW")
    current_bot_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    current_workflow_version_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    active_run_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    waiting_node_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_policy_decision_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow)


class Message(Base):
    __tablename__ = "messages"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: gen_id("msg"))
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"), nullable=False, index=True)
    seq_no: Mapped[int] = mapped_column(Integer, default=0)
    sender_type: Mapped[str] = mapped_column(String(16), default="customer")
    message_type: Mapped[str] = mapped_column(String(32), default="text")
    content_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    sent_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    source_message_id: Mapped[str | None] = mapped_column(String(128), nullable=True)


class WorkflowRun(Base):
    __tablename__ = "workflow_runs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: gen_id("run"))
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"), nullable=False, index=True)
    workflow_version_id: Mapped[str] = mapped_column(String(36), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending")
    trigger_type: Mapped[str] = mapped_column(String(32), default="manual")
    current_node_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    parent_run_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    root_run_id: Mapped[str | None] = mapped_column(String(36), nullable=True)


class WorkflowRunStep(Base):
    __tablename__ = "workflow_run_steps"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: gen_id("step"))
    run_id: Mapped[str] = mapped_column(ForeignKey("workflow_runs.id"), nullable=False, index=True)
    node_execution_id: Mapped[str] = mapped_column(String(64), nullable=False)
    node_id: Mapped[str] = mapped_column(String(64), nullable=False)
    node_type: Mapped[str] = mapped_column(String(32), default="task")
    status: Mapped[str] = mapped_column(String(32), default="pending")
    attempt_no: Mapped[int] = mapped_column(Integer, default=1)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    executor_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class DeviceCommand(Base):
    __tablename__ = "device_commands"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: gen_id("cmd"))
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    device_id: Mapped[str] = mapped_column(ForeignKey("devices.id"), nullable=False, index=True)
    channel_account_id: Mapped[str] = mapped_column(String(64), nullable=False)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"), nullable=False, index=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("workflow_runs.id"), nullable=False, index=True)
    command_type: Mapped[str] = mapped_column(String(32), default="send_message")
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    policy_decision_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="pending")
    issued_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    acked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    done_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    failed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    retryable: Mapped[bool] = mapped_column(Boolean, default=False)
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)


class PolicyDecision(Base):
    __tablename__ = "policy_decisions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: gen_id("pol"))
    project_id: Mapped[str | None] = mapped_column(ForeignKey("projects.id"), nullable=True, index=True)
    conversation_id: Mapped[str | None] = mapped_column(ForeignKey("conversations.id"), nullable=True, index=True)
    run_id: Mapped[str | None] = mapped_column(ForeignKey("workflow_runs.id"), nullable=True, index=True)
    decision_type: Mapped[str] = mapped_column(String(32), nullable=False)
    decision: Mapped[str] = mapped_column(String(64), nullable=False)
    reason_codes: Mapped[list] = mapped_column(JSON, default=list)
    decided_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    model_profile: Mapped[str | None] = mapped_column(String(64), nullable=True)


class AgentInvocation(Base):
    __tablename__ = "agent_invocations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: gen_id("ai"))
    run_id: Mapped[str] = mapped_column(ForeignKey("workflow_runs.id"), nullable=False, index=True)
    node_execution_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    agent_type: Mapped[str] = mapped_column(String(32), nullable=False)
    model_name: Mapped[str] = mapped_column(String(64), default="stub")
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    estimated_cost: Mapped[float] = mapped_column(default=0.0)
    status: Mapped[str] = mapped_column(String(32), default="succeeded")
    confidence: Mapped[float] = mapped_column(default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class Device(Base):
    __tablename__ = "devices"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: gen_id("dev"))
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    channel_account_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    channel_type: Mapped[str] = mapped_column(String(32), default="wechat")
    account_type: Mapped[str] = mapped_column(String(32), default="personal")
    install_fingerprint: Mapped[str | None] = mapped_column(String(256), nullable=True)
    bind_code: Mapped[str | None] = mapped_column(String(64), nullable=True, unique=True)
    device_token: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    token_expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="online")
    device_meta: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class TakeoverRequest(Base):
    __tablename__ = "takeover_requests"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: gen_id("tk"))
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"), nullable=False, index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    operator_id: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="requested")  # requested|active|resolved
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    requested_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: gen_id("aud"))
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    resource_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    resource_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    project_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    actor_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, index=True)


class IdempotencyRecord(Base):
    __tablename__ = "idempotency_records"
    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    operation: Mapped[str] = mapped_column(String(64), nullable=False)
    resource: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

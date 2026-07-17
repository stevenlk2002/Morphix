from typing import Literal

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

from app.core.envelope import DTO

# ---- shared enums (mirror contract) ----
ConversationType = Literal["direct", "group"]
MessageType = Literal["text", "image", "file", "voice", "video", "card", "system"]
ChannelType = Literal["wechat", "wecom", "qq", "unknown"]
DispatchMode = Literal["sync_orchestrate", "async_queue"]
HostingStatus = Literal["enabled", "paused", "disabled"]
SessionState = Literal[
    "IDLE", "AUTO_HOSTING", "WAITING_USER", "WAITING_TIMER", "WAITING_DEVICE_ACK",
    "HUMAN_HANDOFF", "PAUSED_BY_POLICY", "ERROR_REVIEW", "CLOSED",
]
HandoffStatus = Literal["none", "requested", "active", "returning"]
InterruptPolicy = Literal["DROP_NEW", "INTERRUPT_AND_REPLAN", "MERGE_WINDOW"]
WorkflowRunStatus = Literal[
    "pending", "running", "waiting", "interrupted", "failed", "cancelled", "completed"
]
ResumeMode = Literal["idle", "continue", "replan", "restart_from_node"]
DeviceCommandStatus = Literal[
    "pending", "sent", "acked", "done", "failed", "expired", "cancelled"
]
CommandType = Literal["send_message", "send_media", "sync_contacts", "sync_groups", "noop"]
DecisionType = Literal[
    "bot_selection", "workflow_selection", "interrupt", "handoff",
    "model_profile", "risk_block", "supervisor_gate",
]
EventType = Literal["inbound_message", "timer_trigger", "operator_action", "campaign_trigger"]
AgentType = Literal[
    "qa", "sales_progress", "expression_control", "risk_guard", "supervisor", "summarizer"
]
DeviceStatus = Literal["online", "degraded", "paused", "frozen", "offline"]
ChannelAccountStatus = Literal["online", "reconnecting", "logged_out", "restricted", "suspended"]
SyncMode = Literal["full", "incremental"]
DeviceControlFlag = Literal["pause_command_pull", "freeze_device", "require_snapshot_upload", "downgrade_polling"]
AccountType = Literal["personal", "enterprise"]
NodeStatus = Literal["pending", "running", "waiting", "failed", "completed", "skipped"]
AgentStatus = Literal["pending", "succeeded", "failed", "blocked"]
InboundMsgType = Literal["text", "image", "video", "voice", "file", "card", "event"]


# ---- request sub-objects ----
class ContactRef(DTO):
    external_uid: str
    display_name: str | None = None
    tags: list[str] | None = None


class InboundMessage(DTO):
    message_type: MessageType
    content_text: str | None = None
    media_url: str | None = None
    sent_at: str


class EventMetadata(DTO):
    channel_type: ChannelType | None = None
    room_topic: str | None = None
    raw_payload_digest: str | None = None


class DeviceMeta(DTO):
    brand: str
    model: str
    os_version: str
    app_version: str
    locale: str | None = None
    timezone: str | None = None
    network_type: Literal["wifi", "cellular", "offline", "unknown"] | None = None


class DeviceCommandPayload(DTO):
    message_type: MessageType | None = None
    content_text: str | None = None
    media_url: str | None = None
    extra: dict | None = None


class ContactIdentity(DTO):
    external_uid: str
    display_name: str | None = None
    remark_name: str | None = None


class GroupIdentity(DTO):
    external_group_id: str
    group_name: str | None = None


class InboundMessagePayload(DTO):
    message_type: InboundMsgType
    content_text: str | None = None
    media_url: str | None = None
    media_digest: str | None = None
    sent_at: str


class DeviceCommandQueueStatus(DTO):
    pending_count: int = 0
    running_count: int = 0
    retry_count: int = 0
    oldest_pending_at: str | None = None


class DeviceNetworkStatus(DTO):
    network_type: Literal["wifi", "cellular", "offline", "unknown"] | None = None
    signal_level: int | None = None
    ip_address: str | None = None


class DeviceBatteryStatus(DTO):
    percent: int | None = None
    charging: bool | None = None
    power_save_mode: bool | None = None


class DeviceAppRuntimeStatus(DTO):
    process_state: Literal["foreground", "background", "restarting", "unknown"] | None = None
    uptime_sec: int | None = None
    last_crash_at: str | None = None
    storage_used_mb: int | None = None


class DeviceControlDirective(DTO):
    action: Literal[
        "noop", "pause_command_pull", "resume_command_pull", "freeze_device",
        "upload_snapshot", "force_token_refresh",
    ]
    reason: str | None = None
    until: str | None = None
    params: dict | None = None


class ContactSyncItem(DTO):
    external_uid: str
    display_name: str | None = None
    remark_name: str | None = None
    avatar_url: str | None = None
    phone: str | None = None
    tags: list[str] | None = None
    sync_action: Literal["upsert", "delete"]
    updated_at: str | None = None


class GroupSyncItem(DTO):
    external_group_id: str
    group_name: str | None = None
    member_count: int | None = None
    owner_external_uid: str | None = None
    notice_digest: str | None = None
    sync_action: Literal["upsert", "delete"]
    updated_at: str | None = None


class DeviceDiagnosticLogEntry(DTO):
    level: Literal["debug", "info", "warn", "error"]
    occurred_at: str
    category: Literal[
        "bootstrap", "auth", "heartbeat", "command_pull", "command_exec",
        "inbound_message", "sync_contacts", "sync_groups", "handoff", "storage",
    ]
    message: str
    context: dict | None = None


class DeviceCommandSnapshotItem(DTO):
    command_id: str | None = None
    command_type: str | None = None
    status: Literal["pending", "running", "acked", "completed", "failed"] | None = None
    started_at: str | None = None
    ended_at: str | None = None
    failure_reason: str | None = None


class DiagnosticAttachment(DTO):
    name: str | None = None
    content_type: str | None = None
    url: str | None = None
    digest: str | None = None


# ---- request bodies ----
class InboundMessageEventRequest(DTO):
    project_id: str
    channel_account_id: str
    device_id: str
    conversation_type: ConversationType
    source_conversation_id: str
    source_message_id: str
    contact: ContactRef
    message: InboundMessage
    metadata: EventMetadata | None = None


class HandoffRequest(DTO):
    project_id: str
    operator_id: str
    reason: str


class HandoffReturnRequest(DTO):
    project_id: str
    operator_id: str
    resume_mode: ResumeMode


class CreateWorkflowRunRequest(DTO):
    project_id: str
    conversation_id: str
    workflow_version_id: str
    trigger_type: Literal["manual", "inbound_message", "retry", "campaign"]
    input_context: dict | None = None


class InterruptWorkflowRunRequest(DTO):
    reason: str
    operator_id: str


class ResumeWorkflowRunRequest(DTO):
    resume_mode: ResumeMode
    operator_id: str
    restart_from_node_id: str | None = None


class CancelWorkflowRunRequest(DTO):
    reason: str
    operator_id: str


class CreateDeviceCommandRequest(DTO):
    project_id: str
    device_id: str
    channel_account_id: str
    conversation_id: str
    run_id: str
    command_type: CommandType
    payload: DeviceCommandPayload
    policy_decision_id: str | None = None


class DeviceCommandAckRequest(DTO):
    device_id: str
    acked_at: str


class DeviceCommandCompleteRequest(DTO):
    device_id: str
    done_at: str
    result: dict | None = None


class DeviceCommandFailRequest(DTO):
    device_id: str
    failed_at: str
    failure_reason: str
    retryable: bool


class InternalPolicyEvaluateRequest(DTO):
    project_id: str
    conversation_id: str
    session_runtime_id: str
    event_type: EventType
    event_payload: dict
    context: dict


class InternalAgentInvokeRequest(DTO):
    run_id: str
    node_execution_id: str
    agent_type: AgentType
    model_profile: str
    structured_input: dict
    knowledge_context: dict | None = None
    tool_scope: list[str] | None = None


class InternalSupervisorRequest(DTO):
    run_id: str
    conversation_id: str
    trigger_reason: str
    structured_context: dict
    candidate_plans: list[dict] | None = None


class DeviceRegistrationRequest(DTO):
    bind_code: str
    project_id: str
    channel_type: ChannelType
    account_type: AccountType
    install_fingerprint: str
    device_meta: DeviceMeta


class DeviceTokenRefreshRequest(DTO):
    refresh_reason: Literal["expiring", "rotated_by_server", "app_reinstall_recovery", "suspected_leakage"]
    current_token_digest: str | None = None


class DeviceHeartbeatRequest(DTO):
    device_id: str
    reported_at: str
    device_status: DeviceStatus
    account_status: ChannelAccountStatus
    command_queue: DeviceCommandQueueStatus
    network: DeviceNetworkStatus | None = None
    battery: DeviceBatteryStatus | None = None
    app_runtime: DeviceAppRuntimeStatus | None = None
    last_seen_message_at: str | None = None
    last_acked_command_id: str | None = None
    metadata: dict | None = None


class DeviceInboundMessageRequest(DTO):
    device_id: str
    channel_account_id: str
    channel_type: ChannelType
    source_conversation_id: str
    source_message_id: str
    conversation_type: ConversationType
    contact: ContactIdentity
    group: GroupIdentity | None = None
    message: InboundMessagePayload
    raw_context: dict | None = None


class ContactSyncBatchRequest(DTO):
    device_id: str
    channel_account_id: str
    sync_session_id: str
    sync_mode: SyncMode
    cursor: str | None = None
    batch_no: int
    finished: bool
    contacts: list[ContactSyncItem]


class GroupSyncBatchRequest(DTO):
    device_id: str
    channel_account_id: str
    sync_session_id: str
    sync_mode: SyncMode
    cursor: str | None = None
    batch_no: int
    finished: bool
    groups: list[GroupSyncItem]


class DeviceDiagnosticLogBatchRequest(DTO):
    device_id: str
    reported_at: str
    incident_id: str | None = None
    logs: list[DeviceDiagnosticLogEntry]


class DeviceDiagnosticSnapshotRequest(DTO):
    device_id: str
    captured_at: str
    snapshot_type: Literal["runtime_state", "crash_recovery", "command_stall", "manual_support"]
    summary: str | None = None
    last_commands: list[DeviceCommandSnapshotItem] | None = None
    metrics: dict | None = None
    attachments: list[DiagnosticAttachment] | None = None


# ---- management CRUD (contract-TBD) request bodies ----
class ProjectCreate(DTO):
    name: str
    description: str | None = None


class ProjectUpdate(DTO):
    name: str | None = None
    description: str | None = None
    status: str | None = None


class BotCreate(DTO):
    project_id: str
    name: str
    description: str | None = None
    inherited_workflow_version_id: str | None = None


class BotUpdate(DTO):
    name: str | None = None
    description: str | None = None
    status: str | None = None


class WorkflowVersionCreate(DTO):
    project_id: str
    name: str
    definition: dict  # {nodes, edges}


# ---- response data models ----
class BotSummary(DTO):
    id: str
    name: str


class ConversationListItem(DTO):
    conversation_id: str
    channel_account_id: str
    conversation_type: ConversationType
    subject: str
    session_state: SessionState
    handoff_status: HandoffStatus
    current_bot: BotSummary | None = None
    last_message_at: str | None = None
    last_message_preview: str | None = None


class ConversationListData(DTO):
    items: list[ConversationListItem] = []
    page: int = 1
    page_size: int = 20
    total: int = 0


class HandoffSnapshot(DTO):
    operator_id: str | None = None
    requested_at: str | None = None
    activated_at: str | None = None
    reason: str | None = None


class ConversationDetail(DTO):
    conversation_id: str
    project_id: str
    channel_account_id: str
    conversation_type: ConversationType
    subject: str
    owner_type: Literal["ai", "human"]
    handoff_status: HandoffStatus
    current_bot: BotSummary | None = None
    current_workflow_version_id: str | None = None
    latest_handoff: HandoffSnapshot | None = None
    contact: ContactRef | None = None


class ConversationMessage(DTO):
    message_id: str
    seq_no: int
    sender_type: Literal["customer", "ai", "human", "system", "device"]
    message_type: MessageType
    content_text: str | None = None
    sent_at: str
    source_message_id: str | None = None


class ConversationMessageListData(DTO):
    items: list[ConversationMessage] = []
    has_more: bool = False
    next_before_seq: int | None = None


class ConversationRuntime(DTO):
    session_runtime_id: str
    hosting_status: HostingStatus
    session_state: SessionState
    handoff_status: HandoffStatus
    interrupt_policy: InterruptPolicy
    current_bot_id: str | None = None
    current_workflow_version_id: str | None = None
    active_run_id: str | None = None
    waiting_node_id: str | None = None
    locked_until: str | None = None
    last_policy_decision_id: str | None = None
    updated_at: str


class HandoffResponseData(DTO):
    handoff_status: HandoffStatus
    session_state: SessionState
    affected_run_id: str | None = None


class InboundMessageEventAcceptedData(DTO):
    conversation_id: str
    message_id: str
    session_runtime_id: str
    accepted: bool
    dispatch_mode: DispatchMode


class InboundEventStatusData(DTO):
    status: Literal["accepted", "queued", "processing", "processed", "failed"]
    conversation_id: str | None = None
    run_id: str | None = None
    dispatch_result: Literal[
        "workflow_started", "merged_into_existing_run", "dropped_by_policy",
        "handed_to_human", "failed",
    ] | None = None


class CreateWorkflowRunResponseData(DTO):
    run_id: str
    status: WorkflowRunStatus


class WorkflowRunDetail(DTO):
    run_id: str
    project_id: str
    conversation_id: str
    workflow_version_id: str
    status: WorkflowRunStatus
    trigger_type: str
    current_node_id: str | None = None
    started_at: str
    ended_at: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    result_summary: str | None = None
    parent_run_id: str | None = None
    root_run_id: str | None = None


class NodeExecution(DTO):
    node_execution_id: str
    node_id: str
    node_type: str
    status: NodeStatus
    attempt_no: int = 1
    duration_ms: int | None = None
    error_code: str | None = None
    executor_type: str | None = None


class NodeExecutionListData(DTO):
    items: list[NodeExecution] = []


class WorkflowRunStateMutationData(DTO):
    run_id: str
    status: WorkflowRunStatus


class CreateDeviceCommandResponseData(DTO):
    command_id: str
    status: DeviceCommandStatus


class PendingDeviceCommand(DTO):
    command_id: str
    command_type: CommandType
    payload: DeviceCommandPayload
    issued_at: str
    idempotency_key: str | None = None


class PendingDeviceCommandListData(DTO):
    items: list[PendingDeviceCommand] = []


class DeviceCommandMutationData(DTO):
    command_id: str
    status: DeviceCommandStatus


class PolicyDecision(DTO):
    policy_decision_id: str
    decision_type: DecisionType
    decision: str
    reason_codes: list[str] = []
    decided_at: str
    model_profile: str | None = None


class PolicyDecisionListData(DTO):
    items: list[PolicyDecision] = []
    page: int = 1
    page_size: int = 20
    total: int = 0


class AgentInvocation(DTO):
    agent_invocation_id: str
    agent_type: AgentType
    model_name: str
    latency_ms: int
    estimated_cost: float
    status: AgentStatus
    confidence: float


class AgentInvocationListData(DTO):
    items: list[AgentInvocation] = []


class InternalPolicyEvaluateData(DTO):
    bot_selection: str
    workflow_version_selection: str
    allowed_agent_set: list[AgentType] = []
    model_profile: str
    interrupt_decision: InterruptPolicy
    handoff_decision: Literal["stay_ai", "suggest_human", "force_human"]
    supervisor_needed: bool
    reason_codes: list[str] = []


class InternalAgentInvokeData(DTO):
    structured_output: dict
    summary: str
    confidence: float
    latency_ms: int
    estimated_cost: float


class InternalSupervisorData(DTO):
    recommendation: dict
    confidence: float
    constraints: list[str] = []
    notes: str | None = None


class DeviceRegistrationResponseData(DTO):
    device_id: str
    project_id: str
    channel_account_id: str
    channel_type: ChannelType
    device_token: str
    token_expires_at: str
    heartbeat_interval_sec: int
    command_poll_interval_sec: int
    control_flags: list[DeviceControlFlag] = []


class DeviceTokenRefreshResponseData(DTO):
    device_id: str
    device_token: str
    token_expires_at: str


class DeviceHeartbeatResponseData(DTO):
    server_time: str
    next_heartbeat_in_sec: int
    command_poll_interval_sec: int
    control_directive: DeviceControlDirective
    warnings: list[str] = []


class DeviceInboundMessageResponseData(DTO):
    accepted: Literal[True] = True
    event_id: str
    orchestration_request_id: str
    conversation_id: str | None = None
    deduplicated: bool = False


class SyncBatchAcceptedData(DTO):
    sync_session_id: str
    batch_no: int
    accepted_count: int
    finished: bool
    next_cursor: str | None = None
    ingest_job_id: str | None = None


class DiagnosticUploadAcceptedData(DTO):
    accepted: Literal[True] = True
    received_at: str
    incident_id: str | None = None
    support_ticket_hint: str | None = None


# ---- management CRUD response data (contract-TBD) ----
class ProjectData(DTO):
    id: str
    name: str
    description: str | None = None
    status: str
    created_at: str
    updated_at: str


class BotData(DTO):
    id: str
    project_id: str
    name: str
    description: str | None = None
    inherited_workflow_version_id: str | None = None
    status: str
    created_at: str
    updated_at: str


class WorkflowVersionData(DTO):
    id: str
    project_id: str
    name: str
    version: int
    status: str
    definition: dict
    created_at: str
    published_at: str | None = None

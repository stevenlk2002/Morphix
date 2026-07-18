/**
 * P0 类型草案 —— 对齐 morphix-control/app/schemas 与 control 端点契约。
 *
 * 约定：
 * - 所有日期字段在后端为 ISO 字符串，前端统一用 `string`。
 * - 枚举用 `type` + union 精确镜像后端 `Literal`（见 morphix-control/app/schemas/__init__.py）。
 * - 所有响应包在统一信封 ApiEnvelope<T> 中（code/message/request_id/data）。
 *
 * 对应端点（API base: /api，详见 src/utils/api.js）：
 * - GET  /control/conversations                      -> ConversationListData
 * - GET  /control/conversations/{id}                  -> ConversationDetail
 * - GET  /control/conversations/{id}/messages         -> ConversationMessageListData
 * - GET  /control/conversations/{id}/runtime          -> ConversationRuntime
 * - POST /control/conversations/{id}/handoff          -> HandoffResponseData
 * - POST /control/conversations/{id}/return           -> HandoffResponseData
 * - POST /control/workflow-runs                       -> CreateWorkflowRunResponseData
 * - GET  /control/workflow-runs/{run_id}              -> WorkflowRunDetail
 * - GET  /control/workflow-runs/{run_id}/node-executions -> NodeExecutionListData
 * - GET  /control/workflow-runs/{run_id}/policy-decisions -> PolicyDecisionListData
 * - GET  /control/workflow-runs/{run_id}/agent-invocations -> AgentInvocationListData
 * - POST /control/workflow-runs/{run_id}/interrupt    -> WorkflowRunStateMutationData
 * - POST /control/workflow-runs/{run_id}/resume       -> WorkflowRunStateMutationData
 * - POST /control/workflow-runs/{run_id}/cancel       -> WorkflowRunStateMutationData
 */

// ---- 枚举（镜像 morphix-control Literal）----
export type ConversationType = 'direct' | 'group';
export type MessageType =
  | 'text' | 'image' | 'file' | 'voice' | 'video' | 'card' | 'system';
export type ChannelType = 'wechat' | 'wecom' | 'qq' | 'unknown';
export type HostingStatus = 'enabled' | 'paused' | 'disabled';
export type SessionState =
  | 'IDLE'
  | 'AUTO_HOSTING'
  | 'WAITING_USER'
  | 'WAITING_TIMER'
  | 'WAITING_DEVICE_ACK'
  | 'HUMAN_HANDOFF'
  | 'PAUSED_BY_POLICY'
  | 'ERROR_REVIEW'
  | 'CLOSED';
export type HandoffStatus = 'none' | 'requested' | 'active' | 'returning';
export type InterruptPolicy =
  | 'DROP_NEW' | 'INTERRUPT_AND_REPLAN' | 'MERGE_WINDOW';
export type WorkflowRunStatus =
  | 'pending'
  | 'running'
  | 'waiting'
  | 'interrupted'
  | 'failed'
  | 'cancelled'
  | 'completed';
export type ResumeMode = 'idle' | 'continue' | 'replan' | 'restart_from_node';
export type NodeStatus =
  | 'pending' | 'running' | 'waiting' | 'failed' | 'completed' | 'skipped';
export type DecisionType =
  | 'bot_selection'
  | 'workflow_selection'
  | 'interrupt'
  | 'handoff'
  | 'model_profile'
  | 'risk_block'
  | 'supervisor_gate';
export type AgentType =
  | 'qa'
  | 'sales_progress'
  | 'expression_control'
  | 'risk_guard'
  | 'supervisor'
  | 'summarizer';
export type AgentStatus = 'pending' | 'succeeded' | 'failed' | 'blocked';
export type OwnerType = 'ai' | 'human';
export type SenderType = 'customer' | 'ai' | 'human' | 'system' | 'device';

// ---- 子对象 ----
export interface BotSummary {
  id: string;
  name: string;
}

export interface ContactRef {
  external_uid: string;
  display_name?: string | null;
  tags?: string[] | null;
}

export interface HandoffSnapshot {
  operator_id?: string | null;
  requested_at?: string | null;
  activated_at?: string | null;
  reason?: string | null;
}

// ---- 会话列表 / 详情 / 消息 ----
export interface ConversationListItem {
  conversation_id: string;
  channel_account_id: string;
  conversation_type: ConversationType;
  subject: string;
  session_state: SessionState;
  handoff_status: HandoffStatus;
  current_bot?: BotSummary | null;
  last_message_at?: string | null;
  last_message_preview?: string | null;
}

export interface ConversationListData {
  items: ConversationListItem[];
  page: number;
  page_size: number;
  total: number;
}

export interface ConversationDetail {
  conversation_id: string;
  project_id: string;
  channel_account_id: string;
  conversation_type: ConversationType;
  subject: string;
  owner_type: OwnerType;
  handoff_status: HandoffStatus;
  current_bot?: BotSummary | null;
  current_workflow_version_id?: string | null;
  latest_handoff?: HandoffSnapshot | null;
  contact?: ContactRef | null;
}

export interface ConversationMessage {
  message_id: string;
  seq_no: number;
  sender_type: SenderType;
  message_type: MessageType;
  content_text?: string | null;
  sent_at: string;
  source_message_id?: string | null;
}

export interface ConversationMessageListData {
  items: ConversationMessage[];
  has_more: boolean;
  next_before_seq?: number | null;
}

export interface ConversationRuntime {
  session_runtime_id: string;
  hosting_status: HostingStatus;
  session_state: SessionState;
  handoff_status: HandoffStatus;
  interrupt_policy: InterruptPolicy;
  current_bot_id?: string | null;
  current_workflow_version_id?: string | null;
  active_run_id?: string | null;
  waiting_node_id?: string | null;
  locked_until?: string | null;
  last_policy_decision_id?: string | null;
  updated_at: string;
}

// ---- 接管 ----
export interface HandoffRequest {
  project_id: string;
  operator_id: string;
  reason: string;
}
export interface HandoffReturnRequest {
  project_id: string;
  operator_id: string;
  resume_mode: ResumeMode;
}
export interface HandoffResponseData {
  handoff_status: HandoffStatus;
  session_state: SessionState;
  affected_run_id?: string | null;
}

// ---- Run 调试 ----
export interface CreateWorkflowRunRequest {
  project_id: string;
  conversation_id: string;
  workflow_version_id: string;
  trigger_type: 'manual' | 'inbound_message' | 'retry' | 'campaign';
  input_context?: Record<string, unknown> | null;
}
export interface CreateWorkflowRunResponseData {
  run_id: string;
  status: WorkflowRunStatus;
}

export interface WorkflowRunDetail {
  run_id: string;
  project_id: string;
  conversation_id: string;
  workflow_version_id: string;
  status: WorkflowRunStatus;
  trigger_type: string;
  current_node_id?: string | null;
  started_at: string;
  ended_at?: string | null;
  error_code?: string | null;
  error_message?: string | null;
  result_summary?: string | null;
  parent_run_id?: string | null;
  root_run_id?: string | null;
}

export interface NodeExecution {
  node_execution_id: string;
  node_id: string;
  node_type: string;
  status: NodeStatus;
  attempt_no: number;
  duration_ms?: number | null;
  error_code?: string | null;
  executor_type?: string | null;
}
export interface NodeExecutionListData {
  items: NodeExecution[];
}

export interface PolicyDecision {
  policy_decision_id: string;
  decision_type: DecisionType;
  decision: string;
  reason_codes: string[];
  decided_at: string;
  model_profile?: string | null;
}
export interface PolicyDecisionListData {
  items: PolicyDecision[];
  page: number;
  page_size: number;
  total: number;
}

export interface AgentInvocation {
  agent_invocation_id: string;
  agent_type: AgentType;
  model_name: string;
  latency_ms: number;
  estimated_cost: number;
  status: AgentStatus;
  confidence: number;
}
export interface AgentInvocationListData {
  items: AgentInvocation[];
}

// Run 控制请求体
export interface InterruptWorkflowRunRequest {
  reason: string;
  operator_id: string;
}
export interface ResumeWorkflowRunRequest {
  resume_mode: ResumeMode;
  operator_id: string;
  restart_from_node_id?: string | null;
}
export interface CancelWorkflowRunRequest {
  reason: string;
  operator_id: string;
}
export interface WorkflowRunStateMutationData {
  run_id: string;
  status: WorkflowRunStatus;
}

// ---- 统一信封 ----
export interface ApiEnvelope<T> {
  request_id: string;
  code: number;
  message: string;
  data: T;
}

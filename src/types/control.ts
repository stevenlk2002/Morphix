/**
 * P0 类型定义 —— 对齐 morphix-control 契约与 /api/control/* 端点。
 *
 * 约定：
 * - 所有日期字段在后端为 ISO 字符串，前端统一用 `string`。
 * - 枚举用 `type` + union 精确镜像后端 Literal。
 * - 契约响应统一包在信封 ApiEnvelope<T> 中（requestId / success / data / error）。
 *   信封由 src/api/client.ts 自动解包为 `data`。
 *
 * 对应端点（API base: /api，详见 src/api/client.ts 与 src/services/sessions.ts）：
 * - GET  /control/conversations                      -> ConversationListData
 * - GET  /control/conversations/{id}                 -> ConversationDetail
 * - GET  /control/conversations/{id}/messages        -> ConversationMessageListData
 * - GET  /control/conversations/{id}/runtime         -> ConversationRuntime
 * - POST /control/conversations/{id}/handoff         -> HandoffResponseData
 * - POST /control/conversations/{id}/handoff/return  -> HandoffResponseData
 * - POST /control/workflow-runs                      -> CreateWorkflowRunResponseData
 * - GET  /control/workflow-runs/{run_id}             -> WorkflowRunDetail
 * - GET  /control/workflow-runs/{run_id}/node-executions -> NodeExecutionListData
 * - GET  /control/workflow-runs/{run_id}/policy-decisions -> PolicyDecisionListData
 * - GET  /control/workflow-runs/{run_id}/agent-invocations -> AgentInvocationListData
 * - POST /control/workflow-runs/{run_id}/interrupt   -> WorkflowRunStateMutationData
 * - POST /control/workflow-runs/{run_id}/resume      -> WorkflowRunStateMutationData
 * - POST /control/workflow-runs/{run_id}/cancel      -> WorkflowRunStateMutationData
 */

// ---- 枚举（镜像 morphix-control Literal）----
export type ConversationType = 'direct' | 'group'
export type MessageType =
  | 'text'
  | 'image'
  | 'file'
  | 'voice'
  | 'video'
  | 'card'
  | 'system'
export type ChannelType = 'wechat' | 'wecom' | 'qq' | 'unknown'
export type HostingStatus = 'enabled' | 'paused' | 'disabled'
export type SessionState =
  | 'IDLE'
  | 'AUTO_HOSTING'
  | 'WAITING_USER'
  | 'WAITING_TIMER'
  | 'WAITING_DEVICE_ACK'
  | 'HUMAN_HANDOFF'
  | 'PAUSED_BY_POLICY'
  | 'ERROR_REVIEW'
  | 'CLOSED'
export type HandoffStatus = 'none' | 'requested' | 'active' | 'returning'
export type InterruptPolicy =
  | 'DROP_NEW'
  | 'INTERRUPT_AND_REPLAN'
  | 'MERGE_WINDOW'
export type WorkflowRunStatus =
  | 'pending'
  | 'running'
  | 'waiting'
  | 'interrupted'
  | 'failed'
  | 'cancelled'
  | 'completed'
export type ResumeMode = 'idle' | 'continue' | 'replan' | 'restart_from_node'
export type NodeStatus =
  | 'pending'
  | 'running'
  | 'waiting'
  | 'failed'
  | 'completed'
  | 'skipped'
export type DecisionType =
  | 'bot_selection'
  | 'workflow_selection'
  | 'interrupt'
  | 'handoff'
  | 'model_profile'
  | 'risk_block'
  | 'supervisor_gate'
export type AgentType =
  | 'qa'
  | 'sales_progress'
  | 'expression_control'
  | 'risk_guard'
  | 'supervisor'
  | 'summarizer'
export type AgentStatus = 'pending' | 'succeeded' | 'failed' | 'blocked'
export type OwnerType = 'ai' | 'human'
export type SenderType = 'customer' | 'ai' | 'human' | 'system' | 'device'

// ---- 子对象 ----
export interface BotSummary {
  id: string
  name: string
}

export interface ContactRef {
  externalUid: string
  displayName?: string | null
  tags?: string[] | null
}

export interface HandoffSnapshot {
  operatorId?: string | null
  requestedAt?: string | null
  activatedAt?: string | null
  reason?: string | null
}

// ---- 会话列表 / 详情 / 消息 ----
export interface ConversationListItem {
  conversationId: string
  channelAccountId: string
  conversationType: ConversationType
  subject: string
  sessionState: SessionState
  handoffStatus: HandoffStatus
  currentBot?: BotSummary | null
  lastMessageAt?: string | null
  lastMessagePreview?: string | null
}

export interface ConversationListData {
  items: ConversationListItem[]
  page: number
  pageSize: number
  total: number
}

export interface ConversationDetail {
  conversationId: string
  projectId: string
  channelAccountId: string
  conversationType: ConversationType
  subject: string
  ownerType: OwnerType
  handoffStatus: HandoffStatus
  currentBot?: BotSummary | null
  currentWorkflowVersionId?: string | null
  latestHandoff?: HandoffSnapshot | null
  contact?: ContactRef | null
}

export interface ConversationMessage {
  messageId: string
  seqNo: number
  senderType: SenderType
  messageType: MessageType
  contentText?: string | null
  sentAt: string
  sourceMessageId?: string | null
}

export interface ConversationMessageListData {
  items: ConversationMessage[]
  hasMore: boolean
  nextBeforeSeq?: number | null
}

export interface ConversationRuntime {
  sessionRuntimeId: string
  hostingStatus: HostingStatus
  sessionState: SessionState
  handoffStatus: HandoffStatus
  interruptPolicy: InterruptPolicy
  currentBotId?: string | null
  currentWorkflowVersionId?: string | null
  activeRunId?: string | null
  waitingNodeId?: string | null
  lockedUntil?: string | null
  lastPolicyDecisionId?: string | null
  updatedAt: string
}

// ---- 接管 ----
export interface HandoffRequest {
  projectId: string
  operatorId: string
  reason: string
}

export interface HandoffReturnRequest {
  projectId: string
  operatorId: string
  resumeMode: ResumeMode
}

export interface HandoffResponseData {
  handoffStatus: HandoffStatus
  sessionState: SessionState
  affectedRunId?: string | null
}

// ---- Run 调试 ----
export interface CreateWorkflowRunRequest {
  projectId: string
  conversationId: string
  workflowVersionId: string
  triggerType: 'manual' | 'inbound_message' | 'retry' | 'campaign'
  inputContext?: Record<string, unknown> | null
}

export interface CreateWorkflowRunResponseData {
  runId: string
  status: WorkflowRunStatus
}

export interface WorkflowRunDetail {
  runId: string
  projectId: string
  conversationId: string
  workflowVersionId: string
  status: WorkflowRunStatus
  triggerType: string
  currentNodeId?: string | null
  startedAt: string
  endedAt?: string | null
  errorCode?: string | null
  errorMessage?: string | null
  resultSummary?: string | null
  parentRunId?: string | null
  rootRunId?: string | null
}

export interface WorkflowRunListData {
  items: WorkflowRunDetail[]
  page: number
  pageSize: number
  total: number
}

export interface NodeExecution {
  nodeExecutionId: string
  nodeId: string
  nodeType: string
  status: NodeStatus
  attemptNo: number
  durationMs?: number | null
  errorCode?: string | null
  executorType?: string | null
}

export interface NodeExecutionListData {
  items: NodeExecution[]
}

export interface PolicyDecision {
  policyDecisionId: string
  decisionType: DecisionType
  decision: string
  reasonCodes: string[]
  decidedAt: string
  modelProfile?: string | null
}

export interface PolicyDecisionListData {
  items: PolicyDecision[]
  page: number
  pageSize: number
  total: number
}

export interface AgentInvocation {
  agentInvocationId: string
  agentType: AgentType
  modelName: string
  latencyMs: number
  estimatedCost: number
  status: AgentStatus
  confidence: number
}

export interface AgentInvocationListData {
  items: AgentInvocation[]
}

// Run 控制请求体
export interface InterruptWorkflowRunRequest {
  reason: string
  operatorId: string
}

export interface ResumeWorkflowRunRequest {
  resumeMode: ResumeMode
  operatorId: string
  restartFromNodeId?: string | null
}

export interface CancelWorkflowRunRequest {
  reason: string
  operatorId: string
}

export interface WorkflowRunStateMutationData {
  runId: string
  status: WorkflowRunStatus
}

// ---- 统一信封（线格式为 camelCase）----
export interface ErrorEnvelope {
  code: string
  message: string
  details?: Array<Record<string, unknown>>
}

export interface ApiEnvelope<T> {
  requestId: string
  success: boolean
  data: T
  error: ErrorEnvelope | null
}

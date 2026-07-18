/**
 * 渠道会话相关接口封装（契约面 /api/control/*）。
 * 所有响应经 src/api/client.ts 自动解包为 `data`。
 */
import { api } from '../api/client'
import type {
  ConversationListData,
  ConversationDetail,
  ConversationMessageListData,
  ConversationRuntime,
  WorkflowRunListData,
  WorkflowRunDetail,
  NodeExecutionListData,
  PolicyDecisionListData,
  AgentInvocationListData,
} from '../types/control'

type Json = Record<string, unknown>

// 列表查询：会话列表（契约返回 { items, page, pageSize, total }）
export async function listConversations(params: {
  page?: number
  pageSize?: number
} = {}): Promise<ConversationListData> {
  return api.get<ConversationListData>('/control/conversations', { params })
}

// 会话详情
export async function getConversation(conversationId: string): Promise<ConversationDetail> {
  return api.get<ConversationDetail>(`/control/conversations/${conversationId}`)
}

// 会话消息流水（游标分页）
export async function listConversationMessages(
  conversationId: string,
  params: { page?: number; beforeSeq?: number } = {}
): Promise<ConversationMessageListData> {
  return api.get<ConversationMessageListData>(
    `/control/conversations/${conversationId}/messages`,
    { params }
  )
}

// 人工接管（handoff）
export async function takeOverConversation(
  conversationId: string,
  payload: Json
): Promise<unknown> {
  return api.post(`/control/conversations/${conversationId}/handoff`, payload)
}

// 交还控制权
export async function returnConversation(
  conversationId: string,
  data: Json
): Promise<unknown> {
  return api.post(`/control/conversations/${conversationId}/handoff/return`, data)
}

// 创建一次工作流运行
export async function createWorkflowRun(data: Json): Promise<unknown> {
  return api.post('/control/workflow-runs', data)
}

// 会话运行时（活跃运行、最新接管等）
export async function getConversationRuntime(
  conversationId: string,
  projectId?: string
): Promise<ConversationRuntime> {
  const params: Record<string, unknown> = {}
  if (projectId) params.projectId = projectId
  return api.get<ConversationRuntime>(
    `/control/conversations/${conversationId}/runtime`,
    { params }
  )
}

// 工作流运行列表（分页）
export async function listWorkflowRuns(params: {
  projectId?: string
  conversationId?: string
  page?: number
  pageSize?: number
} = {}): Promise<WorkflowRunListData> {
  const query: Record<string, unknown> = {
    page: params.page ?? 1,
    pageSize: params.pageSize ?? 20,
  }
  if (params.projectId) query.projectId = params.projectId
  if (params.conversationId) query.conversationId = params.conversationId
  return api.get<WorkflowRunListData>('/control/workflow-runs', { params: query })
}

// 单个工作流运行详情
export async function getWorkflowRun(runId: string): Promise<WorkflowRunDetail> {
  return api.get<WorkflowRunDetail>(`/control/workflow-runs/${runId}`)
}

// 运行节点执行记录（分页）
export async function listNodeExecutions(params: {
  runId: string
  page?: number
  pageSize?: number
}): Promise<NodeExecutionListData> {
  return api.get<NodeExecutionListData>(
    `/control/workflow-runs/${params.runId}/node-executions`,
    { params: { page: params.page ?? 1, pageSize: params.pageSize ?? 50 } }
  )
}

// 策略决策记录（分页）
export async function listPolicyDecisions(params: {
  conversationId: string
  page?: number
  pageSize?: number
}): Promise<PolicyDecisionListData> {
  return api.get<PolicyDecisionListData>(
    `/control/conversations/${params.conversationId}/policy-decisions`,
    { params: { page: params.page ?? 1, pageSize: params.pageSize ?? 50 } }
  )
}

// Agent 调用记录（分页）
export async function listAgentInvocations(params: {
  runId: string
  page?: number
  pageSize?: number
} = { runId: '' }): Promise<AgentInvocationListData> {
  return api.get<AgentInvocationListData>(
    `/control/workflow-runs/${params.runId}/agent-invocations`,
    { params: { page: params.page ?? 1, pageSize: params.pageSize ?? 50 } }
  )
}

// 中断运行
export async function interruptWorkflowRun(
  runId: string,
  data: Json
): Promise<unknown> {
  return api.post(`/control/workflow-runs/${runId}/interrupt`, data)
}

// 恢复运行
export async function resumeWorkflowRun(runId: string, data: Json): Promise<unknown> {
  return api.post(`/control/workflow-runs/${runId}/resume`, data)
}

// 取消运行
export async function cancelWorkflowRun(runId: string, data: Json): Promise<unknown> {
  return api.post(`/control/workflow-runs/${runId}/cancel`, data)
}

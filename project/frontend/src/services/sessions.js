// 渠道会话相关接口封装（控制面 /api/control/*）
// 响应封套约定：{ success, data, error }，业务数据在 data 字段内。
import { api } from '../utils/api'

const BASE = '/api/control'

// 列表查询：会话列表（必需 projectId）
export async function listConversations(params = {}) {
  const res = await api.get(`${BASE}/conversations`, { params })
  return res.data // { items, page, page_size, total }
}

// 会话详情
export async function getConversation(conversationId) {
  const res = await api.get(`${BASE}/conversations/${conversationId}`)
  return res.data
}

// 会话消息流水
export async function listConversationMessages(conversationId, params = {}) {
  const res = await api.get(`${BASE}/conversations/${conversationId}/messages`, { params })
  return res.data // { items, has_more, next_before_seq }
}

// 会话运行态
export async function getConversationRuntime(conversationId) {
  const res = await api.get(`${BASE}/conversations/${conversationId}/runtime`)
  return res.data
}

// 工作流运行列表（按 conversationId 过滤）
export async function listWorkflowRuns(params = {}) {
  const res = await api.get(`${BASE}/workflow-runs`, { params })
  return res.data // { items, page, page_size, total }
}

// 工作流运行详情
export async function getWorkflowRun(runId) {
  const res = await api.get(`${BASE}/workflow-runs/${runId}`)
  return res.data
}

// 节点执行轨迹
export async function listNodeExecutions(runId, params = {}) {
  const res = await api.get(`${BASE}/workflow-runs/${runId}/node-executions`, { params })
  return res.data // { items }
}

// 策略决策记录
export async function listPolicyDecisions(params = {}) {
  const res = await api.get(`${BASE}/policy-decisions`, { params })
  return res.data // { items, page, page_size, total }
}

// Agent 调用记录
export async function listAgentInvocations(params = {}) {
  const res = await api.get(`${BASE}/agent-invocations`, { params })
  return res.data // { items }
}

// 创建（手动触发）工作流运行
export async function createWorkflowRun(body) {
  const res = await api.post(`${BASE}/workflow-runs`, body)
  return res.data // { run_id, status }
}

// 中断工作流运行
export async function interruptWorkflowRun(runId, body) {
  const res = await api.post(`${BASE}/workflow-runs/${runId}/interrupt`, body)
  return res.data // { run_id, status }
}

// 恢复工作流运行
export async function resumeWorkflowRun(runId, body) {
  const res = await api.post(`${BASE}/workflow-runs/${runId}/resume`, body)
  return res.data
}

// 取消工作流运行
export async function cancelWorkflowRun(runId, body) {
  const res = await api.post(`${BASE}/workflow-runs/${runId}/cancel`, body)
  return res.data
}

// 人工接管（handoff）
export async function takeOverConversation(conversationId, body) {
  const res = await api.post(`${BASE}/conversations/${conversationId}/handoff`, body)
  return res.data // { handoff_status, session_state, affected_run_id }
}

// 交还控制权（handoff return）
export async function returnConversation(conversationId, body) {
  const res = await api.post(`${BASE}/conversations/${conversationId}/handoff/return`, body)
  return res.data
}

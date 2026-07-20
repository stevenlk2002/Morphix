/**
 * 封套感知 fetch 客户端。
 *
 * - 契约域（/api/control、/api/runtime、/internal …）返回统一信封：
 *     { requestId, success, data, error }
 *   客户端检测到信封时自动解包为 `data`；success=false 时抛出 ApiClientError。
 * - 资源域（/api/bots、/api/dashboard、/api/channel-accounts …）返回裸数据
 *   （数组 / 对象），客户端原样返回。
 */

import type {
  AccountDTO,
  ContactDTO,
  ContactDetailDTO,
  SessionDTO,
  MessageDTO,
  HostingSessionDTO,
  HostingRuleDTO,
  TeamDTO,
  WechatSubjectDTO,
  WechatSubjectInput,
  HostingBotDTO,
} from '../types/channels'
import type {
  CustomerListPage,
  CustomerGroupDTO,
  CustomerGroupWithMembersDTO,
  TagGroupDTO,
  CustomerProfileUpdateRequest,
  BatchAiSummaryRequest,
  BatchTagsRequest,
  CustomerGroupCreateWithMembersRequest,
  AddMembersRequest,
} from '../types/customers'

const API_BASE: string = import.meta.env.VITE_API_BASE_URL || '/api'

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

export class ApiClientError extends Error {
  code: string
  details?: Array<Record<string, unknown>>

  constructor(
    message: string,
    code = 'CLIENT_ERROR',
    details?: Array<Record<string, unknown>>
  ) {
    super(message)
    this.name = 'ApiClientError'
    this.code = code
    this.details = details
  }
}

interface RequestOptions {
  method?: string
  params?: Record<string, unknown>
  body?: unknown
  headers?: Record<string, string>
}

function isEnvelope(value: unknown): value is ApiEnvelope<unknown> {
  return (
    typeof value === 'object' &&
    value !== null &&
    'success' in value &&
    'requestId' in value
  )
}

function buildUrl(endpoint: string, params?: Record<string, unknown>): string {
  let url = `${API_BASE}${endpoint}`
  if (params && typeof params === 'object') {
    const search = new URLSearchParams()
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== '') {
        search.append(key, String(value))
      }
    })
    const qs = search.toString()
    if (qs) url += (url.includes('?') ? '&' : '?') + qs
  }
  return url
}

async function request<T>(endpoint: string, options: RequestOptions = {}): Promise<T> {
  const { method = 'GET', params, body, headers } = options
  const url = buildUrl(endpoint, params)
  const config: RequestInit = {
    method,
    headers: {
      'Content-Type': 'application/json',
      ...headers,
    },
  }
  if (body !== undefined) {
    config.body = JSON.stringify(body)
  }

  const response = await fetch(url, config)
  if (!response.ok) {
    let message = `API Error: ${response.status} ${response.statusText}`
    try {
      const errJson: unknown = await response.json()
      if (isEnvelope(errJson) && errJson.error) {
        message = errJson.error.message || message
      } else if (
        errJson &&
        typeof errJson === 'object' &&
        typeof (errJson as { message?: unknown }).message === 'string'
      ) {
        message = (errJson as { message: string }).message
      }
    } catch {
      /* 忽略解析错误，保留默认信息 */
    }
    throw new ApiClientError(message, `HTTP_${response.status}`)
  }

  const json: unknown = await response.json()
  if (isEnvelope(json)) {
    if (!json.success) {
      const err = json.error
      throw new ApiClientError(
        err?.message || '请求失败',
        err?.code || 'API_ERROR',
        err?.details
      )
    }
    return json.data as T
  }
  return json as T
}

type QueryOptions = Omit<RequestOptions, 'method' | 'body'>
type BodyOptions = Omit<RequestOptions, 'method' | 'body'>
type DeleteOptions = Omit<RequestOptions, 'method'>

export const api = {
  get: <T>(endpoint: string, options?: QueryOptions) =>
    request<T>(endpoint, { ...options, method: 'GET' }),
  post: <T>(endpoint: string, body?: unknown, options?: BodyOptions) =>
    request<T>(endpoint, { ...options, method: 'POST', body }),
  put: <T>(endpoint: string, body?: unknown, options?: BodyOptions) =>
    request<T>(endpoint, { ...options, method: 'PUT', body }),
  patch: <T>(endpoint: string, body?: unknown, options?: BodyOptions) =>
    request<T>(endpoint, { ...options, method: 'PATCH', body }),
  delete: <T>(endpoint: string, options?: DeleteOptions) =>
    request<T>(endpoint, { ...options, method: 'DELETE' }),
}

function normalizeArray(res: unknown): unknown[] {
  if (Array.isArray(res)) return res
  if (
    res &&
    typeof res === 'object' &&
    Array.isArray((res as { items?: unknown[] }).items)
  ) {
    return (res as { items: unknown[] }).items
  }
  return []
}

// ---- 资源域封装（裸数据，无信封） ----
export const botsApi = {
  list: () => api.get<unknown>('/bots').then(normalizeArray),
  create: (data: unknown) => api.post<unknown>('/bots', data),
  train: (botId: string) => api.post<unknown>(`/bots/${botId}/train`),
}

export const dashboardApi = {
  get: () => api.get<unknown>('/dashboard'),
}

export const channelsApi = {
  // 遗留端点（保留）
  list: () => api.get<unknown>('/channel-accounts'),
  create: (data: unknown) => api.post<unknown>('/channel-accounts', data),

  // ---- 渠道会话管理域（/api/channels/...） ----
  listTeams: () => api.get<TeamDTO[]>('/channels/teams'),
  createTeam: (data: unknown) => api.post<TeamDTO>('/channels/teams', data),

  listAccounts: () => api.get<AccountDTO[]>('/channels/accounts'),
  createAccount: (data: unknown) => api.post<AccountDTO>('/channels/accounts', data),

  listContacts: (params?: {
    accountId?: string
    type?: string
    status?: string
    search?: string
  }) => api.get<ContactDTO[]>('/channels/contacts', { params }),
  getContactDetail: (id: string) =>
    api.get<ContactDetailDTO>(`/channels/contacts/${id}`),

  listSessions: (params?: {
    accountId?: string
    read?: string
    hosted?: string
    online?: string
    search?: string
  }) => api.get<SessionDTO[]>('/channels/sessions', { params }),
  listSessionMessages: (id: string) =>
    api.get<MessageDTO[]>(`/channels/sessions/${id}/messages`),
  setSessionHosting: (id: string, data: { hosted: boolean; botId?: string | null }) =>
    api.post<SessionDTO>(`/channels/sessions/${id}/hosting`, data),

  listHostingSessions: (params?: {
    accountId?: string
    botId?: string
    sessionType?: string
    nickname?: string
    start?: string
    end?: string
  }) => api.get<HostingSessionDTO[]>('/channels/hosting-sessions', { params }),
  batchUpdateHosting: (data: { ids: string[]; hostedStatus?: string; hostingChain?: string }) =>
    api.post<{ updated: number }>('/channels/hosting-sessions/batch-update', data),

  getHostingRules: (params?: { accountId?: string }) =>
    api.get<HostingRuleDTO>('/channels/hosting-rules', { params }),
  upsertHostingRules: (data: {
    accountId?: string
    autoResumeSeconds?: number | null
    autoCancelEnabled?: boolean
  }) => api.put<HostingRuleDTO>('/channels/hosting-rules', data),

  listWechatSubjects: () => api.get<WechatSubjectDTO[]>('/channels/wechat-subjects'),
  createWechatSubject: (data: WechatSubjectInput) =>
    api.post<WechatSubjectDTO>('/channels/wechat-subjects', data),
  updateWechatSubject: (id: string, data: WechatSubjectInput) =>
    api.put<WechatSubjectDTO>(`/channels/wechat-subjects/${id}`, data),

  listHostingBots: () => api.get<HostingBotDTO[]>('/channels/hosting-bots'),
}

export const tagsApi = {
  list: () => api.get<unknown>('/customer-tags'),
  create: (data: unknown) => api.post<unknown>('/customer-tags', data),
}

/** 知识条目 DTO（snake_case DB → camelCase）。 */
export interface KnowledgeItemDTO {
  id: string
  botId: string
  question: string
  answer: string
  tags: string[]
  source: string
  kind: string
  creator: string
  createdAt: string
  updatedAt: string
}

/** 素材条目 DTO。 */
export interface MaterialItemDTO {
  id: string
  botId: string
  name: string
  type: string
  size: number
  category: string
  url: string | null
  source: string
  usageCount: number
  uploadedAt: string
  updatedAt: string
}

/** 通用分页响应（素材列表）。 */
export interface Paged<T> {
  items: T[]
  total: number
  page: number
  pageSize: number
  hasMore: boolean
}

/** 训练记录 DTO。 */
export interface TrainingRecordDTO {
  id: string
  botId: string
  title: string
  createdAt: string
  goodCount: number
  badCount: number
  totalCount: number
}

/** 训练消息 DTO。 */
export interface TrainingMessageDTO {
  id: string
  recordId: string
  botId: string
  role: string
  content: string
  recordRef: string
  feedback: string | null
  msgOrder: number
  createdAt: string
}

export const knowledgeApi = {
  listByBot: (botId: string, params?: { kind?: string; search?: string }) =>
    api
      .get<KnowledgeItemDTO[]>(`/bots/${botId}/knowledge`, { params })
      .then((res) => normalizeArray(res) as KnowledgeItemDTO[]),
  create: (botId: string, data: unknown) =>
    api.post<unknown>(`/bots/${botId}/knowledge`, data),
  update: (knowledgeId: string, data: unknown) =>
    api.put<unknown>(`/knowledge/${knowledgeId}`, data),
  delete: (knowledgeId: string) => api.delete<unknown>(`/knowledge/${knowledgeId}`),
  batchDelete: (botId: string, ids: string[]) =>
    api.delete<{ deleted: number }>(`/bots/${botId}/knowledge/batch`, { body: { ids } }),
  /** 侧栏「删除知识库」：按 bot_id + kind 删除整库（真实硬删）。 */
  deleteByKind: (botId: string, kind: string) =>
    api.delete<{ deleted: number; kind: string }>(
      `/bots/${botId}/knowledge/base/${kind}`
    ),
}

export const materialsApi = {
  listByBot: (
    botId: string,
    params?: {
      name?: string
      startDate?: string
      endDate?: string
      source?: string
      page?: number
      pageSize?: number
    }
  ) => api.get<Paged<MaterialItemDTO>>(`/bots/${botId}/materials`, { params }),
  create: (botId: string, data: unknown) =>
    api.post<unknown>(`/bots/${botId}/materials`, data),
  delete: (materialId: string) => api.delete<unknown>(`/materials/${materialId}`),
  batchDelete: (botId: string, ids: string[]) =>
    api.delete<{ deleted: number }>(`/bots/${botId}/materials/batch`, { body: { ids } }),
}

export const trainingApi = {
  listRecords: (botId: string) =>
    api.get<TrainingRecordDTO[]>(`/bots/${botId}/training/records`),
  createRecord: (botId: string, title: string) =>
    api.post<TrainingRecordDTO>(`/bots/${botId}/training/records`, { title }),
  deleteRecord: (recordId: string) =>
    api.delete<unknown>(`/training/records/${recordId}`),
  listMessages: (recordId: string) =>
    api.get<TrainingMessageDTO[]>(`/training/records/${recordId}/messages`),
  addMessage: (
    recordId: string,
    data: { role: string; content: string; recordRef?: string }
  ) => api.post<TrainingMessageDTO>(`/training/records/${recordId}/messages`, data),
  updateFeedback: (messageId: string, feedback: 'like' | 'dislike' | null) =>
    api.put<{ id: string; feedback: string | null; record: TrainingRecordDTO }>(
      `/training/messages/${messageId}/feedback`,
      { feedback }
    ),
}

// ---- 托管消息日志 API ----
export type ReplyStatus = '成功' | '失败' | '处理中'

export interface MessageLogNodeDTO {
  name: string
  icon: string // user | chat | robot | search | send
  runtime: string
  input: unknown
  output: unknown
  code: string
}

export interface MessageLogItemDTO {
  id: string
  content: { text: string; type: string }
  question: string
  account: string
  session: string
  robot: string
  channel: string
  time: string
  status: ReplyStatus
}

export interface MessageLogDetailDTO extends Omit<MessageLogItemDTO, 'content'> {
  content: { text: string; type: string }
  nodes: MessageLogNodeDTO[]
}

export const messageLogApi = {
  list: (
    botId: string,
    params?: {
      aiReplyId?: string
      question?: string
      session?: string
      status?: string
      start?: string
      end?: string
      page?: number
      pageSize?: number
    }
  ) => api.get<Paged<MessageLogItemDTO>>(`/bots/${botId}/message-logs`, { params }),
  getDetail: (botId: string, aiReplyId: string) =>
    api.get<MessageLogDetailDTO>(`/bots/${botId}/message-logs/${aiReplyId}`),
}

// ---- 客户管理域 API ----
export const customersApi = {
  /** 客户列表聚合（筛选+分页）。 */
  list: (params?: {
    type?: string
    accountId?: string
    channel?: string
    channelType?: string
    keyword?: string
    tagIds?: string
    dateFrom?: string
    dateTo?: string
    page?: number
    pageSize?: number
  }) => api.get<CustomerListPage>('/customers', { params }),

  /** 客户详情（复用 /api/channels/contacts/{id}）。 */
  getDetail: (id: string) =>
    api.get<ContactDetailDTO>(`/channels/contacts/${id}`),

  /** 更新客户档案。 */
  updateProfile: (contactId: string, data: CustomerProfileUpdateRequest) =>
    api.put<unknown>(`/channels/contacts/${contactId}/profile`, data),

  /** 新增沟通记录。 */
  createCommunication: (customerId: string, data: { content: string; type?: string; aiSummary?: string }) =>
    api.post<unknown>(`/customers/${customerId}/communications`, data),

  /** 获取沟通记录列表。 */
  listCommunications: (customerId: string) =>
    api.get<unknown[]>(`/customers/${customerId}/communications`),

  /** 新增自定义属性。 */
  createAttribute: (customerId: string, data: { name: string; value: string }) =>
    api.post<unknown>(`/customers/${customerId}/attributes`, data),

  /** 获取客户标签。 */
  getCustomerTags: (customerId: string) =>
    api.get<unknown[]>(`/customers/${customerId}/tags`),

  /** 设置客户标签（替换式）。 */
  setCustomerTags: (customerId: string, tagIds: string[]) =>
    api.put<unknown>(`/customers/${customerId}/tags`, { tagIds }),

  /** 批量更新 AI 总结开关。 */
  batchUpdateAiSummary: (data: BatchAiSummaryRequest) =>
    api.put<{ updated: number }>('/customers/batch/ai-summary', data),

  /** 批量操作客户标签。 */
  batchUpdateTags: (data: BatchTagsRequest) =>
    api.put<{ updated: number; rowsAffected: number }>('/customers/batch/tags', data),
}

export const tagGroupsApi = {
  /** 标签组列表（含组内标签）。 */
  list: () => api.get<TagGroupDTO[]>('/customer-tag-groups'),

  /** 新建标签组。 */
  create: (data: { name: string; isHot: boolean; tags: { name: string; color?: string }[] }) =>
    api.post<TagGroupDTO>('/customer-tag-groups', data),

  /** 编辑标签组。 */
  update: (id: string, data: { name?: string; isHot?: boolean; tags?: { name: string; color?: string }[] }) =>
    api.put<TagGroupDTO>(`/customer-tag-groups/${id}`, data),

  /** 删除标签组。 */
  delete: (id: string) =>
    api.delete<{ id: string; deleted: boolean }>(`/customer-tag-groups/${id}`),
}

export const customerGroupsApi = {
  /** 客户分组列表。 */
  list: (params?: { name?: string; type?: string }) =>
    api.get<CustomerGroupDTO[]>('/customer-groups', { params }),

  /** 新建客户分组。 */
  create: (data: { name: string; type?: string; customerIds?: string[] }) =>
    api.post<CustomerGroupDTO>('/customer-groups', data),

  /** 新建客户分组并添加初始成员（事务）。 */
  createWithMembers: (data: CustomerGroupCreateWithMembersRequest) =>
    api.post<CustomerGroupDTO>('/customer-groups/with-members', data),

  /** 批量添加成员到已有分组。 */
  addMembers: (groupId: string, data: AddMembersRequest) =>
    api.post<CustomerGroupDTO>('/customer-groups/' + groupId + '/members', data),

  /** 获取分组详情（含成员列表含聚合数据）。 */
  getWithMembers: (groupId: string) =>
    api.get<CustomerGroupWithMembersDTO>('/customer-groups/' + groupId),

  /** 批量删除客户分组。 */
  delete: (groupIds: string[]) =>
    api.post<{ deleted: number; groupIds: string[] }>('/customer-groups/batch-delete', { group_ids: groupIds }),
}

// ---- 工作流编排 API（后端未实现，USE_API=false 时全部 fallback 到 localStorage） ----
const USE_API = true

export const workflowApi = {
  /** GET /api/orchestration/workflows/{botId} → 加载工作流 */
  load: async (botId: string): Promise<unknown> => {
    if (!USE_API) throw new Error('FALLBACK')
    return api.get(`/orchestration/workflows/${botId}`)
  },
  /** PUT /api/orchestration/workflows/{botId} → 保存工作流 */
  save: async (botId: string, data: unknown): Promise<unknown> => {
    if (!USE_API) throw new Error('FALLBACK')
    return api.put(`/orchestration/workflows/${botId}`, data)
  },
  /** DELETE /api/orchestration/workflows/{botId} → 删除工作流 */
  delete: async (botId: string): Promise<unknown> => {
    if (!USE_API) throw new Error('FALLBACK')
    return api.delete(`/orchestration/workflows/${botId}`)
  },
}

/**
 * 封套感知 fetch 客户端。
 *
 * - 契约域（/api/control、/api/runtime、/internal …）返回统一信封：
 *     { requestId, success, data, error }
 *   客户端检测到信封时自动解包为 `data`；success=false 时抛出 ApiClientError。
 * - 资源域（/api/bots、/api/dashboard、/api/channel-accounts …）返回裸数据
 *   （数组 / 对象），客户端原样返回。
 */

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

export const api = {
  get: <T>(endpoint: string, options?: QueryOptions) =>
    request<T>(endpoint, { ...options, method: 'GET' }),
  post: <T>(endpoint: string, body?: unknown, options?: BodyOptions) =>
    request<T>(endpoint, { ...options, method: 'POST', body }),
  put: <T>(endpoint: string, body?: unknown, options?: BodyOptions) =>
    request<T>(endpoint, { ...options, method: 'PUT', body }),
  patch: <T>(endpoint: string, body?: unknown, options?: BodyOptions) =>
    request<T>(endpoint, { ...options, method: 'PATCH', body }),
  delete: <T>(endpoint: string, options?: QueryOptions) =>
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
  list: () => api.get<unknown>('/channel-accounts'),
  create: (data: unknown) => api.post<unknown>('/channel-accounts', data),
}

export const tagsApi = {
  list: () => api.get<unknown>('/customer-tags'),
  create: (data: unknown) => api.post<unknown>('/customer-tags', data),
}

export const knowledgeApi = {
  listByBot: (botId: string) =>
    api.get<unknown>(`/bots/${botId}/knowledge`).then(normalizeArray),
  create: (botId: string, data: unknown) =>
    api.post<unknown>(`/bots/${botId}/knowledge`, data),
  update: (knowledgeId: string, data: unknown) =>
    api.put<unknown>(`/knowledge/${knowledgeId}`, data),
  delete: (knowledgeId: string) => api.delete<unknown>(`/knowledge/${knowledgeId}`),
}

export const materialsApi = {
  listByBot: (botId: string) =>
    api.get<unknown>(`/bots/${botId}/materials`).then(normalizeArray),
  create: (botId: string, data: unknown) =>
    api.post<unknown>(`/bots/${botId}/materials`, data),
  delete: (materialId: string) => api.delete<unknown>(`/materials/${materialId}`),
}

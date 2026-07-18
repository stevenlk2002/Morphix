const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api'

async function request(endpoint, options = {}) {
  const url = `${API_BASE}${endpoint}`
  const config = {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
  }

  const response = await fetch(url, config)
  if (!response.ok) {
    throw new Error(`API Error: ${response.status} ${response.statusText}`)
  }
  return response.json()
}

export const api = {
  get: (endpoint) => request(endpoint, { method: 'GET' }),
  post: (endpoint, data) =>
    request(endpoint, {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  put: (endpoint, data) =>
    request(endpoint, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),
  patch: (endpoint, data) =>
    request(endpoint, {
      method: 'PATCH',
      body: JSON.stringify(data),
    }),
  delete: (endpoint) => request(endpoint, { method: 'DELETE' }),
}

// 具体 API 调用
export const botsApi = {
  list: () => api.get('/bots'),
  create: (data) => api.post('/bots', data),
  train: (botId) => api.post(`/bots/${botId}/train`),
}

export const dashboardApi = {
  get: () => api.get('/dashboard'),
}

export const channelsApi = {
  list: () => api.get('/channel-accounts'),
  create: (data) => api.post('/channel-accounts', data),
}

export const tagsApi = {
  list: () => api.get('/customer-tags'),
  create: (data) => api.post('/customer-tags', data),
}

export const knowledgeApi = {
  listByBot: (botId) => api.get(`/bots/${botId}/knowledge`),
  create: (botId, data) => api.post(`/bots/${botId}/knowledge`, data),
  update: (knowledgeId, data) => api.put(`/knowledge/${knowledgeId}`, data),
  delete: (knowledgeId) => api.delete(`/knowledge/${knowledgeId}`),
}

export const materialsApi = {
  listByBot: (botId) => api.get(`/bots/${botId}/materials`),
  create: (botId, data) => api.post(`/bots/${botId}/materials`, data),
  delete: (materialId) => api.delete(`/materials/${materialId}`),
}

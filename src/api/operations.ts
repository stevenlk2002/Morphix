/**
 * 运营任务 API 封装。
 *
 * 端点：
 * - listTasks   GET  /api/operations/tasks
 * - createTask  POST /api/operations/tasks
 * - getTask     GET  /api/operations/tasks/:id
 * - updateTask  PUT  /api/operations/tasks/:id
 * - toggleTask  PATCH /api/operations/tasks/:id/toggle
 * - deleteTask  DELETE /api/operations/tasks/:id
 * - listTargets GET  /api/operations/tasks/:id/targets
 * - setTargets  PUT  /api/operations/tasks/:id/targets
 * - listSessions GET /api/operations/targets/sessions
 */

import { api } from './client'
import type {
  OperationTask,
  OperationTaskDetail,
  OperationTaskTarget,
  TargetSession,
  TargetSessionListResponse,
  HostingAccount,
  HostingBot,
  TagItem,
  TagGroup,
  ChannelAccount,
  CreateTaskRequest,
  UpdateTaskRequest,
  TaskTargetInput,
} from '../types/operations'

export interface ListTasksParams extends Record<string, string | undefined> {
  search?: string
  type?: string
  enabled?: string
  run_status?: string
  sortBy?: string
  sortOrder?: string
}

export const operationsTasksApi = {
  /** 任务列表（筛选 + 排序）。 */
  list: (params?: ListTasksParams) =>
    api.get<OperationTask[]>('/operations/tasks', { params }),

  /** 创建任务。 */
  create: (data: CreateTaskRequest) =>
    api.post<OperationTask>('/operations/tasks', data),

  /** 任务详情（含 targets）。 */
  get: (id: string) =>
    api.get<OperationTaskDetail>(`/operations/tasks/${id}`),

  /** 更新任务。 */
  update: (id: string, data: UpdateTaskRequest) =>
    api.put<OperationTask>(`/operations/tasks/${id}`, data),

  /** 启停切换。 */
  toggleEnabled: (id: string) =>
    api.patch<OperationTask>(`/operations/tasks/${id}/toggle`),

  /** 删除任务。 */
  delete: (id: string) =>
    api.delete<{ id: string; deleted: boolean }>(`/operations/tasks/${id}`),

  /** 获取运营对象。 */
  listTargets: (taskId: string) =>
    api.get<OperationTaskTarget[]>(`/operations/tasks/${taskId}/targets`),

  /** 设置运营对象（全量替换）。 */
  setTargets: (taskId: string, targets: TaskTargetInput[]) =>
    api.put<OperationTaskTarget[]>(`/operations/tasks/${taskId}/targets`, { targets }),

  /** 可用会话列表。 */
  listSessions: (params?: {
    account_id?: string
    search?: string
    session_type?: string
    task_id?: string
  }) =>
    api.get<TargetSession[]>(`/operations/targets/sessions`, { params }),

  // ---- 新增：运营对象选择器 v2 ----

  /** 运营对象选择器 v2（分页+多条件筛选）。 */
  listTargetSessionsV2: (params: {
    channel?: string
    sessionType?: string
    keyword?: string
    hostingAccountId?: string
    hostingBotId?: string
    tagId?: string
    tagRelation?: string
    page?: number
    pageSize?: number
  }) =>
    api.get<TargetSessionListResponse>('/operations/target-sessions', { params }),

  /** 托管账号列表。 */
  listHostingAccounts: (channel?: string) =>
    api.get<HostingAccount[]>('/operations/hosting-accounts', {
      params: channel ? { channel } : undefined,
    }),

  /** 托管机器人列表。 */
  listHostingBots: () =>
    api.get<HostingBot[]>('/operations/hosting-bots'),

  /** 客户标签列表。 */
  listTags: () =>
    api.get<TagItem[]>('/operations/tags'),

  /** 标签分组列表。 */
  listTagGroups: () =>
    api.get<TagGroup[]>('/operations/tag-groups'),

  /** AI 生成 Cron 表达式。 */
  aiCron: (prompt: string) =>
    api.post<{ cron: string; explanation?: string }>('/operations/ai-cron', { prompt }),

  /** 渠道账号列表（朋友圈任务选择运营对象）。 */
  listChannelAccounts: (channel: string) =>
    api.get<ChannelAccount[]>('/operations/channel-accounts', { params: { channel } }),
}

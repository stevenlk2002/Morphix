/** 运营任务类型枚举。 */
export type TaskType =
  | '群发任务'
  | '机器人定时任务'
  | '朋友圈任务'
  | '特定节点定时任务'
  | '特定节点机器人定时任务'

/** 运行状态枚举。 */
export type RunStatus = '运行中' | '未运行' | '已完成' | '失败' | '已暂停'

/** 运行频率枚举。 */
export type RunFrequency = '一次' | '每天' | '每周' | '每月' | 'Cron表达式'

/** 调度计划类型（内部使用）。 */
export type ScheduleType = 'once' | 'daily' | 'weekly' | 'monthly' | 'cron'

/** 调度计划配置（判别联合类型）。 */
export type ScheduleConfig =
  | { type: 'once'; runTime: string }
  | { type: 'daily'; runTimes: string[]; effectiveStart: string; effectiveEnd: string }
  | { type: 'weekly'; weekdays: number[]; runTimes: string[]; effectiveStart: string; effectiveEnd: string }
  | { type: 'monthly'; days: number[]; lastDays: number[]; runTimes: string[]; effectiveStart: string; effectiveEnd: string }
  | { type: 'cron'; cron: string }

/** ScheduleType → RunFrequency 映射。 */
const SCHEDULE_TYPE_TO_FREQUENCY: Record<ScheduleType, RunFrequency> = {
  once: '一次',
  daily: '每天',
  weekly: '每周',
  monthly: '每月',
  cron: 'Cron表达式',
}

/** RunFrequency → ScheduleType 映射。 */
const FREQUENCY_TO_SCHEDULE_TYPE: Record<string, ScheduleType> = {
  '一次': 'once',
  '每天': 'daily',
  '每周': 'weekly',
  '每月': 'monthly',
  'Cron表达式': 'cron',
}

/** 将 ScheduleConfig 转为 API 请求中的扁平字段。 */
export function scheduleConfigToApiFields(config: ScheduleConfig): {
  run_frequency: string
  run_time: string
  effective_start: string
  effective_end: string
  cron_expression: string
  schedule_type: string
  schedule_config: string
} {
  const result = {
    run_frequency: SCHEDULE_TYPE_TO_FREQUENCY[config.type],
    run_time: '',
    effective_start: '',
    effective_end: '',
    cron_expression: '',
    schedule_type: config.type,
    schedule_config: JSON.stringify(config),
  }
  switch (config.type) {
    case 'once':
      result.run_time = config.runTime
      break
    case 'cron':
      result.cron_expression = config.cron
      break
    default:
      result.effective_start = config.effectiveStart
      result.effective_end = config.effectiveEnd
      break
  }
  return result
}

/** 从任务 API 响应中还原 ScheduleConfig（兼容新旧字段）。 */
export function apiFieldsToScheduleConfig(task: {
  schedule_config?: string
  run_frequency?: string
  run_time?: string
  effective_start?: string
  effective_end?: string
  cron_expression?: string
}): ScheduleConfig {
  if (task.schedule_config) {
    try {
      const parsed = JSON.parse(task.schedule_config)
      if (parsed && parsed.type) return parsed as ScheduleConfig
    } catch { /* fall through to legacy */ }
  }
  // 从旧字段推导
  const freq = task.run_frequency || '一次'
  const st = FREQUENCY_TO_SCHEDULE_TYPE[freq] || 'once'
  const rt = task.run_time || ''
  const es = task.effective_start || ''
  const ee = task.effective_end || ''
  const cron = task.cron_expression || ''
  switch (st) {
    case 'once':
      return { type: 'once', runTime: rt }
    case 'daily':
      return { type: 'daily', runTimes: rt ? [rt] : [], effectiveStart: es, effectiveEnd: ee }
    case 'weekly':
      return { type: 'weekly', weekdays: [], runTimes: rt ? [rt] : [], effectiveStart: es, effectiveEnd: ee }
    case 'monthly':
      return { type: 'monthly', days: [], lastDays: [], runTimes: rt ? [rt] : [], effectiveStart: es, effectiveEnd: ee }
    case 'cron':
      return { type: 'cron', cron }
  }
}

/** 创建默认的 ScheduleConfig（单次运行）。 */
export function defaultScheduleConfig(): ScheduleConfig {
  return { type: 'once', runTime: '' }
}

/** 内容块类型枚举。 */
export type ContentBlockType = 'text' | 'image' | 'video' | 'file' | 'card' | 'moments'

/** 文本内容块。 */
export interface TextContentBlock {
  type: 'text'
  value: string
}

/** 图片内容块。value 为 blob URL（原型阶段）。 */
export interface ImageContentBlock {
  type: 'image'
  value: string
  name?: string
}

/** 视频内容块。value 为 blob URL（原型阶段）。 */
export interface VideoContentBlock {
  type: 'video'
  value: string
  name?: string
}

/** 文件内容块。value 为 blob URL（原型阶段）。 */
export interface FileContentBlock {
  type: 'file'
  value: string
  name?: string
  size?: number
}

/** 卡片链接内容块。 */
export interface CardContentBlock {
  type: 'card'
  url: string
  title: string
  desc: string
  cover?: string
}

/** 朋友圈任务内容块（存 JSON 字符串）。 */
export interface MomentsContentBlock {
  type: 'moments'
  value: string
}

/** 内容块（判别联合类型）。 */
export type ContentBlock =
  | TextContentBlock
  | ImageContentBlock
  | VideoContentBlock
  | FileContentBlock
  | CardContentBlock
  | MomentsContentBlock

/** 运营任务列表项。 */
export interface OperationTask {
  id: string
  name: string
  task_type: TaskType
  channel_type: string
  session_type: string
  content_blocks: ContentBlock[]
  hosting_action: string
  run_frequency: string
  run_time: string
  effective_start: string
  effective_end: string
  cron_expression: string
  schedule_type?: string
  schedule_config?: string
  run_status: RunStatus
  enabled: boolean
  next_run_time: string
  target_count: number
  created_at: string
  updated_at: string
}

/** 运营任务详情（含 targets）。 */
export interface OperationTaskDetail extends OperationTask {
  targets: OperationTaskTarget[]
}

/** 运营对象。 */
export interface OperationTaskTarget {
  id: string
  task_id: string
  target_type: string // "static" | "dynamic" | "group"
  session_id: string
  group_id?: string
  session_name: string
  account_name: string
  session_type: string
  hosted_status: string
  filter_rules: Record<string, unknown>
}

/** 可选目标会话。 */
export interface TargetSession {
  id: string
  name: string
  account_name: string
  session_type: string
  hosted_status: string
  add_time: string
  selected: boolean
}

/** 创建任务请求体。 */
export interface CreateTaskRequest {
  name: string
  task_type: TaskType
  channel_type: string
  session_type: string
  content_blocks: ContentBlock[]
  hosting_action: string
  run_frequency: string
  run_time: string
  effective_start: string
  effective_end: string
  cron_expression: string
  schedule_type?: string
  schedule_config?: string
  targets: TaskTargetInput[]
}

/** 创建时的运营对象输入。 */
export interface TaskTargetInput {
  session_id?: string
  account_id?: string
  target_type: string // "static" | "dynamic" | "group" | "account"
  group_id?: string
  filter_rules?: Record<string, unknown>
}

/** 渠道账号（用于朋友圈任务选择运营对象）。 */
export interface ChannelAccount {
  id: string
  account_name: string
  channel_type: string
  status: string
  display_name: string
}

// ---- 新增：运营对象选择器 v2 类型 ----

/** 目标会话详情（v2 接口）。 */
export interface TargetSessionDetail {
  id: string
  name: string
  avatar: string
  account_id: string
  account_name: string
  channel_type: string
  session_type: string
  hosted_status: string
  hosted_bot_id: string
  hosted_bot_name: string
  hosting_chain: string
  add_time: string
  customer_nickname: string
  customer_remark: string
  selected: boolean
}

/** 目标会话分页响应。 */
export interface TargetSessionListResponse {
  items: TargetSessionDetail[]
  total: number
  page: number
  page_size: number
  has_more: boolean
}

/** 托管账号选项。 */
export interface HostingAccount {
  id: string
  channel: string
  account_name: string
  display_name: string
}

/** 托管机器人选项。 */
export interface HostingBot {
  id: string
  name: string
  status: string
}

/** 标签项（含分组信息）。 */
export interface TagItem {
  id: string
  group_id: string
  name: string
  color: string
  group_name: string
}

/** 标签分组。 */
export interface TagGroup {
  id: string
  name: string
  is_hot: boolean
}

/** 静态选择筛选条件。 */
export interface StaticFilterState {
  keyword: string
  hostingAccountId: string
  hostingBotId: string
  tagId: string
  tagRelation: 'and' | 'or' | ''
}

/** 动态选择筛选条件。 */
export interface DynamicFilterState {
  hostingAccountId: string
  hostingBotId: string
  tagRelation: 'and' | 'or'
  tagIds: string[]
}

/** 更新任务请求体。 */
export interface UpdateTaskRequest {
  name?: string
  task_type?: string
  channel_type?: string
  session_type?: string
  content_blocks?: ContentBlock[]
  hosting_action?: string
  run_frequency?: string
  run_time?: string
  effective_start?: string
  effective_end?: string
  cron_expression?: string
  schedule_type?: string
  schedule_config?: string
  enabled?: boolean
}

/** 任务类型卡片配置。 */
export const TASK_TYPE_OPTIONS: { value: TaskType; label: string; icon: string; desc: string }[] = [
  { value: '群发任务', label: '群发任务', icon: '➤', desc: '确定时间、确定内容的消息发送，适用于统一的通知消息等场景，如直播预告、活动预告等' },
  { value: '机器人定时任务', label: '机器人定时任务', icon: '◉', desc: '确定时间、不定内容的消息发送，适用于在特定时间为用户发送不同内容的场景，如每日最新消息汇总、每月情况统计等' },
  { value: '朋友圈任务', label: '朋友圈任务', icon: '◎', desc: '通过企微和个微账号，发送固定的朋友圈内容，批量触达客户' },
  { value: '特定节点定时任务', label: '特定节点定时任务', icon: '◆', desc: '不定时间、确定内容的消息发送，适用于在某些时间节点为用户发送特定消息的场景，如每年生日祝福、成交后10天回访等' },
  { value: '特定节点机器人定时任务', label: '特定节点机器人定时任务', icon: '◇', desc: '不定时间、不定内容的消息发送，适用于在某些时间节点为用户发送不同内容的场景，如流失X天后用户召回等' },
]

/** 运行状态标签映射。 */
export const RUN_STATUS_LABELS: Record<RunStatus, string> = {
  '运行中': '运行中',
  '未运行': '未运行',
  '已完成': '已完成',
  '失败': '异常结束',
  '已暂停': '人工停止',
}

/** 托管机器人选项（与 BOT_NAMES 对齐）。 */
export const HOSTING_ACTION_OPTIONS = [
  { value: '保持不变', label: '保持不变' },
  { value: '取消托管', label: '取消托管' },
  { value: 'yefengqiu', label: '野风秋大健康机器人' },
  { value: 'fanfuni', label: '梵芙尼美妆销售机器人' },
]

/** 运行频率选项。 */
export const RUN_FREQUENCY_OPTIONS: { value: RunFrequency; label: string }[] = [
  { value: '一次', label: '单次运行' },
  { value: '每天', label: '每天' },
  { value: '每周', label: '每周' },
  { value: '每月', label: '每月' },
  { value: 'Cron表达式', label: 'Cron表达式' },
]

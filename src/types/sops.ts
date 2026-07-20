/** SOP 类型：customer | group */
export type SopType = 'customer' | 'group'

/** SOP 运行状态 */
export type SopStatus = 'running' | 'stopped'

/** 流程节点类型 */
export type SopNodeType = 'settings' | 'message' | 'attr' | 'robot' | 'runRobot' | 'delay' | 'group-settings'

/** 渠道类型 */
export type ChannelType = '企业微信' | '微信' | '邮件'

/** 筛选类型 */
export type FilterType = 'dynamic' | 'static' | 'group'

/** 触发类型 */
export type TriggerType = 'attribute_change' | 'timed' | 'periodic' | 'special'

/** 内容类型 */
export type ContentType = 'text' | 'image' | 'video' | 'file' | 'card'

/** 动态筛选配置 */
export interface DynamicFilterConfig {
  hostingAccountId: string
  hostingBotId: string
  tagRelation: 'and' | 'or'
  tagIds: string[]
}

/** 静态筛选配置 */
export interface StaticFilterConfig {
  customerIds: string[]
}

/** 分组筛选配置 */
export interface GroupFilterConfig {
  groupId: string
}

/** 属性变化触发配置 */
export interface AttributeChangeConfig {
  conditions: Array<{ field: string; op: string; value: string }>
}

/** 定时触发配置 */
export interface TimedTriggerConfig {
  time: string
}

/** 周期触发配置 */
export interface PeriodicTriggerConfig {
  period: 'daily' | 'weekly' | 'monthly'
  dayOfWeek?: number
  dayOfMonth?: number
  runTime: string
}

/** 特殊场景触发配置 */
export interface SpecialTriggerConfig {
  scene: string
}

/** 节点配置（判别联合） */
export interface SopNodeConfig {
  // settings / group-settings
  channel?: ChannelType
  filterType?: FilterType
  dynamicFilter?: DynamicFilterConfig
  staticFilter?: StaticFilterConfig
  groupFilter?: GroupFilterConfig
  stopWhenNotMatch?: boolean
  triggerType?: TriggerType
  triggerConfig?: Record<string, unknown>
  // message
  contentType?: ContentType
  content?: string
  // attr
  addTagIds?: string[]
  removeTagIds?: string[]
  // robot
  robotId?: string
  // runRobot
  runRobotId?: string
  // delay
  hours?: number
  [key: string]: unknown
}

/** 流程节点 */
export interface SopNode {
  id: string
  type: SopNodeType
  x: number
  y: number
  config: SopNodeConfig
}

/** SOP 列表项 */
export interface SopItem {
  id: string
  name: string
  type: SopType
  channel: string
  enabled: boolean
  status: SopStatus
  trigger_type: string
  trigger_config: Record<string, unknown>
  nodes: SopNode[]
  created_at: string
  updated_at: string
}

/** 创建 SOP 请求 */
export interface SopCreateRequest {
  name: string
  type: SopType
  channel: string
  trigger_type: string
  trigger_config: Record<string, unknown>
  nodes: SopNode[]
}

/** 更新 SOP 请求 */
export interface SopUpdateRequest {
  name?: string
  type?: SopType
  channel?: string
  enabled?: boolean
  status?: SopStatus
  trigger_type?: string
  trigger_config?: Record<string, unknown>
  nodes?: SopNode[]
}

/** 删除响应 */
export interface SopDeleteResponse {
  id: string
  deleted: boolean
}

/** SOP 运行记录 */
export interface SopRecord {
  id: string
  sop_id: string
  run_time: string
  run_status: string
  error_message: string
  created_at: string
}

/** 运行状态标签映射 */
export const RECORD_STATUS_LABELS: Record<string, string> = {
  success: '成功',
  failed: '失败',
  running: '运行中',
}

/** 列表过滤参数 */
export interface SopListParams extends Record<string, string | undefined> {
  search?: string
  type?: string
  enabled?: string
  status?: string
  sortBy?: string
}

/** SOP 类型标签映射 */
export const SOP_TYPE_LABELS: Record<SopType, string> = {
  customer: '客户SOP',
  group: '群聊SOP',
}

/** SOP 状态标签映射 */
export const SOP_STATUS_LABELS: Record<SopStatus, string> = {
  running: '运行中',
  stopped: '未运行',
}

/** 节点类型标签映射 */
export const NODE_TYPE_LABELS: Record<SopNodeType, string> = {
  'settings': '流程设置',
  'group-settings': '群聊流程设置',
  'message': '消息触达',
  'attr': '客户属性修改',
  'robot': '机器人托管',
  'runRobot': '运行机器人',
  'delay': '延迟',
}

/** 非 settings 节点可用的子节点类型 */
export const CHILD_NODE_TYPES: Array<{ type: SopNodeType; icon: string; label: string }> = [
  { type: 'message', icon: '💬', label: '客户触达' },
  { type: 'attr', icon: '🏷️', label: '客户属性修改' },
  { type: 'robot', icon: '🤖', label: '机器人托管' },
  { type: 'runRobot', icon: '▶️', label: '运行机器人' },
  { type: 'delay', icon: '⏱️', label: '延迟' },
]

/** 群聊 SOP 可用的子节点类型 */
export const GROUP_CHILD_NODE_TYPES: Array<{ type: SopNodeType; icon: string; label: string }> = [
  { type: 'message', icon: '💬', label: '群聊触达' },
  { type: 'delay', icon: '⏱️', label: '延迟' },
]

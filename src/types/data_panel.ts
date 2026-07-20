/** 数据面板类型定义。 */

/** 单日指标。 */
export interface DailyMetric {
  date: string
  new_sessions: number
  hosted_sessions: number
  bot_processed_sessions: number
  total_messages: number
  bot_processed_messages: number
  bot_transfers: number
  msg_rate: number
  session_rate: number
  transfer_rate: number
}

/** 聚合总计。 */
export interface MetricsTotal {
  new_sessions: number
  hosted_sessions: number
  bot_processed_sessions: number
  total_messages: number
  bot_processed_messages: number
  bot_transfers: number
  msg_rate: number
  session_rate: number
  transfer_rate: number
}

/** GET /api/data-panel/metrics 响应。 */
export interface DataPanelMetricsResponse {
  total: MetricsTotal
  daily: DailyMetric[]
}

/** 筛选器下拉选项。 */
export interface FilterOption {
  value: string
  label: string
}

/** GET /api/data-panel/filter-options 响应。 */
export interface DataPanelFilterOptionsResponse {
  channels: FilterOption[]
  accounts: FilterOption[]
  bots: FilterOption[]
}

/** 指标卡片 key → 展示标签映射。 */
export const METRIC_LABELS: Record<string, string> = {
  new_sessions: '新增会话数',
  hosted_sessions: '托管会话数',
  bot_processed_sessions: '机器人处理会话数',
  total_messages: '总消息数',
  bot_processed_messages: '机器人处理消息数',
  bot_transfers: '机器人转人工数',
}

/** 比率卡片 key → 展示标签映射。 */
export const RATE_LABELS: Record<string, string> = {
  msg_rate: '机器人消息处理率',
  session_rate: '机器人会话处理率',
  transfer_rate: '机器人转人工率',
}

/** 指标 key 列表（顺序与原型一致）。 */
export const METRIC_KEYS: string[] = [
  'new_sessions',
  'hosted_sessions',
  'bot_processed_sessions',
  'total_messages',
  'bot_processed_messages',
  'bot_transfers',
]

/** 比率 key 列表（顺序与原型一致）。 */
export const RATE_KEYS: string[] = ['msg_rate', 'session_rate', 'transfer_rate']

/** 指标对应的 accent 色号（1-6），与原型 CSS .dp-metric.accent-N 对应。 */
export const METRIC_ACCENT: Record<string, number> = {
  new_sessions: 1,
  hosted_sessions: 2,
  bot_processed_sessions: 3,
  total_messages: 4,
  bot_processed_messages: 5,
  bot_transfers: 6,
}

/** 图表柱状图颜色（与原型 JS 5103-5111 行完全一致）。 */
export const BAR_COLORS: Record<string, string> = {
  new_sessions: '#f5c99b',
  hosted_sessions: '#a8dcc1',
  bot_processed_sessions: '#a8c8e8',
  total_messages: '#f3e6a8',
  bot_processed_messages: '#d3c2e8',
  bot_transfers: '#f0b8b8',
}

/** 图表折线颜色（与原型 JS 5126-5130 行完全一致）。 */
export const LINE_COLORS: Record<string, string> = {
  msg_rate: '#3b82f6',
  session_rate: '#06b6d4',
  transfer_rate: '#ef4444',
}

/** 工具提示中的帮助文本。 */
export const METRIC_HELP: Record<string, string> = {
  new_sessions:
    '选定期间内，新出现在Morphix平台上的会话数，包含单聊、群聊；可能是新增好友的会话，也可能是添加渠道账号前已存在，添加后首次收到新消息的会话。',
  hosted_sessions:
    '选定期间内，曾处于过机器人托管状态的会话数，包含单聊、群聊。请注意，这里包含后来取消托管的会话。',
  bot_processed_sessions:
    '选定期间内，机器人曾处理过其中客户消息的会话数，包含单聊、群聊。请注意，处理指机器人思考过用户发送的消息，可能思考后选择不回复或转人工。',
  total_messages:
    '选定期间内，Morphix平台在各个托管会话中收到的外部消息数；会排除掉系统消息和企微内部联系人发送的消息。',
  bot_processed_messages:
    '选定期间内，机器人曾处理过的客户消息数。请注意，处理指机器人思考过用户发送的消息，可能思考后选择不回复或转人工。',
  bot_transfers: '选定期间内，机器人思考过后，决定转人工的次数。',
}

/** 比率帮助文本。 */
export const RATE_HELP: Record<string, string> = {
  msg_rate: '机器人消息处理率=机器人处理消息数/总消息数',
  session_rate: '机器人会话处理率=机器人处理会话数/有客户消息的托管会话数',
  transfer_rate: '机器人转人工率=机器人转人工数/机器人处理消息数',
}

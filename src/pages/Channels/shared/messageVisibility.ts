/**
 * 消息可见性判定（聊天气泡渲染前的最后一道闸门）。
 *
 * 背景（Bug：聊天框刷出成片「只有时间戳的空蓝气泡」）：
 * iPad 协议会下发一批「控制/回执类事件」（如 2001 = MarkAsRead 已读回执），
 * 它们用于多端同步，**没有任何聊天正文**。后端 `handle_callback` 早期只按
 * `referid != 0` 过滤，而这些事件的 `referid` 恰为 0，于是整批落库成了消息行。
 *
 * 后端已在入库侧根治（`ipad_sync.CONTROL_EVENT_MSG_TYPES` + 无可见内容不落库），
 * 本模块是**前端防御层**：历史脏数据仍留在库里，且协议随时可能冒出新的信令
 * msgType，渲染前统一按「有没有用户可见内容」判断，避免空气泡再次出现。
 */

import type { MessageExtDTO } from '../../../types/channels'

/**
 * 控制/回执类 msgType（与后端 `ipad_sync.CONTROL_EVENT_MSG_TYPES` 保持一致）。
 * - 2001：MarkAsRead 已读回执（手机端已读时下发）；
 * - 2118：多端同步会话状态事件（正文常为 protobuf 裸字节）；
 * - 2131：多端同步事件（线上样本正文全空）。
 */
export const CONTROL_MSG_TYPES: ReadonlySet<number> = new Set([2001, 2118, 2131])

/** C0/C1 控制字符（保留 \t \n \r）：协议偶发下发 protobuf 裸字节。 */
const CONTROL_CHARS_RE = /[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f]/g

/**
 * 清洗协议文本：剔除不可见控制字符，整体空白归一为空串。
 * 与后端 `_clean_text` 同一套规则，保证前后端判定一致。
 */
export function cleanMessageText(content: string | null | undefined): string {
  if (!content) return ''
  return content.replace(CONTROL_CHARS_RE, '').trim()
}

/**
 * 判定一条消息是否「有用户可见内容」，即是否应该渲染成气泡。
 *
 * 判据（任一命中即可见）：
 * 1. 携带媒体 URL（图片/表情/文件等，正文可为空）；
 * 2. 正文清洗后非空。
 *
 * 例外：`CONTROL_MSG_TYPES` 中的信令事件即便带残缺正文也一律不渲染
 * （唯一放行情形是它真的携带了媒体 URL，如线上偶发的动画表情回调）。
 */
export function isVisibleMessage(msg: MessageExtDTO): boolean {
  if (msg.mediaUrl && msg.mediaUrl.trim() !== '') return true
  if (CONTROL_MSG_TYPES.has(msg.msgType ?? 0)) return false
  return cleanMessageText(msg.content) !== ''
}

/** 过滤出可渲染的消息列表（保持原顺序）。 */
export function filterVisibleMessages(messages: MessageExtDTO[]): MessageExtDTO[] {
  return messages.filter(isVisibleMessage)
}

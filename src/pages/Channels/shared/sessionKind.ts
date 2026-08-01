/**
 * 会话实体语义判定（单一事实来源）。
 *
 * 背景：会话列表、右侧头部、聊天面板三处都需要判断「是否应用/小程序会话」。
 * 早期各自实现了一份，判定条件出现漂移（列表只看 entityKind，另两处还看
 * readonly / sessionType），后续一旦后端语义扩展就会出现「列表不显示徽标、
 * 但输入框被禁用」这类不一致。故统一收敛到本模块。
 *
 * 判定原则：
 * 1. **只消费后端下发的语义字段**（entityKind / readonly），
 *    组件内禁止出现 `msgType === 3` 之类的魔法数字；
 * 2. `sessionType === '应用'` 仅作为**旧版后端**的兼容兜底
 *    （新后端一定会下发 entityKind / readonly）。
 */
import type { SessionDTO } from '../../../types/channels'

/**
 * 判断会话是否为「应用 / 小程序」通知类实体。
 *
 * @param session 会话 DTO，允许为空（未选中会话时返回 false）。
 * @returns 是应用类实体返回 true。
 */
export function isAppSession(session: SessionDTO | null | undefined): boolean {
  if (!session) return false
  // `entityKind` 一旦下发就是**权威判定**，直接短路，不再看 readonly / sessionType。
  // 否则 `readonly === true` 这条兜底会反过来压过明确的 'person' / 'group' 语义：
  // 后端不变式是 readonly ⟺ msg_type ∈ {3,103,107} ⟺ entityKind === 'app'，
  // 真出现「readonly=true 且 entityKind='person'」只可能是数据被污染（参见
  // list_sessions 空串 JOIN 冒名缺陷），此时应信任 entityKind 而非把真人会话
  // 判成应用、连输入框一起禁掉。
  if (session.entityKind) return session.entityKind === 'app'
  // 旧版后端不下发 entityKind：退回 readonly / sessionType 兜底，行为保持不变。
  return session.readonly === true || session.sessionType === '应用'
}

/**
 * 应用会话的类型徽标文案。
 *
 * `appType === 2` 为小程序，其余（含缺省 / 未知）统一显示「应用」。
 *
 * @param session 会话 DTO，允许为空。
 * @returns 徽标文案，'小程序' 或 '应用'。
 */
export function appBadgeText(session: SessionDTO | null | undefined): string {
  return session?.appType === 2 ? '小程序' : '应用'
}

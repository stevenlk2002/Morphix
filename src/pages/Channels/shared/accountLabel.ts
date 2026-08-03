import type { AccountDTO } from '../../../types/channels'

/**
 * 账号展示名：账号名@团队名（如「竹绿-健康@医林通」）。
 *
 * 规则：
 * - 同时拥有 name 与 teamName 时返回 `{name}@{teamName}`
 * - 仅有 name（无 teamName）时仅返回 name
 * - 无 name，或未传入账号（null/undefined）时返回占位符 '—'
 *
 * 统一在渠道会话管理各面板（联系人/群列表、详情抽屉、群管理、单聊详情）
 * 复用此函数，避免各处自行拼接导致格式不一致。
 */
export function accountLabel(account?: AccountDTO | null): string {
  if (!account || !account.name) return '—'
  return account.teamName ? `${account.name}@${account.teamName}` : account.name
}

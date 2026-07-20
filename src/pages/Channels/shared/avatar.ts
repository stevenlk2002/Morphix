/** 头像取色 / 取字共享工具（SES / CON / ACC 复用）。 */

export const AVATAR_COLORS = [
  '#4A90D9',
  '#7fb069',
  '#e8a649',
  '#8b5cf6',
  '#14b8a6',
  '#ef4444',
  '#2f6df6',
  '#ec4899',
]

/** 依据 id 生成稳定的头像背景色。 */
export function avatarColor(seed: string): string {
  let h = 0
  for (let i = 0; i < seed.length; i++) h = (h * 31 + seed.charCodeAt(i)) >>> 0
  return AVATAR_COLORS[h % AVATAR_COLORS.length]
}

/** 取展示用首字（中文取首字，英文取首字母大写）。 */
export function avatarChar(name: string): string {
  const trimmed = (name || '?').trim()
  if (!trimmed) return '?'
  const ch = trimmed[0]
  return /[a-zA-Z]/.test(ch) ? ch.toUpperCase() : ch
}

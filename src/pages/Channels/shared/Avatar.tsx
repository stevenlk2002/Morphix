/** 统一头像组件：优先展示真实头像 URL，加载失败或无 URL 时降级为字母色块。 */

import * as React from 'react'
import { avatarColor, avatarChar } from './avatarUtils'

interface AvatarProps {
  /** 真实头像 URL（企微头像等）。空值则降级为字母色块。 */
  url?: string | null
  /** 展示名称，用于字母色块取字与 alt。 */
  name?: string
  /** 取色种子（通常用 id），保证同对象颜色稳定。 */
  id?: string
  className?: string
  /** 圆形直径（px）。 */
  size?: number
  style?: React.CSSProperties
}

/**
 * 自包含圆形头像：有 URL 时渲染 <img>，否则渲染带背景色的字母块。
 * 外层容器可直接使用现有 class（如 session-account-avatar / session-row-avatar /
 * avatar-sm / group-member-avatar），组件仅负责内容层。
 */
export default function Avatar({ url, name = '', id = '', className = '', size = 32, style }: AvatarProps) {
  const src = (url || '').trim()
  const displayName = (name || '?').trim()
  const bg = avatarColor(id || name || '?')
  const baseStyle: React.CSSProperties = {
    width: size,
    height: size,
    borderRadius: '50%',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    color: '#fff',
    fontWeight: 600,
    overflow: 'hidden',
    flexShrink: 0,
    ...style,
  }

  if (src) {
    return (
      <div className={`avatar-img-wrap${className ? ' ' + className : ''}`} style={baseStyle}>
        <img
          src={src}
          alt={displayName}
          style={{ width: '100%', height: '100%', objectFit: 'cover' }}
          onError={(e) => {
            // 加载失败时降级：移除 img，让背景字母块透出
            e.currentTarget.style.display = 'none'
          }}
        />
      </div>
    )
  }

  return (
    <div className={`avatar-letter${className ? ' ' + className : ''}`} style={{ ...baseStyle, background: bg }}>
      {avatarChar(displayName)}
    </div>
  )
}

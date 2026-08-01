/** 统一头像组件：优先展示真实头像 URL，加载失败或无 URL 时降级为字母色块。 */

import * as React from 'react'
import { avatarColor, avatarChar } from './avatarUtils'

/** 头像形状：`circle` 人/群（默认）、`rounded` 应用（圆角矩形 8px）。 */
export type AvatarShape = 'circle' | 'rounded'

/** 应用类头像圆角半径（px）。与 `.avatar-rounded` 保持一致。 */
const ROUNDED_RADIUS = 8

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
  /**
   * 形状。`circle`（默认）保持现状；`rounded` 为应用类会话的圆角矩形，
   * 由后端 `entityKind === 'app'` 驱动，**首字兜底色块同步应用该形状**。
   */
  shape?: AvatarShape
  style?: React.CSSProperties
}

/**
 * 自包含头像：有 URL 时渲染 <img>，否则渲染带背景色的字母块。
 * 外层容器可直接使用现有 class（如 session-account-avatar / session-row-avatar /
 * avatar-sm / group-member-avatar），组件仅负责内容层。
 *
 * 形状由 `shape` 控制：`circle` 圆形（人 / 群 / 开放平台），
 * `rounded` 圆角矩形（企业应用，见 wecom_app_display §8.6）。
 * 圆角需在 `<img>` 容器与首字兜底块**两处**同时生效，否则应用无图标时
 * 仍会显示成圆形，导致「会话列表 / 标题栏 / 消息气泡」三处形状不一致。
 */
export default function Avatar({
  url,
  name = '',
  id = '',
  className = '',
  size = 32,
  shape = 'circle',
  style,
}: AvatarProps) {
  const src = (url || '').trim()
  const displayName = (name || '?').trim()
  const bg = avatarColor(id || name || '?')
  const shapeClass = shape === 'rounded' ? ' avatar-rounded' : ''
  const baseStyle: React.CSSProperties = {
    width: size,
    height: size,
    borderRadius: shape === 'rounded' ? ROUNDED_RADIUS : '50%',
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
      <div className={`avatar-img-wrap${shapeClass}${className ? ' ' + className : ''}`} style={baseStyle}>
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
    <div
      className={`avatar-letter${shapeClass}${className ? ' ' + className : ''}`}
      style={{ ...baseStyle, background: bg }}
    >
      {avatarChar(displayName)}
    </div>
  )
}

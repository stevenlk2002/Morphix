import { useCallback, useEffect, useState } from 'react'
import type { MouseEvent as ReactMouseEvent } from 'react'

const STORAGE_KEY = 'morphix.sessionLeftWidth'
const MIN_WIDTH = 160
const MAX_WIDTH = 300
const DEFAULT_WIDTH = 200

/** 将宽度 clamp 到 [180, 360]，非法值回落默认。 */
function clampWidth(width: number): number {
  if (!Number.isFinite(width)) return DEFAULT_WIDTH
  return Math.min(MAX_WIDTH, Math.max(MIN_WIDTH, width))
}

/**
 * 左中栏拖拽宽度状态（R2-P0 / Q5）。
 *
 * - `.session-mgmt` 首列宽度由 CSS 变量 `--session-left-width` 驱动；
 * - 拖拽时 clamp(180,360) 并实时写入 CSS 变量；
 * - 松手时持久化到 localStorage（key `morphix.sessionLeftWidth`）；
 * - 挂载时从 localStorage 读取初始值。
 */
export function useResizablePanels(): {
  leftWidth: number
  startResize: (e: ReactMouseEvent) => void
} {
  const [leftWidth, setLeftWidth] = useState<number>(() => {
    if (typeof localStorage === 'undefined') return DEFAULT_WIDTH
    const stored = localStorage.getItem(STORAGE_KEY)
    return clampWidth(stored ? parseInt(stored, 10) : NaN)
  })

  // 将当前宽度同步到 CSS 变量，驱动 .session-mgmt 网格首列。
  useEffect(() => {
    document.documentElement.style.setProperty(
      '--session-left-width',
      `${leftWidth}px`
    )
  }, [leftWidth])

  const startResize = useCallback(
    (e: ReactMouseEvent) => {
      e.preventDefault()
      const startX = e.clientX
      const startWidth = leftWidth
      let latest = startWidth

      const onMouseMove = (ev: globalThis.MouseEvent) => {
        latest = clampWidth(startWidth + (ev.clientX - startX))
        setLeftWidth(latest)
        document.documentElement.style.setProperty(
          '--session-left-width',
          `${latest}px`
        )
      }
      const onMouseUp = () => {
        window.removeEventListener('mousemove', onMouseMove)
        window.removeEventListener('mouseup', onMouseUp)
        try {
          localStorage.setItem(STORAGE_KEY, String(latest))
        } catch {
          /* 兼容隐私模式 / 禁用存储的场景 */
        }
      }

      window.addEventListener('mousemove', onMouseMove)
      window.addEventListener('mouseup', onMouseUp)
    },
    [leftWidth]
  )

  return { leftWidth, startResize }
}

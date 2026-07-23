import { useCallback } from 'react'
import type { MouseEvent as ReactMouseEvent } from 'react'

interface ResizerProps {
  /** 鼠标按下时由父级接管拖拽逻辑（监听 window mousemove/mouseup）。 */
  onResizeStart: (e: ReactMouseEvent) => void
}

/** 左中栏可拖拽分隔条（grid 第 2 track，宽 6px）。 */
export default function Resizer({ onResizeStart }: ResizerProps) {
  const handleMouseDown = useCallback(
    (e: ReactMouseEvent) => {
      onResizeStart(e)
    },
    [onResizeStart]
  )

  return (
    <div
      className="session-resizer"
      onMouseDown={handleMouseDown}
      role="separator"
      aria-orientation="vertical"
      aria-label="拖拽调整左栏宽度"
    />
  )
}

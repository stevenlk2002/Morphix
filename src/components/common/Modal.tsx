import { useEffect, type ReactNode } from 'react'
import './Modal.css'

interface ModalProps {
  /** 是否显示弹窗。 */
  open: boolean
  /** 弹窗标题。 */
  title: string
  /** 关闭回调（点击遮罩 / 关闭按钮 / Esc）。 */
  onClose: () => void
  /** 弹窗主体内容。 */
  children: ReactNode
  /** 底部操作区（如取消 / 保存按钮）。 */
  footer?: ReactNode
  /** 弹窗宽度（px），默认 480。 */
  width?: number
}

/**
 * 通用模态弹窗。
 * - 点击遮罩或 Esc 关闭。
 * - 打开时锁定 body 滚动。
 * - 多处页面（标签管理 / 运营SOP）复用，避免重复实现遮罩与样式。
 */
export default function Modal({ open, title, onClose, children, footer, width = 480 }: ModalProps) {
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onKey)
    document.body.style.overflow = 'hidden'
    return () => {
      document.removeEventListener('keydown', onKey)
      document.body.style.overflow = ''
    }
  }, [open, onClose])

  if (!open) return null

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div
        className="modal"
        style={{ width }}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="modal-header">
          <h3 className="modal-title">{title}</h3>
          <button className="modal-close" type="button" onClick={onClose} aria-label="关闭">
            ×
          </button>
        </div>
        <div className="modal-body">{children}</div>
        {footer && <div className="modal-footer">{footer}</div>}
      </div>
    </div>
  )
}

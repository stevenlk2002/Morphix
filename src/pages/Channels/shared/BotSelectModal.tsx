/** 默认机器人选择器弹层（数据源=已上线机器人，「未设置」可清空）。 */

import { useEffect } from 'react'
import { X } from 'lucide-react'
import type { AvailableBotDTO } from '../../../types/channels'
import { avatarColor, avatarChar } from './avatar'

interface BotSelectModalProps {
  /** 是否打开。 */
  open: boolean
  /** 弹层标题（如「默认单聊机器人」）。 */
  title: string
  /** 当前已选机器人 id（空串/undefined 表示未设置）。 */
  currentBotId?: string | null
  /** 可选机器人列表（已上线）。 */
  bots: AvailableBotDTO[]
  /** 关闭弹层。 */
  onClose: () => void
  /** 选中某个机器人；传 null 表示清空（未设置）。 */
  onSelect: (botId: string | null) => void
}

/**
 * 账号卡片「默认机器人」选择器。
 * - 顶部「未设置」项用于清空当前默认机器人；
 * - 列表项展示机器人首字母头像 + 名称，当前选中项高亮；
 * - 支持 ESC / 点击遮罩关闭。
 */
export default function BotSelectModal({
  open,
  title,
  currentBotId,
  bots,
  onClose,
  onSelect,
}: BotSelectModalProps) {
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onClose])

  if (!open) return null

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div
        className="modal-panel bot-select-modal"
        role="dialog"
        aria-modal="true"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="modal-header">
          <h3>{title}</h3>
          <button className="modal-close" onClick={onClose} aria-label="关闭">
            <X size={18} />
          </button>
        </div>
        <div className="modal-body">
          <button
            type="button"
            className={`bot-select-option${!currentBotId ? ' active' : ''}`}
            onClick={() => onSelect(null)}
          >
            <span className="bot-select-initial bot-select-clear">∅</span>
            <span className="bot-select-name">未设置</span>
          </button>

          {bots.map((b) => (
            <button
              type="button"
              key={b.id}
              className={`bot-select-option${currentBotId === b.id ? ' active' : ''}`}
              onClick={() => onSelect(b.id)}
            >
              <span
                className="bot-select-initial"
                style={{ background: avatarColor(b.id) }}
              >
                {avatarChar(b.name)}
              </span>
              <span className="bot-select-name">{b.name}</span>
            </button>
          ))}

          {bots.length === 0 && (
            <div className="bot-select-empty">暂无可用的在线机器人</div>
          )}
        </div>
      </div>
    </div>
  )
}

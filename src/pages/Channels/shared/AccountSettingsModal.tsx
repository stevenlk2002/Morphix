/** 账号设置弹层：默认单聊/群聊托管机器人 + 上线/下线切换。 */

import { useEffect, useState } from 'react'
import { ArrowLeft } from 'lucide-react'
import type {
  AccountDTO,
  AvailableBotDTO,
  SetDefaultBotsRequest,
} from '../../../types/channels'
import Button from '../../../components/common/Button'

interface AccountSettingsModalProps {
  /** 是否打开。 */
  open: boolean
  /** 当前编辑的账号（含默认机器人 + 状态）。 */
  account: AccountDTO | null
  /** 可选机器人列表（已上线）。 */
  bots: AvailableBotDTO[]
  /** 关闭弹层。 */
  onClose: () => void
  /** 保存默认机器人（仅「确认」时触发）。 */
  onSave: (payload: SetDefaultBotsRequest) => Promise<void> | void
  /** 切换上下线（立即触发）。 */
  onStatusChange: (status: 'online' | 'offline') => Promise<void> | void
}

/** 问号 tooltip 文案（单聊/群聊一致）。 */
const STATUS_TOOLTIP = '只针对新增客户生效，老客户请前往托管管理开启托管'

/**
 * 账号设置弹层。
 * - 顶部返回箭头 + 「设置：{账号名}」；
 * - 两个下拉分别配置默认单聊/群聊托管机器人（「未设置」+ 在线机器人）；
 * - 下方文字按钮切换上下线（二次确认后即时生效）；
 * - 底部居右「确认」按钮，仅在此处回写默认机器人配置。
 */
export default function AccountSettingsModal({
  open,
  account,
  bots,
  onClose,
  onSave,
  onStatusChange,
}: AccountSettingsModalProps) {
  const [singleBotId, setSingleBotId] = useState<string>('')
  const [groupBotId, setGroupBotId] = useState<string>('')
  const [saving, setSaving] = useState(false)

  // 每次打开弹层时，用账号当前默认值同步表单。
  useEffect(() => {
    if (open && account) {
      setSingleBotId(account.defaultSingleBotId || '')
      setGroupBotId(account.defaultGroupBotId || '')
    }
    // 仅在「打开」或「切换账号」时重置，避免父级刷新时覆盖用户已选值
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, account?.id])

  if (!open || !account) return null

  const isOnline = account.status === 'online'

  /** 「确认」：仅回写默认机器人配置，由父级负责关闭弹层。 */
  const handleSave = async () => {
    setSaving(true)
    try {
      await onSave({ singleBotId, groupBotId })
    } finally {
      setSaving(false)
    }
  }

  /** 上下线切换：二次确认后即时生效（不关闭弹层）。 */
  const handleToggleStatus = () => {
    const next: 'online' | 'offline' = isOnline ? 'offline' : 'online'
    const confirmMsg = isOnline ? '确认下线该账号？' : '确认上线该账号？'
    if (window.confirm(confirmMsg)) {
      onStatusChange(next)
    }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div
        className="modal-panel account-settings-modal"
        role="dialog"
        aria-modal="true"
        onClick={(e) => e.stopPropagation()}
      >
        {/* 标题区：返回箭头 + 账号名 */}
        <div className="account-settings-header">
          <button
            type="button"
            className="account-settings-back"
            onClick={onClose}
            aria-label="返回"
          >
            <ArrowLeft size={18} />
          </button>
          <h3 className="account-settings-title">设置：{account.name}</h3>
        </div>

        {/* 表单区 */}
        <div className="account-settings-body">
          <div className="account-settings-field">
            <label className="account-settings-label">
              <span className="account-settings-required">*</span>
              <span>默认单聊托管机器人</span>
              <span className="account-settings-tooltip">
                ?
                <span className="account-settings-tooltip-pop">{STATUS_TOOLTIP}</span>
              </span>
            </label>
            <select
              className="account-settings-select"
              value={singleBotId}
              onChange={(e) => setSingleBotId(e.target.value)}
            >
              <option value="">未设置</option>
              {bots.map((b) => (
                <option key={b.id} value={b.id}>
                  {b.name}
                </option>
              ))}
            </select>
          </div>

          <div className="account-settings-field">
            <label className="account-settings-label">
              <span className="account-settings-required">*</span>
              <span>默认群聊托管机器人</span>
              <span className="account-settings-tooltip">
                ?
                <span className="account-settings-tooltip-pop">{STATUS_TOOLTIP}</span>
              </span>
            </label>
            <select
              className="account-settings-select"
              value={groupBotId}
              onChange={(e) => setGroupBotId(e.target.value)}
            >
              <option value="">未设置</option>
              {bots.map((b) => (
                <option key={b.id} value={b.id}>
                  {b.name}
                </option>
              ))}
            </select>
          </div>

          {/* 上下线切换（文字按钮） */}
          <div className="account-settings-toggle">
            {isOnline ? (
              <button
                type="button"
                className="account-settings-toggle-btn offline"
                onClick={handleToggleStatus}
              >
                下线账号
              </button>
            ) : (
              <button
                type="button"
                className="account-settings-toggle-btn online"
                onClick={handleToggleStatus}
              >
                上线账号
              </button>
            )}
          </div>
        </div>

        {/* 底部居右「确认」 */}
        <div className="account-settings-footer">
          <Button variant="primary" onClick={handleSave} disabled={saving}>
            {saving ? '保存中…' : '确认'}
          </Button>
        </div>
      </div>
    </div>
  )
}

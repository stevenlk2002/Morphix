/** 合并区域头部（R-P0 / 客户图 1+2）：名字/标签/机器人托管/机器人选择/清空上下文/托管管理/账号头像。 */

import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ChevronDown, Settings2, Eraser } from 'lucide-react'
import type { AccountDTO, HostingBotDTO, SessionDTO } from '../../../types/channels'
import { channelsApi } from '../../../api/client'
import { avatarColor } from '../shared/avatar'
import { toast, errText } from '../../../utils/toast'

interface RightPanelHeaderProps {
  session: SessionDTO | null
  bots: HostingBotDTO[]
  account: AccountDTO | null
  /** 托管/机器人变更回传。 */
  onHostingChange: (next: SessionDTO) => void
  /** 清空本地消息历史（前端态）回调。 */
  onClearContext?: () => void
}

function badgeForChannel(channel: string): string {
  if (!channel) return ''
  if (channel.includes('微信')) return '@微信'
  if (channel.includes('WhatsApp')) return '@WhatsApp'
  return channel
}

function isGroupSession(session: SessionDTO | null): boolean {
  if (!session) return false
  if (session.sessionType === '群聊') return true
  // 兜底：msg_type=1 为群
  return false
}

export default function RightPanelHeader({
  session,
  bots,
  account,
  onHostingChange,
  onClearContext,
}: RightPanelHeaderProps) {
  const navigate = useNavigate()
  const [botOpen, setBotOpen] = useState(false)
  const [busy, setBusy] = useState(false)

  const hosted = session?.hostedStatus === 'hosted'
  const isGroup = isGroupSession(session)
  const name = session?.name ?? '未选择会话'
  const botName =
    bots.find((b) => b.id === session?.hostedBotId)?.name ?? '请选择客...'
  const tag = isGroup
    ? '客户群'
    : badgeForChannel(session?.channel ?? account?.channel ?? '')

  const toggleHosting = async (checked: boolean) => {
    if (!session) return
    setBusy(true)
    try {
      const next = await channelsApi.setSessionHosting(session.id, {
        hosted: checked,
        botId: checked ? session.hostedBotId || undefined : null,
      })
      onHostingChange(next)
    } catch (e) {
      toast(`托管切换失败：${errText(e)}`)
    } finally {
      setBusy(false)
    }
  }

  const selectBot = async (botId: string) => {
    if (!session) return
    setBotOpen(false)
    try {
      const next = await channelsApi.setSessionHosting(session.id, {
        hosted: hosted,
        botId,
      })
      onHostingChange(next)
    } catch (e) {
      toast(`选择机器人失败：${errText(e)}`)
    }
  }

  const goHosting = () => {
    if (!account) return
    navigate(`/channels/accounts/${account.id}/hosting`)
  }

  const accountInitial = (account?.name ?? '?').charAt(0)
  const accountBg = avatarColor(account?.id ?? account?.name ?? 'X')
  const online = account?.status === 'online'

  return (
    <div className="right-panel-header">
      <div className="right-panel-header-left">
        <span className="right-panel-name" title={name}>
          {name}
        </span>
        {tag && <span className="right-panel-tag">{tag}</span>}
        {isGroup && session && (
          <span className="right-panel-sub">群主：{name.split(/[、,，\s]/)[0]}</span>
        )}
      </div>

      <div className="right-panel-header-center">
        <span className="right-panel-hosting-label">机器人托管</span>
        <label className="switch">
          <input
            type="checkbox"
            checked={hosted}
            disabled={!session || busy}
            onChange={(e) => toggleHosting(e.target.checked)}
          />
          <span className="slider" />
        </label>

        <div className="import-select right-panel-bot-select">
          <div
            className="import-select-trigger right-panel-bot-trigger"
            onClick={() => session && setBotOpen((v) => !v)}
          >
            <span style={{ color: hosted ? 'var(--muted)' : 'var(--ink)' }}>
              {botName}
            </span>
            <ChevronDown size={14} />
          </div>
          {botOpen && (
            <div className="import-select-dropdown" onClick={(e) => e.stopPropagation()}>
              {bots.length === 0 ? (
                <div className="import-select-option" style={{ color: 'var(--muted)' }}>
                  暂无机器人
                </div>
              ) : (
                bots.map((b) => (
                  <div
                    key={b.id}
                    className={`import-select-option${b.id === session?.hostedBotId ? ' active' : ''}`}
                    onClick={() => selectBot(b.id)}
                  >
                    {b.name}
                  </div>
                ))
              )}
            </div>
          )}
        </div>

        <button
          className="right-panel-icon-btn"
          title="清空历史上下文"
          onClick={() => {
            onClearContext?.()
            toast('已清空本地上下文')
          }}
        >
          <Eraser size={14} />
        </button>
      </div>

      <div className="right-panel-header-right">
        <button className="right-panel-icon-btn" onClick={goHosting} title="托管管理">
          <Settings2 size={14} />
          <span>托管管理</span>
        </button>
        <div className="right-panel-account" title={account?.name ?? ''}>
          {account?.avatar ? (
            <img src={account.avatar} alt={account.name} className="right-panel-account-avatar" />
          ) : (
            <div
              className="right-panel-account-avatar"
              style={{ background: accountBg, color: '#fff', display: 'grid', placeItems: 'center' }}
            >
              {accountInitial}
            </div>
          )}
          <span className={`right-panel-account-dot ${online ? 'online' : 'offline'}`} />
        </div>
      </div>
    </div>
  )
}

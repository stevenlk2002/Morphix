/** 会话聊天面板（SES 右一栏）：托管开关 + 机器人选择 + 消息气泡 + 输入区。 */

import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Smile, Image as ImageIcon, FileText, Folder, Send, Bot } from 'lucide-react'
import type { HostingBotDTO, MessageDTO, SessionDTO } from '../../../types/channels'
import { channelsApi } from '../../../api/client'
import { toast, errText } from '../../../utils/toast'

interface SessionChatPanelProps {
  session: SessionDTO | null
  messages: MessageDTO[]
  bots: HostingBotDTO[]
  accountId: string
  /** 折叠/展开客户详情。 */
  onToggleDetail: () => void
  /** 托管状态变更后回传父级。 */
  onHostingChange: (next: SessionDTO) => void
}

export default function SessionChatPanel({
  session,
  messages,
  bots,
  accountId,
  onToggleDetail,
  onHostingChange,
}: SessionChatPanelProps) {
  const navigate = useNavigate()
  const [botId, setBotId] = useState<string>('')
  const [draft, setDraft] = useState('')
  const [busy, setBusy] = useState(false)

  const hosted = session?.hostedStatus === 'hosted'
  const botName = useMemo(
    () => bots.find((b) => b.id === (session?.hostedBotId ?? botId))?.name ?? '请选择机器人',
    [bots, session, botId]
  )

  if (!session) {
    return (
      <section className="session-chat">
        <div className="placeholder">
          <h3>选择一个会话</h3>
          <p>从中间列表选择会话以查看聊天记录</p>
        </div>
      </section>
    )
  }

  const toggleHosting = async (checked: boolean) => {
    setBusy(true)
    try {
      const next = await channelsApi.setSessionHosting(session.id, {
        hosted: checked,
        botId: checked ? (botId || session.hostedBotId || undefined) : null,
      })
      onHostingChange(next)
      toast(checked ? '已开启机器人托管' : '已关闭机器人托管')
    } catch (e) {
      toast(`操作失败：${errText(e)}`)
    } finally {
      setBusy(false)
    }
  }

  const handleSend = () => {
    if (!draft.trim()) return
    toast('手动回复为 P2 能力，当前为演示态')
    setDraft('')
  }

  return (
    <section className="session-chat">
      <div className="chat-header">
        <div className="chat-header-left">
          <span className="chat-title">{session.name}</span>
          <span className="chat-channel">{session.channel}</span>
        </div>
        <div className="chat-header-right">
          <span className="chat-header-label">机器人托管</span>
          <label className="switch">
            <input
              type="checkbox"
              checked={hosted}
              disabled={busy}
              onChange={(e) => toggleHosting(e.target.checked)}
            />
            <span className="slider" />
          </label>
          <div className="import-select">
            <div
              className="import-select-trigger"
              onClick={(e) => {
                const dd = e.currentTarget.nextElementSibling as HTMLElement
                dd.style.display = dd.style.display === 'block' ? 'none' : 'block'
              }}
            >
              {botName}
            </div>
            <div className="import-select-dropdown" style={{ display: 'none' }}>
              {bots.map((b) => (
                <div
                  key={b.id}
                  className={`import-select-option${b.id === (session.hostedBotId ?? botId) ? ' active' : ''}`}
                  onClick={(e) => {
                    setBotId(b.id)
                    ;(e.currentTarget.parentElement as HTMLElement).style.display = 'none'
                    ;(e.currentTarget.parentElement?.previousElementSibling as HTMLElement).textContent = b.name
                  }}
                >
                  {b.name}
                </div>
              ))}
            </div>
          </div>
          <button className="btn btn-ghost btn-sm" onClick={() => navigate(`/channels/accounts/${accountId}/hosting`)}>
            托管管理
          </button>
          <button className="btn btn-ghost btn-sm" onClick={onToggleDetail}>
            客户详情
          </button>
        </div>
      </div>

      <div className="chat-messages">
        {messages.length === 0 && (
          <div className="message user">
            <div className="message-meta">（暂无聊天记录）</div>
          </div>
        )}
        {messages.map((m) => (
          <div key={m.id} className={`message ${m.senderType === 'bot' ? 'bot' : 'user'}`}>
            <div className="message-meta">
              {m.content}
              <span style={{ color: 'var(--text-tertiary)', marginLeft: 8, fontSize: 11 }}>
                {m.createdAt.slice(11, 16)}
              </span>
            </div>
          </div>
        ))}
      </div>

      <div className={`chat-input-wrap${hosted ? ' hosting' : ''}`}>
        <div className="chat-toolbar">
          <button className="btn-icon" title="表情">
            <Smile size={16} />
          </button>
          <button className="btn-icon" title="图片">
            <ImageIcon size={16} />
          </button>
          <button className="btn-icon" title="文件">
            <FileText size={16} />
          </button>
          <button className="btn-icon" title="文件夹">
            <Folder size={16} />
          </button>
        </div>
        <div className="chat-input-box">
          <input
            className="chat-input"
            placeholder={hosted ? '已开启机器人托管' : '“Enter”发送或点击右边按钮发送'}
            value={draft}
            disabled={hosted}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') handleSend()
            }}
          />
          <button className="btn btn-primary" disabled={hosted} onClick={handleSend}>
            <Send size={16} />
          </button>
        </div>
        {hosted && (
          <div className="chat-hosting-mask">
            <Bot size={13} style={{ verticalAlign: '-2px', marginRight: 4 }} />
            已开启机器人托管，请关闭托管后再手动回复
          </div>
        )}
      </div>
    </section>
  )
}

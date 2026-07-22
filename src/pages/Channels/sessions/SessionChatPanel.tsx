/** 会话聊天面板（SES 右一栏）：托管开关 + 机器人选择 + 消息气泡 + 输入区。 */

import { useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Smile, Image as ImageIcon, FileText, Folder, Send, Bot } from 'lucide-react'
import type { HostingBotDTO, MessageExtDTO, SessionDTO } from '../../../types/channels'
import { channelsApi } from '../../../api/client'
import { toast, errText } from '../../../utils/toast'

interface SessionChatPanelProps {
  session: SessionDTO | null
  messages: MessageExtDTO[]
  bots: HostingBotDTO[]
  accountId: string
  /** 折叠/展开客户详情。 */
  onToggleDetail: () => void
  /** 托管状态变更后回传父级。 */
  onHostingChange: (next: SessionDTO) => void
  /** 本地发送成功后乐观追加消息（消息历史回填为 P2，先本地呈现）。 */
  onMessageSent?: (msg: MessageExtDTO) => void
}

export default function SessionChatPanel({
  session,
  messages,
  bots,
  accountId,
  onToggleDetail,
  onHostingChange,
  onMessageSent,
}: SessionChatPanelProps) {
  const navigate = useNavigate()
  const [botId, setBotId] = useState<string>('')
  const [draft, setDraft] = useState('')
  const [busy, setBusy] = useState(false)
  const [sending, setSending] = useState(false)
  const imageInputRef = useRef<HTMLInputElement | null>(null)
  const fileInputRef = useRef<HTMLInputElement | null>(null)

  const hosted = session?.hostedStatus === 'hosted'
  // 应用类会话（msg_type==3）后端禁发，前端禁用输入并提示（决策 #6）。
  const isAppSession = session?.sessionType === '应用'
  const inputDisabled = hosted || isAppSession
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

  // ---- P2-3 富媒体发送（后端代理 CDN 上传） ----
  const pickFile = (mediaType: 'image' | 'file') => {
    const input = mediaType === 'image' ? imageInputRef.current : fileInputRef.current
    input?.click()
  }

  const handleFileChange = async (
    e: React.ChangeEvent<HTMLInputElement>,
    mediaType: 'image' | 'file'
  ) => {
    const file = e.target.files?.[0]
    e.target.value = '' // 允许重复选择同一文件
    if (!file) return
    if (!accountId || !session) {
      toast('该会话未关联渠道账号，无法发送')
      return
    }
    if (inputDisabled) {
      toast('应用类会话或托管中，暂不支持发送')
      return
    }
    setSending(true)
    try {
      const res = await channelsApi.sendMediaMessage(
        accountId,
        'session',
        session.id,
        mediaType,
        file
      )
      onMessageSent?.({
        id: `local-${Date.now()}`,
        conversationId: session.id,
        senderType: 'user',
        content: file.name,
        createdAt: new Date().toISOString(),
        serverId: res.serverId,
        msgType: mediaType === 'image' ? 1 : 2,
        senderId: '',
        direction: 'outbound',
        contentType: mediaType,
        mediaUrl: res.mediaUrl,
        mediaMeta: null,
        isRead: true,
        channelAccountId: accountId,
      })
      toast('已发送')
    } catch (e) {
      toast(`发送失败：${errText(e)}`)
    } finally {
      setSending(false)
    }
  }

  const handleSend = async () => {
    const text = draft.trim()
    if (!text) return
    if (!accountId) {
      toast('该会话未关联渠道账号，无法发送')
      return
    }
    setSending(true)
    try {
      // 后端按 targetType=session 反查 user_id / room_id + isRoom（决策 #6）。
      await channelsApi.sendTextMessage(accountId, 'session', session.id, text)
      // 乐观追加本地消息（消息历史回填为 P2，先本地呈现）。
      onMessageSent?.({
        id: `local-${Date.now()}`,
        conversationId: session.id,
        senderType: 'user',
        content: text,
        createdAt: new Date().toISOString(),
        serverId: '',
        msgType: 0,
        senderId: '',
        direction: 'outbound',
        contentType: 'text',
        mediaUrl: '',
        mediaMeta: null,
        isRead: true,
        channelAccountId: accountId,
      })
      setDraft('')
    } catch (e) {
      toast(`发送失败：${errText(e)}`)
    } finally {
      setSending(false)
    }
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
        {messages.map((m) => {
          const isBot = m.senderType === 'bot'
          return (
            <div key={m.id} className={`message ${isBot ? 'bot' : 'user'}`}>
              <div className="message-meta">
                {m.contentType === 'image' ? (
                  <img
                    src={m.mediaUrl}
                    alt={m.content || '图片'}
                    style={{ maxWidth: 220, borderRadius: 8, display: 'block' }}
                  />
                ) : m.contentType === 'file' ? (
                  <a href={m.mediaUrl} target="_blank" rel="noreferrer" className="message-file">
                    📎 {m.content || '文件'}
                  </a>
                ) : (
                  m.content
                )}
                <span style={{ color: 'var(--text-tertiary)', marginLeft: 8, fontSize: 11 }}>
                  {m.createdAt.slice(11, 16)}
                </span>
              </div>
            </div>
          )
        })}
      </div>

      <div className={`chat-input-wrap${hosted ? ' hosting' : ''}`}>
        <div className="chat-toolbar">
          <button className="btn-icon" title="表情" onClick={() => toast('表情功能开发中')}>
            <Smile size={16} />
          </button>
          <button className="btn-icon" title="图片" onClick={() => pickFile('image')}>
            <ImageIcon size={16} />
          </button>
          <button className="btn-icon" title="文件" onClick={() => pickFile('file')}>
            <FileText size={16} />
          </button>
          <button className="btn-icon" title="文件夹" onClick={() => pickFile('file')}>
            <Folder size={16} />
          </button>
        </div>
        <input
          ref={imageInputRef}
          type="file"
          accept="image/*"
          style={{ display: 'none' }}
          onChange={(e) => handleFileChange(e, 'image')}
        />
        <input
          ref={fileInputRef}
          type="file"
          style={{ display: 'none' }}
          onChange={(e) => handleFileChange(e, 'file')}
        />
        <div className="chat-input-box">
          <input
            className="chat-input"
            placeholder={
              hosted
                ? '已开启机器人托管'
                : isAppSession
                ? '应用类会话不支持发送消息'
                : '“Enter”发送或点击右边按钮发送'
            }
            value={draft}
            disabled={inputDisabled}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') handleSend()
            }}
          />
          <button className="btn btn-primary" disabled={inputDisabled || sending} onClick={handleSend}>
            <Send size={16} />
          </button>
        </div>
        {hosted && (
          <div className="chat-hosting-mask">
            <Bot size={13} style={{ verticalAlign: '-2px', marginRight: 4 }} />
            已开启机器人托管，请关闭托管后再手动回复
          </div>
        )}
        {isAppSession && !hosted && (
          <div className="chat-hosting-mask">
            <Bot size={13} style={{ verticalAlign: '-2px', marginRight: 4 }} />
            应用类会话不支持发送消息
          </div>
        )}
      </div>
    </section>
  )
}

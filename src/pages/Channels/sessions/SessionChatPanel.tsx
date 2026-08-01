/** 会话聊天面板（SES 右一栏）：托管开关 + 机器人选择 + 消息气泡 + 输入区。 */

import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Smile, Image as ImageIcon, FileText, Folder, Send, Bot } from 'lucide-react'
import type { HostingBotDTO, MessageExtDTO, SessionDTO } from '../../../types/channels'
import { channelsApi } from '../../../api/client'
import { isAppSession as isAppEntity } from '../shared/sessionKind'
import {
  WECOM_EMOJI_MAP,
  renderWecomContent,
  emotionPlaceholder,
} from '../shared/wecomEmoji'
import { toast, errText } from '../../../utils/toast'

/** 常用 Unicode emoji（直接插入输入框，无需转义）。 */
const COMMON_EMOJIS: readonly string[] = [
  '😊', '😂', '🤔', '👍', '👎', '❤️', '🎉', '🔥', '👏', '🙏',
  '😭', '😅', '😍', '🤣', '😎', '🤗', '🤝', '✌️', '🙌', '💪',
  '🤷', '🎂', '🎁', '🌹', '🍺', '☕', '🍉', '🌙', '☀️', '🌟',
]

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
  /** 不渲染内置头部（区域级头部已渲染）。 */
  hideHeader?: boolean
}

export default function SessionChatPanel({
  session,
  messages,
  bots,
  accountId,
  onToggleDetail,
  onHostingChange,
  onMessageSent,
  hideHeader = false,
}: SessionChatPanelProps) {
  const navigate = useNavigate()
  const [botId, setBotId] = useState<string>('')
  const [draft, setDraft] = useState('')
  const [busy, setBusy] = useState(false)
  const [sending, setSending] = useState(false)
  const imageInputRef = useRef<HTMLInputElement | null>(null)
  const fileInputRef = useRef<HTMLInputElement | null>(null)
  // 头像 URL 加载失败集合（企业微信头像链接会过期）→ 回退首字占位，避免裂图。
  const [brokenAvatars, setBrokenAvatars] = useState<Record<string, boolean>>({})

  const emojiBtnRef = useRef<HTMLButtonElement | null>(null)
  const emojiPanelRef = useRef<HTMLDivElement | null>(null)
  const textareaRef = useRef<HTMLTextAreaElement | null>(null)
  const [showEmojiPicker, setShowEmojiPicker] = useState<boolean>(false)
  const [emojiTab, setEmojiTab] = useState<'emoji' | 'wecom'>('emoji')

  const hosted = session?.hostedStatus === 'hosted'
  // 应用/小程序通知类会话（后端 msg_type ∈ {3, 103, 107}）后端禁发，前端禁用输入并提示（决策 #6）。
  // 判定统一走 shared/sessionKind，避免与会话列表 / 右侧头部的判定漂移。
  const isAppSession = isAppEntity(session)
  const inputDisabled = hosted || isAppSession
  const botName = useMemo(
    () => bots.find((b) => b.id === (session?.hostedBotId ?? botId))?.name ?? '请选择机器人',
    [bots, session, botId]
  )

  /** 在 textarea 当前光标处插入文本，并重新聚焦恢复光标位置。 */
  const insertAtCursor = (text: string): void => {
    const ta = textareaRef.current
    if (!ta) {
      setDraft((prev) => prev + text)
      return
    }
    const start = ta.selectionStart
    const end = ta.selectionEnd
    const next = draft.slice(0, start) + text + draft.slice(end)
    const caret = start + text.length
    setDraft(next)
    // 受控组件更新后，下一帧把焦点与光标交还 textarea。
    requestAnimationFrame(() => {
      ta.focus()
      ta.setSelectionRange(caret, caret)
    })
  }

  /** 面板关闭后把焦点交还 textarea，并恢复（或保留）光标位置。 */
  const restoreCaret = (pos?: number): void => {
    const ta = textareaRef.current
    if (!ta) return
    ta.focus()
    const caret = pos ?? ta.selectionStart
    ta.setSelectionRange(caret, caret)
  }

  /** 点击表情按钮：切换面板；关闭时把焦点交还输入框。 */
  const toggleEmojiPicker = (): void => {
    if (inputDisabled) return
    const next = !showEmojiPicker
    setShowEmojiPicker(next)
    if (!next) restoreCaret()
  }

  // 点击面板外部 / 再次点击表情按钮时关闭面板（按钮本身由 contains 判定放行，避免与 toggle 冲突）。
  useEffect(() => {
    if (!showEmojiPicker) return
    const handlePointerDown = (e: MouseEvent): void => {
      const target = e.target as Node
      if (emojiBtnRef.current && emojiBtnRef.current.contains(target)) return
      if (emojiPanelRef.current && emojiPanelRef.current.contains(target)) return
      setShowEmojiPicker(false)
      restoreCaret()
    }
    document.addEventListener('mousedown', handlePointerDown)
    return () => document.removeEventListener('mousedown', handlePointerDown)
  }, [showEmojiPicker])

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

  /** 无头像时的占位首字：本账号发出用「我」，对方用会话名首字。 */
  const avatarInitial = (isOutbound: boolean): string =>
    isOutbound ? '我' : (session.name || '?').trim().charAt(0) || '?'

  /** 头像 alt 文案（可访问性）。 */
  const avatarAlt = (isOutbound: boolean): string => (isOutbound ? '我' : session.name || '对方')

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
      toast(isAppSession ? '应用通知会话，暂不支持回复' : '托管中，暂不支持发送')
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
        // 乐观追加时本地无账号头像，留空回退占位；4s 轮询回填后端真实头像。
        senderAvatar: '',
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
    // 只读会话（应用通知）后端会直接拒绝，前端提前拦截，避免无效请求与误导性报错。
    if (inputDisabled) {
      toast(isAppSession ? '应用通知会话，暂不支持回复' : '托管中，暂不支持发送')
      return
    }
    setSending(true)
    try {
      // 后端按 targetType=session 反查 user_id / room_id + isRoom（决策 #6）。
      const res = await channelsApi.sendTextMessage(accountId, 'session', session.id, text)
      // 乐观追加本地消息（消息历史回填为 P2，先本地呈现）。
      // 若后端返回真实 serverId，则用 `msg-{accountId}-{serverId}` 作为稳定 id，
      // 与后端落库记录对齐，使 4s 轮询回填时 key 不变、避免闪烁/重复。
      const stableId = res.serverId
        ? `msg-${accountId}-${res.serverId}`
        : `local-${Date.now()}`
      onMessageSent?.({
        id: stableId,
        conversationId: session.id,
        senderType: 'user',
        content: text,
        createdAt: new Date().toISOString(),
        serverId: res.serverId ?? '',
        msgType: 0,
        senderId: '',
        // 乐观追加时本地无账号头像，留空回退占位；4s 轮询回填后端真实头像。
        senderAvatar: '',
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
      {!hideHeader && (
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
      )}

      <div className="chat-messages">
        {messages.length === 0 && (
          <div className="message user">
            <div className="message-meta">{isAppSession ? '暂无应用通知' : '（暂无聊天记录）'}</div>
          </div>
        )}
        {messages.map((m) => {
          // 气泡方向以 direction 为准（outbound = 本账号发出，靠右）。
          const isOutbound = m.direction === 'outbound' || m.senderType === 'bot'
          const avatarUrl = m.senderAvatar ?? ''
          const showAvatar = Boolean(avatarUrl) && !brokenAvatars[m.id]
          // 图片气泡必须有真实 URL，否则回落文本分支：表情类回调常出现
          // contentType=image 但 mediaUrl 为空的形态，直出 <img> 会渲染成裂图。
          const asImage = m.contentType === 'image' && Boolean(m.mediaUrl)
          const asFile = !asImage && m.contentType === 'file'
          // 孤立的 [表情]/[动画表情]（协议未给图）降级成友好徽标，避免裸文本占位。
          const emotionBadge = !asImage && !asFile ? emotionPlaceholder(m.content) : null
          return (
            <div key={m.id} className={`message-row ${isOutbound ? 'outbound' : 'inbound'}`}>
              {showAvatar ? (
                <img
                  className={`msg-avatar${isAppSession && !isOutbound ? ' avatar-rounded' : ''}`}
                  src={avatarUrl}
                  alt={avatarAlt(isOutbound)}
                  onError={() => setBrokenAvatars((prev) => ({ ...prev, [m.id]: true }))}
                />
              ) : (
                <div
                  className={`msg-avatar-fallback${isAppSession && !isOutbound ? ' avatar-rounded' : ''}`}
                  aria-hidden="true"
                >
                  {avatarInitial(isOutbound)}
                </div>
              )}
              <div className={`message ${isOutbound ? 'bot' : 'user'}`}>
                <div className="message-meta">
                  {asImage ? (
                    <img
                      src={m.mediaUrl}
                      alt={m.content || '图片'}
                      style={{ maxWidth: 220, borderRadius: 8, display: 'block' }}
                    />
                  ) : asFile ? (
                    <a href={m.mediaUrl} target="_blank" rel="noreferrer" className="message-file">
                      📎 {m.content || '文件'}
                    </a>
                  ) : emotionBadge ? (
                    <span
                      className="message-emotion-badge"
                      title="对方发送了一个表情（协议未提供图片）"
                      style={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: 4,
                        padding: '2px 8px',
                        borderRadius: 10,
                        fontSize: 12,
                        lineHeight: '18px',
                        background: 'var(--bg-tertiary, rgba(0,0,0,0.05))',
                        color: 'var(--text-secondary, #666)',
                      }}
                    >
                      <span aria-hidden="true">{emotionBadge.icon}</span>
                      {emotionBadge.label}
                    </span>
                  ) : (
                    renderWecomContent(m.content)
                  )}
                  <span style={{ color: 'var(--text-tertiary)', marginLeft: 8, fontSize: 11 }}>
                    {m.createdAt.slice(11, 16)}
                  </span>
                </div>
              </div>
            </div>
          )
        })}
      </div>

      <div
        className={`chat-input-wrap${hosted ? ' hosting' : ''}${
          isAppSession ? ' composer-disabled' : ''
        }`}
      >
        <div className="chat-toolbar">
          <button
            ref={emojiBtnRef}
            className="btn-icon"
            title="表情"
            disabled={inputDisabled}
            onClick={toggleEmojiPicker}
          >
            <Smile size={16} />
          </button>
          <button className="btn-icon" title="图片" disabled={inputDisabled} onClick={() => pickFile('image')}>
            <ImageIcon size={16} />
          </button>
          <button className="btn-icon" title="文件" disabled={inputDisabled} onClick={() => pickFile('file')}>
            <FileText size={16} />
          </button>
          <button className="btn-icon" title="文件夹" disabled={inputDisabled} onClick={() => pickFile('file')}>
            <Folder size={16} />
          </button>
        </div>
        {showEmojiPicker && !inputDisabled && (
          <div className="emoji-picker" ref={emojiPanelRef}>
            <div className="emoji-picker-tabs">
              <button
                type="button"
                className={`emoji-picker-tab${emojiTab === 'emoji' ? ' active' : ''}`}
                onClick={() => setEmojiTab('emoji')}
              >
                Emoji
              </button>
              <button
                type="button"
                className={`emoji-picker-tab${emojiTab === 'wecom' ? ' active' : ''}`}
                onClick={() => setEmojiTab('wecom')}
              >
                微信表情
              </button>
            </div>
            <div className="emoji-grid">
              {emojiTab === 'emoji'
                ? COMMON_EMOJIS.map((emoji, idx) => (
                    <button
                      type="button"
                      key={idx}
                      className="emoji-cell"
                      title={emoji}
                      onClick={() => insertAtCursor(emoji)}
                    >
                      {emoji}
                    </button>
                  ))
                : Object.entries(WECOM_EMOJI_MAP).map(([name, emoji]) => (
                    <button
                      type="button"
                      key={name}
                      className="emoji-cell emoji-cell-wecom"
                      title={name}
                      onClick={() => insertAtCursor(`[${name}]`)}
                    >
                      <span className="emoji-cell-char">{emoji}</span>
                      <span className="emoji-cell-name">{name}</span>
                    </button>
                  ))}
            </div>
          </div>
        )}
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
          <textarea
            ref={textareaRef}
            className="chat-input"
            placeholder={
              hosted
                ? '已开启机器人托管'
                : isAppSession
                ? '应用通知会话，暂不支持回复'
                : '“Enter”发送，Shift+Enter 换行'
            }
            value={draft}
            disabled={inputDisabled}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault()
                handleSend()
              }
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
            应用通知会话，暂不支持回复
          </div>
        )}
      </div>
    </section>
  )
}

import { useEffect, useState } from 'react'
import { User, Bot, Headphones, Settings, Smartphone, RefreshCw, AlertCircle, ChevronDown } from 'lucide-react'
import { listConversationMessages } from '../../../services/sessions'
import type { ConversationMessage, ConversationRuntime, ContactRef, SenderType, MessageType } from '../../../types/control'

const SENDER_META: Record<SenderType, { label: string; cls: string; icon: typeof User }> = {
  customer: { label: '客户', cls: 'msg-customer', icon: User },
  ai: { label: 'AI', cls: 'msg-ai', icon: Bot },
  human: { label: '人工', cls: 'msg-human', icon: Headphones },
  system: { label: '系统', cls: 'msg-system', icon: Settings },
  device: { label: '设备', cls: 'msg-device', icon: Smartphone },
}

const TYPE_LABEL: Record<MessageType, string> = {
  text: '文本',
  image: '图片',
  video: '视频',
  voice: '语音',
  file: '文件',
  card: '卡片',
  system: '系统',
}

function formatTime(value: string): string {
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return value
  return d.toLocaleString('zh-CN', { hour12: false })
}

interface MessageStreamTabProps {
  conversationId: string
  runtime: ConversationRuntime | null
  contact: ContactRef | null
}

export default function MessageStreamTab({ conversationId, runtime, contact }: MessageStreamTabProps) {
  const [messages, setMessages] = useState<ConversationMessage[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [hasMore, setHasMore] = useState(false)
  const [nextBeforeSeq, setNextBeforeSeq] = useState<number | null>(null)

  async function load(beforeSeq: number | null = null) {
    setLoading(true)
    setError('')
    try {
      const params: { page?: number; beforeSeq?: number } = { page: 1 }
      if (beforeSeq) params.beforeSeq = beforeSeq
      const data = await listConversationMessages(conversationId, params)
      const items = data.items || []
      if (beforeSeq) {
        setMessages((prev) => [...items, ...prev])
      } else {
        setMessages(items)
      }
      setHasMore(!!data.hasMore)
      setNextBeforeSeq(data.nextBeforeSeq ?? null)
    } catch (e) {
      setError(e instanceof Error ? e.message : '加载消息失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [conversationId])

  return (
    <div className="msg-tab">
      {contact && (
        <div className="msg-contact">
          <span className="msg-contact-label">联系人</span>
          <span className="msg-contact-name">{contact.displayName || contact.externalUid}</span>
          {contact.tags && contact.tags.length > 0 && (
            <span className="msg-contact-tags">
              {(contact.tags || []).map((t) => (
                <span key={t} className="tag tag-neutral">
                  {t}
                </span>
              ))}
            </span>
          )}
        </div>
      )}

      {runtime && (
        <div className="msg-runtime">
          <span className="tag tag-info">运行态 {runtime.sessionRuntimeId.slice(0, 8)}</span>
          <span className="text-secondary">等待节点: {runtime.waitingNodeId || '—'}</span>
          {runtime.activeRunId && (
            <span className="text-secondary">活跃运行: {runtime.activeRunId.slice(0, 8)}</span>
          )}
        </div>
      )}

      {hasMore && (
        <button
          type="button"
          className="msg-load-more btn btn-ghost btn-sm"
          onClick={() => load(nextBeforeSeq)}
          disabled={loading}
        >
          <ChevronDown size={14} />
          {loading ? '加载中…' : '加载更早消息'}
        </button>
      )}

      {error && (
        <div className="sd-inline-error">
          <AlertCircle size={16} />
          {error}
          <button type="button" className="btn btn-ghost btn-sm" onClick={() => load()}>
            <RefreshCw size={14} />重试
          </button>
        </div>
      )}

      <div className="msg-list">
        {!loading && messages.length === 0 && <div className="sd-empty">暂无消息</div>}
        {messages.map((m) => {
          const meta = SENDER_META[m.senderType] || SENDER_META.system
          const Icon = meta.icon
          return (
            <div key={m.messageId} className={`msg-row ${meta.cls}`}>
              <div className="msg-bubble">
                <div className="msg-meta">
                  <Icon size={14} />
                  <span className="msg-sender">{meta.label}</span>
                  <span className="msg-type">{TYPE_LABEL[m.messageType] || m.messageType}</span>
                  <span className="msg-time">{formatTime(m.sentAt)}</span>
                </div>
                <div className="msg-body">
                  {m.contentText ||
                    (m.messageType !== 'text' ? `【${TYPE_LABEL[m.messageType] || m.messageType}消息】` : '')}
                </div>
              </div>
            </div>
          )
        })}
        {loading && messages.length === 0 && (
          <div className="sd-empty">
            <RefreshCw size={16} className="spin" /> 加载消息…
          </div>
        )}
      </div>
    </div>
  )
}

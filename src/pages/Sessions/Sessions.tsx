import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Search, RefreshCw, ChevronRight, MessageSquare, Bot, AlertCircle } from 'lucide-react'
import { listConversations } from '../../services/sessions'
import type { ConversationListItem, SessionState } from '../../types/control'
import './Sessions.css'

const STATE_META: Record<SessionState, { label: string; cls: string }> = {
  IDLE: { label: '空闲', cls: 'tag-neutral' },
  AUTO_HOSTING: { label: 'AI 托管', cls: 'tag-success' },
  WAITING_USER: { label: '等待用户', cls: 'tag-info' },
  WAITING_TIMER: { label: '等待定时器', cls: 'tag-info' },
  WAITING_DEVICE_ACK: { label: '等待设备确认', cls: 'tag-info' },
  HUMAN_HANDOFF: { label: '人工接管', cls: 'tag-danger' },
  PAUSED_BY_POLICY: { label: '策略暂停', cls: 'tag-warning' },
  ERROR_REVIEW: { label: '错误复核', cls: 'tag-danger' },
  CLOSED: { label: '已结束', cls: 'tag-neutral' },
}

interface SessionRow {
  id: string
  subject: string
  channel: string
  bot?: string
  state: SessionState
  last?: string
}

function toRow(c: ConversationListItem): SessionRow {
  return {
    id: c.conversationId,
    subject: c.subject,
    channel: c.channelAccountId,
    bot: c.currentBot?.name,
    state: c.sessionState,
    last: c.lastMessagePreview ?? undefined,
  }
}

export default function SessionsPage() {
  const navigate = useNavigate()
  const [rows, setRows] = useState<SessionRow[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [keyword, setKeyword] = useState('')

  const [page, setPage] = useState(1)
  const pageSize = 20

  async function fetchList() {
    setLoading(true)
    setError('')
    try {
      const data = await listConversations()
      setRows((data.items || []).map(toRow))
    } catch (e) {
      setError(e instanceof Error ? e.message : '加载会话列表失败')
      setRows([])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchList()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const filtered = (() => {
    const kw = keyword.trim().toLowerCase()
    if (!kw) return rows
    return rows.filter((row) =>
      [row.subject, row.channel, row.bot, row.last]
        .some((v) => String(v || '').toLowerCase().includes(kw))
    )
  })()

  function handleSearch(e: React.FormEvent) {
    e.preventDefault()
    setPage(1)
  }

  function handleReset() {
    setKeyword('')
    setPage(1)
  }

  const totalPages = Math.max(1, Math.ceil(filtered.length / pageSize))
  const pageItems = filtered.slice((page - 1) * pageSize, page * pageSize)

  return (
    <div className="sessions-page">
      <div className="sessions-header">
        <div>
          <h1 className="sessions-title">渠道会话</h1>
          <p className="sessions-subtitle">
            查看与运营私域渠道内的会话，支持筛选、进入详情查看运行轨迹与人工接管。
          </p>
        </div>
        <button type="button" className="btn btn-ghost" onClick={fetchList} disabled={loading}>
          <RefreshCw size={16} className={loading ? 'spin' : ''} />
          刷新
        </button>
      </div>

      <form className="sessions-filters" onSubmit={handleSearch}>
        <div className="filter-item filter-grow">
          <Search size={16} className="filter-icon" />
          <input
            type="text"
            placeholder="搜索会话主题（前端筛选）"
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
          />
        </div>
        <button type="submit" className="btn btn-primary" disabled={loading}>
          查询
        </button>
        <button type="button" className="btn btn-ghost" onClick={handleReset} disabled={loading}>
          重置
        </button>
      </form>

      {error && (
        <div className="sessions-error">
          <AlertCircle size={16} />
          {error}
        </div>
      )}

      <div className="sessions-table-wrap">
        <table className="sessions-table">
          <thead>
            <tr>
              <th>主题</th>
              <th>渠道账号</th>
              <th>当前机器人</th>
              <th>会话状态</th>
              <th>最近消息</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {loading && (
              <tr>
                <td colSpan={6} className="sessions-empty">
                  加载中…
                </td>
              </tr>
            )}
            {!loading && filtered.length === 0 && (
              <tr>
                <td colSpan={6} className="sessions-empty">
                  <MessageSquare size={28} />
                  <span>{keyword.trim() ? '没有匹配的会话' : '暂无会话数据'}</span>
                </td>
              </tr>
            )}
            {!loading &&
              pageItems.map((row) => (
                <tr key={row.id} onClick={() => navigate(`/sessions/${row.id}`)}>
                  <td className="cell-subject">
                    <span className="cell-subject-text">{row.subject}</span>
                  </td>
                  <td className="cell-mono">{row.channel}</td>
                  <td>
                    {row.bot ? (
                      <span className="cell-bot">
                        <Bot size={14} />
                        {row.bot}
                      </span>
                    ) : (
                      <span className="text-tertiary">—</span>
                    )}
                  </td>
                  <td>
                    <span className={`tag ${STATE_META[row.state]?.cls || 'tag-neutral'}`}>
                      {STATE_META[row.state]?.label || row.state}
                    </span>
                  </td>
                  <td className="cell-message">{row.last}</td>
                  <td className="cell-action">
                    <ChevronRight size={18} />
                  </td>
                </tr>
              ))}
          </tbody>
        </table>
      </div>

      <div className="sessions-pagination">
        <span className="text-secondary">共 {filtered.length} 条</span>
        <div className="page-controls">
          <button
            type="button"
            className="btn btn-ghost btn-sm"
            disabled={page <= 1 || loading}
            onClick={() => setPage(page - 1)}
          >
            上一页
          </button>
          <span className="page-indicator">
            {page} / {totalPages}
          </span>
          <button
            type="button"
            className="btn btn-ghost btn-sm"
            disabled={page >= totalPages || loading}
            onClick={() => setPage(page + 1)}
          >
            下一页
          </button>
        </div>
      </div>
    </div>
  )
}

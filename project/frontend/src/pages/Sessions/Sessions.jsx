import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Search, RefreshCw, ChevronRight, MessageSquare, Bot, Hand, AlertCircle } from 'lucide-react'
import { listConversations } from '../../services/sessions'
import './Sessions.css'

const SESSION_STATE_LABEL = {
  IDLE: '空闲',
  ACTIVE: '进行中',
  WAITING: '等待中',
  HANDOFF: '已接管',
  CLOSED: '已关闭',
}

const HANDOFF_LABEL = {
  none: '无',
  requested: '申请中',
  active: '接管中',
  returned: '已交还',
}

const HANDOFF_CLASS = {
  none: 'tag-neutral',
  requested: 'tag-warning',
  active: 'tag-danger',
  returned: 'tag-success',
}

const SESSION_STATE_CLASS = {
  IDLE: 'tag-neutral',
  ACTIVE: 'tag-success',
  WAITING: 'tag-info',
  HANDOFF: 'tag-danger',
  CLOSED: 'tag-neutral',
}

function formatTime(value) {
  if (!value) return '—'
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return value
  return d.toLocaleString('zh-CN', { hour12: false })
}

export default function SessionsPage() {
  const navigate = useNavigate()
  const [items, setItems] = useState([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  // 筛选条件
  const [keyword, setKeyword] = useState('')
  const [sessionState, setSessionState] = useState('')
  const [handoffStatus, setHandoffStatus] = useState('')
  const [page, setPage] = useState(1)
  const pageSize = 20
  const projectId = '01JPROJECT' // 种子项目，后续从路由/上下文获取

  async function fetchList() {
    setLoading(true)
    setError('')
    try {
      const params = { projectId, page, pageSize }
      if (keyword.trim()) params.keyword = keyword.trim()
      if (sessionState) params.sessionState = sessionState
      if (handoffStatus) params.handoffStatus = handoffStatus
      const data = await listConversations(params)
      setItems(data.items || [])
      setTotal(data.total || 0)
    } catch (e) {
      setError(e?.message || '加载会话列表失败')
      setItems([])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchList()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page])

  function handleSearch(e) {
    e.preventDefault()
    setPage(1)
    fetchList()
  }

  function handleReset() {
    setKeyword('')
    setSessionState('')
    setHandoffStatus('')
    setPage(1)
    fetchList()
  }

  const totalPages = Math.max(1, Math.ceil(total / pageSize))

  return (
    <div className="sessions-page">
      <div className="sessions-header">
        <div>
          <h1 className="sessions-title">渠道会话</h1>
          <p className="sessions-subtitle">查看与运营私域渠道内的会话，支持筛选、进入详情查看运行轨迹与人工接管。</p>
        </div>
        <button className="btn btn-ghost" onClick={fetchList} disabled={loading}>
          <RefreshCw size={16} className={loading ? 'spin' : ''} />
          刷新
        </button>
      </div>

      <form className="sessions-filters" onSubmit={handleSearch}>
        <div className="filter-item filter-grow">
          <Search size={16} className="filter-icon" />
          <input
            type="text"
            placeholder="搜索会话主题"
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
          />
        </div>
        <select value={sessionState} onChange={(e) => setSessionState(e.target.value)}>
          <option value="">全部状态</option>
          <option value="IDLE">空闲</option>
          <option value="ACTIVE">进行中</option>
          <option value="WAITING">等待中</option>
          <option value="HANDOFF">已接管</option>
          <option value="CLOSED">已关闭</option>
        </select>
        <select value={handoffStatus} onChange={(e) => setHandoffStatus(e.target.value)}>
          <option value="">全部接管</option>
          <option value="none">无</option>
          <option value="requested">申请中</option>
          <option value="active">接管中</option>
          <option value="returned">已交还</option>
        </select>
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
              <th>会话主题</th>
              <th>渠道账号</th>
              <th>当前机器人</th>
              <th>会话状态</th>
              <th>接管状态</th>
              <th>最近消息</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {loading && (
              <tr>
                <td colSpan={7} className="sessions-empty">加载中…</td>
              </tr>
            )}
            {!loading && items.length === 0 && (
              <tr>
                <td colSpan={7} className="sessions-empty">
                  <MessageSquare size={28} />
                  <span>暂无会话数据</span>
                </td>
              </tr>
            )}
            {!loading && items.map((row) => (
              <tr key={row.conversation_id} onClick={() => navigate(`/sessions/${row.conversation_id}`)}>
                <td className="cell-subject">
                  <span className="cell-subject-text">{row.subject || '(无主题)'}</span>
                </td>
                <td className="cell-mono">{row.channel_account_id}</td>
                <td>
                  {row.current_bot ? (
                    <span className="cell-bot"><Bot size={14} />{row.current_bot.name}</span>
                  ) : <span className="text-tertiary">—</span>}
                </td>
                <td>
                  <span className={`tag ${SESSION_STATE_CLASS[row.session_state] || 'tag-neutral'}`}>
                    {SESSION_STATE_LABEL[row.session_state] || row.session_state}
                  </span>
                </td>
                <td>
                  <span className={`tag ${HANDOFF_CLASS[row.handoff_status] || 'tag-neutral'}`}>
                    <Hand size={12} />
                    {HANDOFF_LABEL[row.handoff_status] || row.handoff_status}
                  </span>
                </td>
                <td className="cell-time">{formatTime(row.last_message_at)}</td>
                <td className="cell-action">
                  <ChevronRight size={18} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="sessions-pagination">
        <span className="text-secondary">共 {total} 条</span>
        <div className="page-controls">
          <button className="btn btn-ghost btn-sm" disabled={page <= 1 || loading} onClick={() => setPage(page - 1)}>
            上一页
          </button>
          <span className="page-indicator">{page} / {totalPages}</span>
          <button className="btn btn-ghost btn-sm" disabled={page >= totalPages || loading} onClick={() => setPage(page + 1)}>
            下一页
          </button>
        </div>
      </div>
    </div>
  )
}

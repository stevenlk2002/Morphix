import { useEffect, useState, type ReactNode } from 'react'
import {
  RefreshCw,
  SlidersHorizontal,
  Settings,
  ChevronLeft,
  ChevronRight,
  User,
  MessageSquare,
  Bot,
  Search,
  Send,
  ChevronDown,
  Copy,
} from 'lucide-react'
import Button from '../../components/common/Button'
import Modal from '../../components/common/Modal'
import { toast } from '../../utils/toast'
import {
  messageLogApi,
  type MessageLogItemDTO,
  type MessageLogDetailDTO,
  type ReplyStatus,
} from '../../api/client'
import '../prototype.css'
import './Logs.css'

/** 所属会话可选项（简化自原型的分组会话下拉）。 */
const SESSIONS: string[] = [
  'Dr.Jack 恒康倍力 曹医生',
  '竹绿-健康',
  '通天草-林瞰',
  'MenHM VIP 用户群',
  '健康陪伴群 01',
  '恒康倍力客户群',
]

/** 所属机器人可选项（兼作后端 bot_id 作用域切换）。 */
const ROBOTS: string[] = ['野风秋大健康机器人', '梵芙尼美妆销售机器人']

/** 表格列定义（用于渲染与列设置）。 */
const ALL_COL_KEYS = [
  'id',
  'content',
  'question',
  'account',
  'session',
  'robot',
  'channel',
  'time',
  'action',
] as const
type ColKey = (typeof ALL_COL_KEYS)[number]

const COL_LABELS: Record<ColKey, string> = {
  id: 'AI回复id',
  content: 'AI回复内容(JSON)',
  question: '用户问题',
  account: '托管渠道账号名',
  session: '所属会话',
  robot: '所属机器人',
  channel: '所属渠道',
  time: '回复时间',
  action: '操作',
}

// ---- 详情弹窗：JSON 高亮 / 节点图标 / 复制（照搬原型语义，已 escape 防注入） ----

const escapeHtml = (s: string): string =>
  s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')

const highlightJson = (value: unknown): string => {
  const escaped = escapeHtml(JSON.stringify(value, null, 2))
  return escaped
    .replace(/"([^"]+)":/g, '<span class="key">"$1":</span>')
    .replace(/: "([^"]+)"/g, ': <span class="string">"$1"</span>')
    .replace(/: (\d+)/g, ': <span class="number">$1</span>')
    .replace(/: (true|false)/g, ': <span class="boolean">$1</span>')
    .replace(/: (null)/g, ': <span class="null">$1</span>')
}

const NODE_ICONS: Record<string, ReactNode> = {
  user: <User size={16} />,
  chat: <MessageSquare size={16} />,
  robot: <Bot size={16} />,
  search: <Search size={16} />,
  send: <Send size={16} />,
}

const nodeIcon = (icon: string): ReactNode => NODE_ICONS[icon] ?? <Bot size={16} />

const copyDebugCode = async (text: string) => {
  try {
    await navigator.clipboard.writeText(text)
    toast('已复制')
  } catch {
    toast('复制失败')
  }
}

/**
 * 托管消息日志页（/bots/logs）。
 * 接真实后端：列表走服务端分页 + 筛选；「查看回复详情」渲染为编排工作流节点执行追踪。
 */
export default function BotLogsPage() {
  const [logs, setLogs] = useState<MessageLogItemDTO[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)

  // 筛选条件
  const [idFilter, setIdFilter] = useState('')
  const [questionFilter, setQuestionFilter] = useState('')
  const [sessionFilter, setSessionFilter] = useState('')
  const [robotFilter, setRobotFilter] = useState('')
  const [statusFilter, setStatusFilter] = useState<ReplyStatus | ''>('')
  // 默认日期范围对齐原型（2026-07-04 ~ 2026-07-10）
  const [startDate, setStartDate] = useState('2026-07-04')
  const [endDate, setEndDate] = useState('2026-07-10')
  // 日期输入聚焦时切换为原生 date 选择器，失焦还原为文本以固定显示 YYYY-MM-DD
  const [startFocused, setStartFocused] = useState(false)
  const [endFocused, setEndFocused] = useState(false)

  // 筛选面板 / 列设置 可见性
  const [filtersOpen, setFiltersOpen] = useState(true)
  const [columnsOpen, setColumnsOpen] = useState(false)
  const [visibleCols, setVisibleCols] = useState<Set<ColKey>>(() => new Set(ALL_COL_KEYS))

  // 分页
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)

  // 由「所属机器人」下拉派生后端 bot 作用域（空 / 野风秋 → yefengqiu，梵芙尼 → fanfuni）
  const botId = robotFilter === '梵芙尼美妆销售机器人' ? 'fanfuni' : 'yefengqiu'

  // 回复详情弹窗
  const [detail, setDetail] = useState<MessageLogDetailDTO | null>(null)
  const [detailOpen, setDetailOpen] = useState(false)
  // 受控展开：默认展开首个节点
  const [expanded, setExpanded] = useState<Set<number>>(new Set([0]))

  // 任意筛选条件变化后回到第一页，避免停留在空页。
  useEffect(() => {
    setPage(1)
  }, [idFilter, questionFilter, sessionFilter, robotFilter, statusFilter, startDate, endDate])

  // 服务端分页拉取（bot_id 作用域 + 筛选条件）
  useEffect(() => {
    let cancelled = false
    setLoading(true)
    messageLogApi
      .list(botId, {
        aiReplyId: idFilter || undefined,
        question: questionFilter || undefined,
        session: sessionFilter || undefined,
        status: statusFilter || undefined,
        start: startDate || undefined,
        end: endDate || undefined,
        page,
        pageSize,
      })
      .then((res) => {
        if (cancelled) return
        setLogs(res.items)
        setTotal(res.total)
      })
      .catch(() => {
        if (cancelled) return
        setLogs([])
        setTotal(0)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [botId, idFilter, questionFilter, sessionFilter, statusFilter, startDate, endDate, page, pageSize])

  const resetFilters = () => {
    setIdFilter('')
    setQuestionFilter('')
    setSessionFilter('')
    setRobotFilter('')
    setStatusFilter('')
    setStartDate('')
    setEndDate('')
    setPage(1)
  }

  const handleRefresh = () => {
    // 重新拉取当前页（依赖 effect 自动触发）
    setPage(1)
  }

  const toggleCol = (key: ColKey) => {
    setVisibleCols((prev) => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })
  }

  const openDetail = async (row: MessageLogItemDTO) => {
    try {
      const d = await messageLogApi.getDetail(botId, row.id)
      setDetail(d)
      setExpanded(new Set([0]))
      setDetailOpen(true)
    } catch {
      toast('加载详情失败')
    }
  }
  const closeDetail = () => setDetailOpen(false)

  const toggleNode = (idx: number) => {
    setExpanded((prev) => {
      const next = new Set(prev)
      if (next.has(idx)) next.delete(idx)
      else next.add(idx)
      return next
    })
  }

  const renderCell = (row: MessageLogItemDTO, key: ColKey): ReactNode => {
    switch (key) {
      case 'id':
        return <span className="mono">{row.id}</span>
      case 'content':
        return <pre className="json-preview">{JSON.stringify(row.content, null, 2)}</pre>
      case 'question':
        return row.question || '-'
      case 'account':
        return row.account
      case 'session':
        return row.session
      case 'robot':
        return row.robot ? (
          <span className="proto-badge proto-badge-info">{row.robot}</span>
        ) : (
          '-'
        )
      case 'channel':
        return row.channel
      case 'time':
        return <span className="mono text-secondary">{row.time}</span>
      default:
        return null
    }
  }

  const visibleKeys = ALL_COL_KEYS.filter((k) => visibleCols.has(k))

  const startIdx = total === 0 ? 0 : (page - 1) * pageSize + 1
  const endIdx = total === 0 ? 0 : (page - 1) * pageSize + logs.length
  const showLoading = loading && logs.length === 0
  const showEmpty = !loading && total === 0

  return (
    <div className="proto-page">
      {/* 头部工具栏：标题 + 三个图标操作（刷新 / 筛选 / 列设置） */}
      <div className="message-logs-toolbar">
        <div className="message-logs-title">托管消息日志</div>
        <div className="message-logs-actions">
          <button className="btn-icon" type="button" title="刷新" onClick={handleRefresh}>
            <RefreshCw size={16} />
          </button>
          <button
            className="btn-icon"
            type="button"
            title="筛选"
            onClick={() => setFiltersOpen((o) => !o)}
          >
            <SlidersHorizontal size={16} />
          </button>
          <div className="logs-colsettings">
            <button
              className="btn-icon"
              type="button"
              title="列设置"
              onClick={() => setColumnsOpen((o) => !o)}
            >
              <Settings size={16} />
            </button>
            {columnsOpen && (
              <div className="logs-colsettings-menu" role="menu">
                {ALL_COL_KEYS.map((k) => (
                  <label key={k} className="logs-colsettings-item">
                    <input type="checkbox" checked={visibleCols.has(k)} onChange={() => toggleCol(k)} />
                    {COL_LABELS[k]}
                  </label>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* 筛选卡片：4 列网格，末列底部放「重置 / 查询」 */}
      {filtersOpen && (
        <div className="proto-card logs-filters">
          <div className="message-logs-filters">
            <div className="filter-field">
              <label>AI回复id</label>
              <input
                className="input"
                value={idFilter}
                placeholder="请输入"
                onChange={(e) => setIdFilter(e.target.value)}
              />
            </div>
            <div className="filter-field">
              <label>用户问题</label>
              <input
                className="input"
                value={questionFilter}
                placeholder="请输入"
                onChange={(e) => setQuestionFilter(e.target.value)}
              />
            </div>
            <div className="filter-field">
              <label>所属会话</label>
              <select
                className="select"
                value={sessionFilter}
                onChange={(e) => setSessionFilter(e.target.value)}
              >
                <option value="">请输入会话名称搜索</option>
                {SESSIONS.map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </select>
            </div>
            <div className="filter-field">
              <label>所属机器人</label>
              <select
                className="select"
                value={robotFilter}
                onChange={(e) => setRobotFilter(e.target.value)}
              >
                <option value="">请选择</option>
                {ROBOTS.map((r) => (
                  <option key={r} value={r}>
                    {r}
                  </option>
                ))}
              </select>
            </div>
            <div className="filter-field">
              <label>AI回复状态</label>
              <select
                className="select"
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value as ReplyStatus | '')}
              >
                <option value="">请选择</option>
                <option value="成功">成功</option>
                <option value="失败">失败</option>
                <option value="处理中">处理中</option>
              </select>
            </div>
            <div className="filter-field">
              <label>回复时间</label>
              <div className="date-range">
                <input
                  className="input"
                  type={startFocused ? 'date' : 'text'}
                  value={startDate}
                  placeholder="2026-07-04"
                  style={{ textAlign: 'center' }}
                  onFocus={() => setStartFocused(true)}
                  onBlur={() => setStartFocused(false)}
                  onChange={(e) => setStartDate(e.target.value)}
                />
                <span className="logs-date-arrow">→</span>
                <input
                  className="input"
                  type={endFocused ? 'date' : 'text'}
                  value={endDate}
                  placeholder="2026-07-10"
                  style={{ textAlign: 'center' }}
                  onFocus={() => setEndFocused(true)}
                  onBlur={() => setEndFocused(false)}
                  onChange={(e) => setEndDate(e.target.value)}
                />
              </div>
            </div>
            <div className="filter-field" />
            <div className="filter-field">
              <div className="filter-btns">
                <button type="button" className="logs-btn-reset" onClick={resetFilters}>
                  重置
                </button>
                <button type="button" className="logs-btn-query" onClick={() => setPage(1)}>
                  查询
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* 表格 */}
      <div className="proto-card">
        {showLoading ? (
          <div className="logs-empty">加载中…</div>
        ) : showEmpty ? (
          <div className="logs-empty">暂无符合条件的托管消息日志</div>
        ) : (
          <table className="proto-table message-logs-table">
            <thead>
              <tr>
                {visibleKeys.map((k) => (
                  <th key={k}>{COL_LABELS[k]}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {logs.map((row) => (
                <tr key={row.id}>
                  {visibleKeys.map((k) => (
                    <td key={k} className={k === 'content' ? 'col-content' : undefined}>
                      {k === 'action' ? (
                        <button className="proto-link col-link" type="button" onClick={() => openDetail(row)}>
                          查看回复详情
                        </button>
                      ) : (
                        renderCell(row, k)
                      )}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        )}

        {/* 分页脚注 */}
        <div className="logs-pagination">
          <span className="logs-page-info">
            第 {total === 0 ? 0 : startIdx}-{endIdx} 条/总共 {total} 条
          </span>
          <div className="logs-page-nav">
            <Button
              variant="ghost"
              size="sm"
              icon={<ChevronLeft size={14} />}
              disabled={page <= 1}
              onClick={() => setPage((p) => Math.max(1, p - 1))}
            >
              上一页
            </Button>
            <Button
              variant="ghost"
              size="sm"
              icon={<ChevronRight size={14} />}
              disabled={endIdx >= total}
              onClick={() => setPage((p) => p + 1)}
            >
              下一页
            </Button>
          </div>
          <select
            className="select logs-page-size"
            value={pageSize}
            onChange={(e) => {
              setPageSize(Number(e.target.value))
              setPage(1)
            }}
          >
            <option value={20}>20 条/页</option>
            <option value={50}>50 条/页</option>
            <option value={100}>100 条/页</option>
          </select>
        </div>
      </div>

      {/* 回复详情弹窗：编排工作流节点执行追踪 */}
      <Modal open={detailOpen} title="回复详情" width={760} onClose={closeDetail}>
        {detail && (
          <div className="logs-debug">
            <div className="logs-debug-id mono">{detail.id}</div>
            <div className="debug-nodes">
              {detail.nodes.map((node, idx) => (
                <div key={idx} className={`debug-node${expanded.has(idx) ? ' expanded' : ''}`}>
                  <div className="debug-node-header" onClick={() => toggleNode(idx)}>
                    <span className="arrow">
                      <ChevronDown size={16} />
                    </span>
                    <span className="debug-node-icon">{nodeIcon(node.icon)}</span>
                    <span className="debug-node-title">{node.name}</span>
                    <span className="debug-node-runtime">运行时间：{node.runtime}</span>
                  </div>
                  <div className="debug-node-body">
                    <div className="debug-section">
                      <div className="debug-section-label">模块输入值</div>
                      <div className="debug-code-block">
                        <div className="debug-code-header">
                          <span>json</span>
                          <button
                            type="button"
                            className="debug-code-copy"
                            onClick={() => copyDebugCode(JSON.stringify(node.input, null, 2))}
                          >
                            <Copy size={12} /> 复制
                          </button>
                        </div>
                        <div
                          className="debug-code-body"
                          dangerouslySetInnerHTML={{ __html: highlightJson(node.input) }}
                        />
                      </div>
                    </div>
                    <div className="debug-section">
                      <div className="debug-section-label">模块输出值</div>
                      <div className="debug-code-block">
                        <div className="debug-code-header">
                          <span>json</span>
                          <button
                            type="button"
                            className="debug-code-copy"
                            onClick={() => copyDebugCode(JSON.stringify(node.output, null, 2))}
                          >
                            <Copy size={12} /> 复制
                          </button>
                        </div>
                        <div
                          className="debug-code-body"
                          dangerouslySetInnerHTML={{ __html: highlightJson(node.output) }}
                        />
                      </div>
                    </div>
                    <div className="debug-section">
                      <div className="debug-section-label">源码片段</div>
                      <div className="debug-code-block">
                        <div className="debug-code-header">
                          <span>python</span>
                          <button
                            type="button"
                            className="debug-code-copy"
                            onClick={() => copyDebugCode(node.code)}
                          >
                            <Copy size={12} /> 复制
                          </button>
                        </div>
                        <div
                          className="debug-code-body"
                          dangerouslySetInnerHTML={{ __html: escapeHtml(node.code || '') }}
                        />
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </Modal>
    </div>
  )
}

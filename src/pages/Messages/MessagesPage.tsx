import { useCallback, useEffect, useState } from 'react'
import Modal from '../../components/common/Modal'
import { messagesApi, ApiClientError } from '../../api/client'
import type { SystemMessageDTO, MessagesListResponse } from '../../api/client'
import { toast, errText } from '../../utils/toast'
import './MessagesPage.css'

type MessageTab = 'unread' | 'read'

/**
 * 消息中心页面。
 *
 * 对齐原型 `prototype/index.html` 的 messages 视图：
 * - 未读 / 已读 两个 tab（无「全部」）
 * - 标题筛选（点「查询」提交，点「重置」清空）
 * - 分页（每页 10/20/50，默认 20）
 * - 「全部已读」仅在未读 tab 生效
 * - 单条「已读」、行内「查看详情」弹窗
 *
 * 数据全部来自后端 /api/messages，组件仅持有 UI 态（tab / 页码 / 筛选值）。
 */
export default function MessagesPage() {
  const [currentTab, setCurrentTab] = useState<MessageTab>('unread')
  const [currentPage, setCurrentPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)
  /** 标题筛选下拉的当前选择（受控）。 */
  const [titleSelect, setTitleSelect] = useState('')
  /** 已提交的标题筛选值（仅「查询」时更新，参与查询）。 */
  const [titleFilter, setTitleFilter] = useState('')

  const [items, setItems] = useState<SystemMessageDTO[]>([])
  const [total, setTotal] = useState(0)
  const [titles, setTitles] = useState<string[]>([])
  const [unreadCount, setUnreadCount] = useState(0)

  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [selected, setSelected] = useState<SystemMessageDTO | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const data: MessagesListResponse = await messagesApi.list({
        tab: currentTab,
        title: titleFilter,
        page: currentPage,
        pageSize,
      })
      setItems(data.items)
      setTotal(data.total)
      setTitles(data.titles)
      setUnreadCount(data.unreadCount)
    } catch (e) {
      const msg =
        e instanceof ApiClientError ? e.message : '加载消息失败，请稍后重试'
      setError(msg)
    } finally {
      setLoading(false)
    }
  }, [currentTab, currentPage, pageSize, titleFilter])

  // 切换 tab / 翻页 / 改每页条数 / 提交筛选后重新拉取。
  useEffect(() => {
    void load()
  }, [load])

  const switchTab = (tab: MessageTab) => {
    setCurrentTab(tab)
    setCurrentPage(1)
  }

  /** 点「查询」：提交当前下拉选择，回到第一页。 */
  const applyFilter = () => {
    setTitleFilter(titleSelect)
    setCurrentPage(1)
  }

  /** 点「重置」：清空筛选，回到第一页。 */
  const resetFilter = () => {
    setTitleSelect('')
    setTitleFilter('')
    setCurrentPage(1)
  }

  const markRead = async (id: string) => {
    try {
      await messagesApi.markRead(id)
      toast('已归档到已读')
      await load()
    } catch (e) {
      setError(errText(e))
    }
  }

  const markAllRead = async () => {
    if (currentTab === 'read') return
    const before = unreadCount
    try {
      const res = await messagesApi.markAllRead()
      const count = res.updated > 0 ? res.updated : before
      toast(`已将 ${count} 条消息归档到已读`)
      setCurrentPage(1)
      await load()
    } catch (e) {
      setError(errText(e))
    }
  }

  const start = (currentPage - 1) * pageSize
  const displayEnd = Math.min(start + pageSize, total)
  const displayStart = total === 0 ? 0 : start + 1
  const totalPages = Math.max(1, Math.ceil(total / pageSize))

  return (
    <div className="messages-page">
      <div className="messages-header">
        <h2>消息中心</h2>
      </div>

      <div className="card">
        <div className="card-body">
          <div className="messages-toolbar">
            <div className="filter-bar">
              <label>标题</label>
              <select
                className="select"
                value={titleSelect}
                onChange={(e) => setTitleSelect(e.target.value)}
              >
                <option value="">全部</option>
                {titles.map((t) => (
                  <option key={t} value={t}>
                    {t}
                  </option>
                ))}
              </select>
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                onClick={resetFilter}
              >
                重置
              </button>
              <button
                type="button"
                className="btn btn-primary btn-sm"
                onClick={applyFilter}
              >
                查询
              </button>
            </div>

            <div className="messages-toolbar-right">
              <div className="messages-tabs">
                <button
                  type="button"
                  className={`messages-tab ${currentTab === 'unread' ? 'active' : ''}`}
                  onClick={() => switchTab('unread')}
                >
                  未读
                </button>
                <button
                  type="button"
                  className={`messages-tab ${currentTab === 'read' ? 'active' : ''}`}
                  onClick={() => switchTab('read')}
                >
                  已读
                </button>
              </div>
              <button
                type="button"
                className="btn btn-primary btn-sm"
                onClick={markAllRead}
                disabled={currentTab === 'read'}
              >
                全部已读
              </button>
            </div>
          </div>

          {error && <div className="messages-error">{error}</div>}

          {items.length === 0 ? (
            <div className="messages-empty">
              {loading ? '加载中…' : `暂无${currentTab === 'read' ? '已读' : '未读'}消息`}
            </div>
          ) : (
            <table className="messages-table">
              <thead>
                <tr>
                  <th className="col-title">标题</th>
                  <th className="col-content">内容</th>
                  <th className="col-time">时间</th>
                  <th className="col-action">操作</th>
                </tr>
              </thead>
              <tbody>
                {items.map((m) => (
                  <tr key={m.id}>
                    <td>
                      <div className={`msg-title ${m.warn ? 'warning' : ''}`}>
                        {m.title}
                      </div>
                    </td>
                    <td>
                      <div className="msg-content">{m.content}</div>
                    </td>
                    <td>
                      <div className="msg-time">{m.time}</div>
                    </td>
                    <td>
                      <div className="msg-actions">
                        {currentTab === 'unread' && (
                          <button
                            type="button"
                            className="btn-text read"
                            onClick={() => markRead(m.id)}
                          >
                            已读
                          </button>
                        )}
                        <button
                          type="button"
                          className="btn-text"
                          onClick={() => setSelected(m)}
                        >
                          查看详情
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}

          <div className="messages-pagination">
            <span>
              第 {displayStart}-{displayEnd} 条/总共 {total} 条
            </span>
            <div className="page-buttons">
              {Array.from({ length: totalPages }, (_, i) => i + 1).map((p) => (
                <button
                  key={p}
                  type="button"
                  className={`page-btn ${p === currentPage ? 'active' : ''}`}
                  onClick={() => setCurrentPage(p)}
                >
                  {p}
                </button>
              ))}
            </div>
            <select
              className="page-size-select"
              value={pageSize}
              onChange={(e) => {
                setPageSize(Number(e.target.value))
                setCurrentPage(1)
              }}
            >
              <option value={10}>10条/页</option>
              <option value={20}>20条/页</option>
              <option value={50}>50条/页</option>
            </select>
          </div>
        </div>
      </div>

      <Modal
        open={selected !== null}
        title={selected?.title ?? ''}
        onClose={() => setSelected(null)}
        footer={
          selected ? (
            <>
              {!selected.read ? (
                <>
                  <button
                    type="button"
                    className="btn btn-secondary"
                    onClick={() => setSelected(null)}
                  >
                    取消
                  </button>
                  <button
                    type="button"
                    className="btn btn-primary"
                    onClick={() => {
                      const id = selected.id
                      setSelected(null)
                      void markRead(id)
                    }}
                  >
                    已读
                  </button>
                </>
              ) : (
                <button
                  type="button"
                  className="btn btn-primary"
                  onClick={() => setSelected(null)}
                >
                  确认
                </button>
              )}
            </>
          ) : null
        }
      >
        <p className="message-detail-content">{selected?.content}</p>
      </Modal>
    </div>
  )
}

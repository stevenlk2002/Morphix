import { useState, useEffect, useCallback, useRef, useMemo } from 'react'
import { Search, X } from 'lucide-react'
import Button from '../../../components/common/Button'
import { operationsTasksApi } from '../../../api/operations'
import { customerGroupsApi } from '../../../api/client'
import type {
  TargetSessionDetail,
  HostingAccount,
  HostingBot,
  TagItem,
  TagGroup,
  StaticFilterState,
  DynamicFilterState,
} from '../../../types/operations'
import type { CustomerGroupDTO } from '../../../types/customers'

/** 默认静态筛选状态。 */
const DEFAULT_STATIC_FILTER: StaticFilterState = {
  keyword: '',
  hostingAccountId: '',
  hostingBotId: '',
  tagId: '',
  tagRelation: '',
}

/** 默认动态筛选状态。 */
const DEFAULT_DYNAMIC_FILTER: DynamicFilterState = {
  hostingAccountId: '',
  hostingBotId: '',
  tagRelation: 'and',
  tagIds: [],
}

interface Props {
  /** 会话类型：单聊 / 群聊 */
  sessionType: 'single' | 'group'
  /** 渠道（如 企业微信） */
  channel: string
  /** 已选会话 ID 列表 */
  selectedSessionIds: string[]
  /** 选择变更回调 */
  onChange: (selectedIds: string[]) => void
  /** 已选客户分组 ID 列表 */
  selectedGroupIds: string[]
  /** 分组选择变更回调 */
  onGroupChange: (ids: string[]) => void
  /** 编辑时传入，标记已选 */
  taskId?: string
}

/** GroupTab 属性。 */
interface GroupTabProps {
  selectedIds: string[]
  onChange: (ids: string[]) => void
}

/** 通过客户分组选择 Tab。 */
function GroupTab({ selectedIds, onChange }: GroupTabProps) {
  const [groups, setGroups] = useState<CustomerGroupDTO[]>([])
  const [loading, setLoading] = useState(false)
  const [nameInput, setNameInput] = useState('')
  const [typeInput, setTypeInput] = useState('')
  const [appliedName, setAppliedName] = useState('')
  const [appliedType, setAppliedType] = useState('')
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(10)
  const [total, setTotal] = useState(0)
  const [showNamePopup, setShowNamePopup] = useState(false)
  const nameInputRef = useRef<HTMLInputElement>(null)

  /** 将 string[] 转为 Set 以便 O(1) 查找。 */
  const selectedSet = useMemo(() => new Set(selectedIds), [selectedIds])

  const loadGroups = useCallback(async () => {
    setLoading(true)
    try {
      const res = await customerGroupsApi.list({ name: appliedName, type: appliedType })
      setGroups(res)
      setTotal(res.length)
    } catch {
      setGroups([])
      setTotal(0)
    } finally {
      setLoading(false)
    }
  }, [appliedName, appliedType])

  useEffect(() => {
    loadGroups()
  }, [loadGroups])

  const filtered = useMemo(() => {
    const start = (page - 1) * pageSize
    return groups.slice(start, start + pageSize)
  }, [groups, page, pageSize])

  const endItem = Math.min(page * pageSize, total)

  const allCurrentChecked =
    filtered.length > 0 && filtered.every((g) => selectedSet.has(g.id))
  const someCurrentChecked = filtered.some((g) => selectedSet.has(g.id)) && !allCurrentChecked

  const toggleAllCurrent = () => {
    const next = new Set(selectedSet)
    if (allCurrentChecked) {
      filtered.forEach((g) => next.delete(g.id))
    } else {
      filtered.forEach((g) => next.add(g.id))
    }
    onChange(Array.from(next))
  }

  const toggleOne = (id: string) => {
    const next = new Set(selectedSet)
    if (next.has(id)) next.delete(id)
    else next.add(id)
    onChange(Array.from(next))
  }

  const handleReset = () => {
    setNameInput('')
    setTypeInput('')
    setAppliedName('')
    setAppliedType('')
    setPage(1)
  }

  const handleQuery = () => {
    setAppliedName(nameInput)
    setAppliedType(typeInput)
    setPage(1)
  }

  const nameMatches = useMemo(() => {
    if (!nameInput.trim()) return []
    const kw = nameInput.toLowerCase()
    return groups.filter((g) => g.name.toLowerCase().includes(kw)).slice(0, 8)
  }, [nameInput, groups])

  return (
    <div className="target-panel">
      {/* 筛选栏 */}
      <div className="target-filter-bar">
        <div className="form-group groups-filter-item" style={{ position: 'relative' }}>
          <label className="form-label">客户分组：</label>
          <input
            ref={nameInputRef}
            className="input"
            value={nameInput}
            placeholder="请输入"
            onChange={(e) => {
              setNameInput(e.target.value)
              setShowNamePopup(true)
            }}
            onFocus={() => setShowNamePopup(true)}
            onBlur={() => setTimeout(() => setShowNamePopup(false), 150)}
          />
          {showNamePopup && nameMatches.length > 0 && (
            <div className="target-name-popup">
              {nameMatches.map((g) => (
                <div
                  key={g.id}
                  className="target-name-popup-item"
                  onClick={() => {
                    setNameInput(g.name)
                    setAppliedName(g.name)
                    setShowNamePopup(false)
                    setPage(1)
                  }}
                >
                  {g.name}
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="form-group groups-filter-item">
          <label className="form-label">类型：</label>
          <select className="select" value={typeInput} onChange={(e) => setTypeInput(e.target.value)}>
            <option value="">请选择</option>
            <option value="custom">动态</option>
            <option value="system">静态</option>
          </select>
        </div>

        <div className="groups-filter-actions">
          <Button variant="secondary" size="sm" onClick={handleReset}>重置</Button>
          <Button variant="primary" size="sm" icon={<Search size={14} />} onClick={handleQuery}>查询</Button>
        </div>
      </div>

      {/* 表格 */}
      <div className="target-table-wrapper">
        {loading ? (
          <div className="target-loading">加载中...</div>
        ) : (
          <table className="proto-table target-data-table">
            <thead>
              <tr>
                <th style={{ width: 40 }}>
                  <input
                    type="checkbox"
                    checked={allCurrentChecked}
                    ref={(el) => {
                      if (el) el.indeterminate = someCurrentChecked
                    }}
                    onChange={toggleAllCurrent}
                  />
                </th>
                <th>客户分组</th>
                <th>类型</th>
                <th style={{ textAlign: 'right' }}>当前客户数</th>
                <th>创建时间</th>
                <th>编辑时间</th>
                <th>编辑人</th>
              </tr>
            </thead>
            <tbody>
              {filtered.length === 0 ? (
                <tr>
                  <td colSpan={7} style={{ textAlign: 'center', color: 'var(--text-tertiary)', padding: 24 }}>
                    暂无数据
                  </td>
                </tr>
              ) : (
                filtered.map((g) => (
                  <tr key={g.id}>
                    <td>
                      <input
                        type="checkbox"
                        checked={selectedSet.has(g.id)}
                        onChange={() => toggleOne(g.id)}
                      />
                    </td>
                    <td>{g.name}</td>
                    <td>
                      <span className={`proto-badge ${g.type === 'system' ? 'proto-badge-info' : 'proto-badge-success'}`}>
                        {g.type === 'system' ? '静态' : '动态'}
                      </span>
                    </td>
                    <td style={{ textAlign: 'right' }}>{g.count}</td>
                    <td className="text-secondary">{g.createdAt}</td>
                    <td className="text-secondary">{g.updatedAt}</td>
                    <td>{g.editor || '—'}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        )}
      </div>

      {/* 分页 + 跨页全选 */}
      <div className="target-pagination">
        <label className="target-cross-page">
          <input
            type="checkbox"
            checked={total > 0 && groups.every((g) => selectedSet.has(g.id))}
            ref={(el) => {
              if (el)
                el.indeterminate =
                  groups.some((g) => selectedSet.has(g.id)) && !groups.every((g) => selectedSet.has(g.id))
            }}
            onChange={() => {
              const next = new Set(selectedSet)
              if (groups.every((g) => selectedSet.has(g.id))) {
                groups.forEach((g) => next.delete(g.id))
              } else {
                groups.forEach((g) => next.add(g.id))
              }
              onChange(Array.from(next))
            }}
          />
          <span>跨页全选</span>
          <span style={{ color: 'var(--text-tertiary)' }}>已选中分组数：{selectedSet.size}</span>
        </label>
        <div className="target-page-info">
          第 {(page - 1) * pageSize + 1 || 0}-{endItem} 条/总共 {total} 条
        </div>
        <div className="target-pager">
          <button
            className="btn btn-ghost btn-sm"
            disabled={page === 1}
            onClick={() => setPage((p) => Math.max(1, p - 1))}
          >
            ‹
          </button>
          <span style={{ padding: '0 12px', fontSize: 13 }}>
            {page} / {Math.max(1, Math.ceil(total / pageSize))}
          </span>
          <button
            className="btn btn-ghost btn-sm"
            disabled={page >= Math.ceil(total / pageSize)}
            onClick={() => setPage((p) => Math.min(Math.ceil(total / pageSize), p + 1))}
          >
            ›
          </button>
          <select
            className="select"
            value={pageSize}
            onChange={(e) => {
              setPageSize(Number(e.target.value))
              setPage(1)
            }}
            style={{ marginLeft: 8, height: 28, padding: '0 8px' }}
          >
            <option value={10}>10 条/页</option>
            <option value={20}>20 条/页</option>
            <option value={50}>50 条/页</option>
          </select>
        </div>
      </div>
    </div>
  )
}

/** 运营对象选择器（v2）：静态选择 / 动态选择 / 通过客户分组选择 三 Tab。 */
export default function TargetSelector({
  sessionType,
  channel,
  selectedSessionIds,
  onChange,
  selectedGroupIds,
  onGroupChange,
  taskId: _taskId,
}: Props) {
  // ---- Tab ----
  const [activeTab, setActiveTab] = useState<'static' | 'dynamic' | 'group'>('static')

  // ---- 静态筛选 ----
  const [staticFilter, setStaticFilter] = useState<StaticFilterState>(DEFAULT_STATIC_FILTER)
  const [appliedStaticFilter, setAppliedStaticFilter] = useState<StaticFilterState>(DEFAULT_STATIC_FILTER)

  // ---- 动态筛选 ----
  const [dynamicFilter, setDynamicFilter] = useState<DynamicFilterState>(DEFAULT_DYNAMIC_FILTER)

  // ---- 表格数据 ----
  const [sessions, setSessions] = useState<TargetSessionDetail[]>([])
  const [loading, setLoading] = useState(false)
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [pageSize] = useState(20)

  // ---- 跨页全选 ----
  const [selectAllAcrossPages, setSelectAllAcrossPages] = useState(false)

  // ---- 下拉选项 ----
  const [hostingAccounts, setHostingAccounts] = useState<HostingAccount[]>([])
  const [hostingBots, setHostingBots] = useState<HostingBot[]>([])
  const [tags, setTags] = useState<TagItem[]>([])
  const [tagGroups, setTagGroups] = useState<TagGroup[]>([])

  // ---- 标签弹窗 ----
  const [showTagModal, setShowTagModal] = useState(false)
  const [tagSearchKeyword, setTagSearchKeyword] = useState('')
  const tagModalRef = useRef<HTMLDivElement>(null)

  // ---- 初始化加载下拉选项 ----
  useEffect(() => {
    operationsTasksApi.listHostingAccounts(channel).then(setHostingAccounts).catch(() => setHostingAccounts([]))
    operationsTasksApi.listHostingBots().then(setHostingBots).catch(() => setHostingBots([]))
    operationsTasksApi.listTags().then(setTags).catch(() => setTags([]))
    operationsTasksApi.listTagGroups().then(setTagGroups).catch(() => setTagGroups([]))
  }, [channel])

  // ---- 加载表格数据 ----
  const loadSessions = useCallback(
    async (p: number) => {
      setLoading(true)
      try {
        if (activeTab === 'static') {
          const data = await operationsTasksApi.listTargetSessionsV2({
            channel,
            sessionType,
            keyword: appliedStaticFilter.keyword,
            hostingAccountId: appliedStaticFilter.hostingAccountId,
            hostingBotId: appliedStaticFilter.hostingBotId,
            tagId: appliedStaticFilter.tagId || undefined,
            tagRelation: appliedStaticFilter.tagRelation || undefined,
            page: p,
            pageSize,
          })
          setSessions(data.items)
          setTotal(data.total)
          setPage(data.page)
        } else {
          const data = await operationsTasksApi.listTargetSessionsV2({
            channel,
            sessionType,
            hostingAccountId: dynamicFilter.hostingAccountId,
            hostingBotId: dynamicFilter.hostingBotId,
            tagId: dynamicFilter.tagIds.length > 0 ? dynamicFilter.tagIds.join(',') : undefined,
            tagRelation: dynamicFilter.tagRelation,
            page: p,
            pageSize,
          })
          setSessions(data.items)
          setTotal(data.total)
          setPage(data.page)
        }
      } catch (err) {
        console.error('加载会话失败:', err)
        setSessions([])
        setTotal(0)
      } finally {
        setLoading(false)
      }
    },
    [channel, sessionType, appliedStaticFilter, dynamicFilter, activeTab, pageSize],
  )

  // 首次加载 + 切换 Tab / 筛选变化时重新加载
  useEffect(() => {
    loadSessions(1)
  }, [loadSessions])

  // 当 sessionType 变化时，清空选择并重置筛选
  useEffect(() => {
    setStaticFilter(DEFAULT_STATIC_FILTER)
    setAppliedStaticFilter(DEFAULT_STATIC_FILTER)
    setDynamicFilter(DEFAULT_DYNAMIC_FILTER)
    setSelectAllAcrossPages(false)
    setPage(1)
  }, [sessionType])

  // ---- 勾选逻辑 ----
  const toggleSession = useCallback(
    (sid: string) => {
      if (selectAllAcrossPages) {
        // 跨页全选模式下：取消跨页全选，改为仅选中当前页
        setSelectAllAcrossPages(false)
        const currentPageIds = sessions.map((s) => s.id)
        const withoutCurrent = selectedSessionIds.filter((id) => !currentPageIds.includes(id))
        if (selectedSessionIds.includes(sid)) {
          onChange(withoutCurrent.filter((id) => id !== sid))
        } else {
          onChange([...withoutCurrent, sid])
        }
      } else {
        if (selectedSessionIds.includes(sid)) {
          onChange(selectedSessionIds.filter((id) => id !== sid))
        } else {
          onChange([...selectedSessionIds, sid])
        }
      }
    },
    [selectedSessionIds, onChange, selectAllAcrossPages, sessions],
  )

  const toggleAllCurrentPage = useCallback(() => {
    const currentPageIds = sessions.map((s) => s.id)
    const allCurrentChecked = currentPageIds.every((id) => selectedSessionIds.includes(id))

    if (selectAllAcrossPages) {
      setSelectAllAcrossPages(false)
    }

    if (allCurrentChecked) {
      onChange(selectedSessionIds.filter((id) => !currentPageIds.includes(id)))
    } else {
      const toAdd = currentPageIds.filter((id) => !selectedSessionIds.includes(id))
      onChange([...selectedSessionIds, ...toAdd])
    }
  }, [sessions, selectedSessionIds, onChange, selectAllAcrossPages])

  const handleSelectAllAcrossPages = useCallback(() => {
    if (selectAllAcrossPages) {
      setSelectAllAcrossPages(false)
    } else {
      setSelectAllAcrossPages(true)
      // 将当前页所有 ID 加入选中（若尚未在全量中）
      const currentPageIds = sessions.map((s) => s.id)
      const toAdd = currentPageIds.filter((id) => !selectedSessionIds.includes(id))
      if (toAdd.length > 0) {
        onChange([...selectedSessionIds, ...toAdd])
      }
    }
  }, [selectAllAcrossPages, sessions, selectedSessionIds, onChange])

  // ---- 分页 ----
  const totalPages = Math.max(1, Math.ceil(total / pageSize))

  const handlePageChange = useCallback(
    (newPage: number) => {
      if (newPage < 1 || newPage > totalPages) return
      loadSessions(newPage)
    },
    [totalPages, loadSessions],
  )

  // ---- 静态筛选：查询 ----
  const handleStaticQuery = useCallback(() => {
    setAppliedStaticFilter({ ...staticFilter })
  }, [staticFilter])

  // ---- 静态筛选：重置 ----
  const handleStaticReset = useCallback(() => {
    setStaticFilter(DEFAULT_STATIC_FILTER)
    setAppliedStaticFilter(DEFAULT_STATIC_FILTER)
    setSelectAllAcrossPages(false)
  }, [])

  // ---- 动态筛选：标签弹窗 ----
  const handleTagToggle = useCallback(
    (tagId: string) => {
      setDynamicFilter((prev) => ({
        ...prev,
        tagIds: prev.tagIds.includes(tagId)
          ? prev.tagIds.filter((id) => id !== tagId)
          : [...prev.tagIds, tagId],
      }))
    },
    [],
  )

  const handleClearTags = useCallback(() => {
    setDynamicFilter((prev) => ({ ...prev, tagIds: [] }))
  }, [])

  // 分组标签
  const filteredTags = tags.filter(
    (t) =>
      !tagSearchKeyword ||
      t.name.includes(tagSearchKeyword) ||
      t.group_name.includes(tagSearchKeyword),
  )

  // 全部标签分组
  const allTagsGroup: TagItem[] = []
  const groupMap = new Map<string, { group: TagGroup; tags: TagItem[] }>()

  for (const t of filteredTags) {
    allTagsGroup.push(t)
    const gid = t.group_id || '__none__'
    if (!groupMap.has(gid)) {
      const tg = tagGroups.find((g) => g.id === gid)
      groupMap.set(gid, {
        group: tg || { id: gid, name: t.group_name || '未分组', is_hot: false },
        tags: [],
      })
    }
    groupMap.get(gid)!.tags.push(t)
  }

  // 排序：热门组优先
  const sortedGroups = [...groupMap.entries()].sort((a, b) => {
    if (a[1].group.is_hot && !b[1].group.is_hot) return -1
    if (!a[1].group.is_hot && b[1].group.is_hot) return 1
    return 0
  })

  // ---- 当前页勾选状态 ----
  const currentPageIds = sessions.map((s) => s.id)
  const allCurrentChecked =
    currentPageIds.length > 0 && currentPageIds.every((id) => selectedSessionIds.includes(id))
  const someCurrentChecked = currentPageIds.some((id) => selectedSessionIds.includes(id))

  // ---- 跨页全选的已选会话数 ----
  const selectedCount = selectAllAcrossPages ? total : selectedSessionIds.length

  // ---- 渲染 ----
  return (
    <div className="target-selector">
      {/* Tabs */}
      <div className="target-tabs">
        <button
          className={`target-tab ${activeTab === 'static' ? 'active' : ''}`}
          onClick={() => setActiveTab('static')}
        >
          静态选择
        </button>
        <button
          className={`target-tab ${activeTab === 'dynamic' ? 'active' : ''}`}
          onClick={() => setActiveTab('dynamic')}
        >
          动态选择
        </button>
        <button
          className={`target-tab ${activeTab === 'group' ? 'active' : ''}`}
          onClick={() => setActiveTab('group')}
        >
          通过客户分组选择
        </button>
      </div>

      {/* 静态选择 */}
      {activeTab === 'static' && (
        <div className="target-panel">
          {/* 筛选栏 */}
          <div className="target-filter-bar">
            <input
              className="input"
              placeholder="相关客户"
              value={staticFilter.keyword}
              onChange={(e) => setStaticFilter((p) => ({ ...p, keyword: e.target.value }))}
              style={{ width: 140 }}
            />
            <select
              className="select"
              value={staticFilter.hostingAccountId}
              onChange={(e) => setStaticFilter((p) => ({ ...p, hostingAccountId: e.target.value }))}
            >
              <option value="">托管账号</option>
              {hostingAccounts.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.display_name}
                </option>
              ))}
            </select>
            <select
              className="select"
              value={staticFilter.hostingBotId}
              onChange={(e) => setStaticFilter((p) => ({ ...p, hostingBotId: e.target.value }))}
            >
              <option value="">AI托管机器人</option>
              {hostingBots.map((b) => (
                <option key={b.id} value={b.id}>
                  {b.name}
                </option>
              ))}
            </select>
            <select
              className="select"
              value={staticFilter.tagId}
              onChange={(e) => setStaticFilter((p) => ({ ...p, tagId: e.target.value }))}
            >
              <option value="">标签</option>
              {tags.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.name}
                </option>
              ))}
            </select>
            <select
              className="select"
              value={staticFilter.tagRelation}
              onChange={(e) =>
                setStaticFilter((p) => ({
                  ...p,
                  tagRelation: e.target.value as 'and' | 'or' | '',
                }))
              }
            >
              <option value="">标签关系</option>
              <option value="and">与</option>
              <option value="or">或</option>
            </select>
          </div>

          {/* 全选行 */}
          <div className="target-select-row">
            <label className="target-select-all">
              <input
                type="checkbox"
                checked={allCurrentChecked}
                ref={(el) => {
                  if (el) el.indeterminate = someCurrentChecked && !allCurrentChecked
                }}
                onChange={toggleAllCurrentPage}
              />
              <span>全选当前页</span>
            </label>
            <button
              className={`btn btn-sm ${selectAllAcrossPages ? 'btn-primary' : 'btn-secondary'}`}
              onClick={handleSelectAllAcrossPages}
            >
              {selectAllAcrossPages ? '取消跨页全选' : '跨页全选'}
            </button>
            <span className="target-selected-count">
              已选 <strong>{selectedCount}</strong> 个会话
            </span>
            <div style={{ marginLeft: 'auto', display: 'flex', gap: 8 }}>
              <button className="btn btn-secondary btn-sm" onClick={handleStaticReset}>
                重置
              </button>
              <button className="btn btn-primary btn-sm" onClick={handleStaticQuery}>
                <Search size={14} style={{ marginRight: 4 }} />
                查询
              </button>
            </div>
          </div>

          {/* 表格 */}
          <div className="target-table-wrapper">
            {loading ? (
              <div className="target-loading">加载中...</div>
            ) : (
              <table className="proto-table target-data-table">
                <thead>
                  <tr>
                    <th style={{ width: 40 }}>
                      <input
                        type="checkbox"
                        checked={allCurrentChecked}
                        ref={(el) => {
                          if (el) el.indeterminate = someCurrentChecked && !allCurrentChecked
                        }}
                        onChange={toggleAllCurrentPage}
                      />
                    </th>
                    <th>会话</th>
                    <th>客户昵称·备注</th>
                    <th>所属托管账号</th>
                    <th>会话类型</th>
                    <th>添加时间</th>
                    <th>当前托管状态</th>
                    <th>托管链</th>
                  </tr>
                </thead>
                <tbody>
                  {sessions.length === 0 && (
                    <tr>
                      <td colSpan={8} className="target-empty-cell">
                        暂无可用会话
                      </td>
                    </tr>
                  )}
                  {sessions.map((session) => (
                    <tr
                      key={session.id}
                      className={selectedSessionIds.includes(session.id) ? 'target-row-selected' : ''}
                    >
                      <td>
                        <input
                          type="checkbox"
                          checked={selectedSessionIds.includes(session.id)}
                          onChange={() => toggleSession(session.id)}
                        />
                      </td>
                      <td>
                        <div className="target-session-name">
                          {session.avatar && (
                            <img
                              src={session.avatar}
                              alt=""
                              className="target-avatar"
                              onError={(e) => {
                                ;(e.target as HTMLImageElement).style.display = 'none'
                              }}
                            />
                          )}
                          {session.name}
                        </div>
                      </td>
                      <td>
                        {session.customer_nickname || session.customer_remark
                          ? `${session.customer_nickname || ''}${session.customer_remark ? `·${session.customer_remark}` : ''}`
                          : '—'}
                      </td>
                      <td>{session.account_name || '—'}</td>
                      <td>
                        <span className="proto-badge proto-badge-info">
                          {sessionType === 'single' ? '单聊' : '群聊'}
                        </span>
                      </td>
                      <td>{session.add_time || '—'}</td>
                      <td>
                        <span
                          className={`proto-badge ${
                            session.hosted_status === 'hosted'
                              ? 'proto-badge-success'
                              : 'proto-badge-neutral'
                          }`}
                        >
                          {session.hosted_status === 'hosted' ? '已托管' : '未托管'}
                        </span>
                      </td>
                      <td>
                        {session.hosted_bot_name ? (
                          <span className="proto-badge proto-badge-info">{session.hosted_bot_name}</span>
                        ) : (
                          '—'
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>

          {/* 分页 */}
          {total > 0 && (
            <div className="target-pagination">
              <span className="target-pagination-info">
                共 {total} 条，第 {page} / {totalPages} 页
              </span>
              <div className="target-pagination-btns">
                <button
                  className="btn btn-sm btn-secondary"
                  disabled={page <= 1}
                  onClick={() => handlePageChange(page - 1)}
                >
                  上一页
                </button>
                {Array.from({ length: Math.min(totalPages, 7) }, (_, i) => {
                  let pageNum: number
                  if (totalPages <= 7) {
                    pageNum = i + 1
                  } else if (page <= 4) {
                    pageNum = i + 1
                  } else if (page >= totalPages - 3) {
                    pageNum = totalPages - 6 + i
                  } else {
                    pageNum = page - 3 + i
                  }
                  return (
                    <button
                      key={pageNum}
                      className={`btn btn-sm ${pageNum === page ? 'btn-primary' : 'btn-secondary'}`}
                      onClick={() => handlePageChange(pageNum)}
                    >
                      {pageNum}
                    </button>
                  )
                })}
                <button
                  className="btn btn-sm btn-secondary"
                  disabled={page >= totalPages}
                  onClick={() => handlePageChange(page + 1)}
                >
                  下一页
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* 动态选择 */}
      {activeTab === 'dynamic' && (
        <div className="target-panel">
          <div className="target-filter-bar">
            <select
              className="select"
              value={dynamicFilter.hostingAccountId}
              onChange={(e) =>
                setDynamicFilter((p) => ({ ...p, hostingAccountId: e.target.value }))
              }
            >
              <option value="">托管账号</option>
              {hostingAccounts.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.display_name}
                </option>
              ))}
            </select>

            <select
              className="select"
              value={dynamicFilter.hostingBotId}
              onChange={(e) =>
                setDynamicFilter((p) => ({ ...p, hostingBotId: e.target.value }))
              }
            >
              <option value="">托管机器人</option>
              {hostingBots.map((b) => (
                <option key={b.id} value={b.id}>
                  {b.name}
                </option>
              ))}
            </select>

            <select
              className="select"
              value={dynamicFilter.tagRelation}
              onChange={(e) =>
                setDynamicFilter((p) => ({
                  ...p,
                  tagRelation: e.target.value as 'and' | 'or',
                }))
              }
            >
              <option value="and">标签关系：与</option>
              <option value="or">标签关系：或</option>
            </select>

            <button
              className="btn btn-secondary btn-sm"
              onClick={() => setShowTagModal(true)}
              style={{ display: 'flex', alignItems: 'center', gap: 4 }}
            >
              <Search size={14} />
              标签
              {dynamicFilter.tagIds.length > 0 && (
                <span className="target-tag-count-badge">{dynamicFilter.tagIds.length}</span>
              )}
            </button>
          </div>

          {/* 已选标签 chips */}
          {dynamicFilter.tagIds.length > 0 && (
            <div className="target-tag-chips">
              {dynamicFilter.tagIds.map((tid) => {
                const tag = tags.find((t) => t.id === tid)
                return tag ? (
                  <span key={tid} className="target-tag-chip">
                    {tag.name}
                    <button
                      className="target-tag-chip-remove"
                      onClick={() => handleTagToggle(tid)}
                    >
                      <X size={12} />
                    </button>
                  </span>
                ) : null
              })}
              <button className="btn btn-ghost btn-sm" onClick={handleClearTags}>
                清除
              </button>
            </div>
          )}

          {/* 条件匹配提示 */}
          <div className="target-dynamic-hint">
            当前条件将匹配 <strong>{total}</strong> 个会话
          </div>
        </div>
      )}

      {/* 通过客户分组选择 */}
      {activeTab === 'group' && <GroupTab selectedIds={selectedGroupIds} onChange={onGroupChange} />}

      {/* 标签选择弹窗 */}
      {showTagModal && (
        <div
          className="tag-modal-overlay"
          onClick={(e) => {
            if (e.target === e.currentTarget) setShowTagModal(false)
          }}
        >
          <div className="tag-modal" ref={tagModalRef}>
            <div className="tag-modal-header">
              <span className="tag-modal-title">选择标签</span>
              <button
                className="btn btn-ghost btn-sm"
                onClick={() => setShowTagModal(false)}
                style={{ padding: 4 }}
              >
                <X size={18} />
              </button>
            </div>

            {/* 搜索 */}
            <div className="tag-modal-search">
              <Search size={14} style={{ color: 'var(--text-tertiary)' }} />
              <input
                className="input"
                placeholder="搜索标签"
                value={tagSearchKeyword}
                onChange={(e) => setTagSearchKeyword(e.target.value)}
                style={{ border: 'none', flex: 1, outline: 'none' }}
              />
            </div>

            {/* 全部标签 */}
            <div className="tag-modal-body">
              {allTagsGroup.length > 0 && (
                <div className="tag-modal-group">
                  <div className="tag-modal-group-title">全部标签</div>
                  <div className="tag-modal-tags">
                    {allTagsGroup.map((tag) => (
                      <label key={tag.id} className="tag-modal-tag-item">
                        <input
                          type="checkbox"
                          checked={dynamicFilter.tagIds.includes(tag.id)}
                          onChange={() => handleTagToggle(tag.id)}
                        />
                        <span className={`tag-dot tag-dot-${tag.color || 'blue'}`} />
                        {tag.name}
                      </label>
                    ))}
                  </div>
                </div>
              )}

              {/* 分组标签 */}
              {sortedGroups.map(([gid, { group, tags: groupTags }]) => (
                <div key={gid} className="tag-modal-group">
                  <div className="tag-modal-group-title">{group.name}</div>
                  <div className="tag-modal-tags">
                    {groupTags.map((tag) => (
                      <label key={tag.id} className="tag-modal-tag-item">
                        <input
                          type="checkbox"
                          checked={dynamicFilter.tagIds.includes(tag.id)}
                          onChange={() => handleTagToggle(tag.id)}
                        />
                        <span className={`tag-dot tag-dot-${tag.color || 'blue'}`} />
                        {tag.name}
                      </label>
                    ))}
                  </div>
                </div>
              ))}
            </div>

            {/* 底部操作 */}
            <div className="tag-modal-footer">
              <button className="btn btn-secondary btn-sm" onClick={handleClearTags}>
                清除
              </button>
              <span className="tag-modal-selected-count">
                已选 {dynamicFilter.tagIds.length} 个标签
              </span>
              <button
                className="btn btn-primary btn-sm"
                onClick={() => setShowTagModal(false)}
              >
                确定
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

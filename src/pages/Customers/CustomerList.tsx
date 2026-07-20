import { useCallback, useEffect, useRef, useState } from 'react'
import { Upload, ChevronLeft, ChevronRight, Plus, ChevronDown } from 'lucide-react'
import Button from '../../components/common/Button'
import { customersApi, customerGroupsApi } from '../../api/client'
import type { CustomerListItem, CustomerGroupDTO } from '../../types/customers'
import { toast } from '../../utils/toast'
import CustomerFilterPopover from './CustomerFilterPopover'
import CustomerDetailDrawer from './CustomerDetailDrawer'
import CardImportModal from './CardImportModal'
import CustomerTagModal from './CustomerTagModal'
import CustomerGroupCreateModal from './CustomerGroupCreateModal'
import '../../pages/prototype.css'
import './Customers.css'

const PAGE_SIZE_OPTS = [10, 20, 50]
const AVATAR_COLORS = [
  '#ef4444', '#e8a649', '#4A90D9', '#7fb069', '#8b5cf6',
  '#ec4899', '#14b8a6', '#f59e0b', '#06b6d4', '#84cc16',
]

function avatarColor(name: string): string {
  let hash = 0
  for (let i = 0; i < (name || '').length; i++) hash = name.charCodeAt(i) + ((hash << 5) - hash)
  return AVATAR_COLORS[Math.abs(hash) % AVATAR_COLORS.length]
}

function fillEmpty(v: string | undefined | null): string {
  return v || '--'
}

const CHANNEL_GROUPS = [
  { label: '企业微信', accounts: ['全选', '恒康倍力'] },
  { label: '微信', accounts: ['全选', '通天草-健康', '竹绿-健康'] },
  { label: 'WhatsApp', accounts: ['全选'] },
]

export default function CustomerListPage() {
  // Tab
  const [tab, setTab] = useState<'external' | 'internal'>('external')

  // Data
  const [items, setItems] = useState<CustomerListItem[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)

  // Filters
  const [keyword, setKeyword] = useState('')
  const [appliedKeyword, setAppliedKeyword] = useState('')
  const [channelFilter, setChannelFilter] = useState('触达渠道')
  const [filterOpen, setFilterOpen] = useState(false)

  // Pagination
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(10)

  // Selection
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())

  // Modals
  const [drawerId, setDrawerId] = useState<string | null>(null)
  const [cardImportOpen, setCardImportOpen] = useState(false)
  const [tagModalOpen, setTagModalOpen] = useState(false)
  const [groupCreateOpen, setGroupCreateOpen] = useState(false)

  // Group dropdown
  const [groupDropdownOpen, setGroupDropdownOpen] = useState(false)
  const [groupList, setGroupList] = useState<CustomerGroupDTO[]>([])
  const groupDropdownRef = useRef<HTMLDivElement>(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const res = await customersApi.list({
        type: tab,
        keyword: appliedKeyword || undefined,
        page,
        pageSize,
      })
      setItems(res.items || [])
      setTotal(res.total || 0)
    } catch {
      setItems([])
      setTotal(0)
      toast('加载客户列表失败')
    } finally {
      setLoading(false)
    }
  }, [tab, appliedKeyword, page, pageSize])

  useEffect(() => {
    load()
  }, [load])

  // Load groups for dropdown
  useEffect(() => {
    customerGroupsApi.list().then(setGroupList).catch(() => setGroupList([]))
  }, [])

  // Click-away for group dropdown
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (groupDropdownRef.current && !groupDropdownRef.current.contains(e.target as Node)) {
        setGroupDropdownOpen(false)
      }
    }
    if (groupDropdownOpen) document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [groupDropdownOpen])

  // ---- Batch action helpers ----

  const selectedItems = items.filter((i) => selectedIds.has(i.id))
  const selectedContactIds = selectedItems.map((i) => i.contactId)
  const selectedProfileIds = selectedItems.map((i) => i.id)
  const selectedNames = selectedItems.map((i) => i.name)

  const handleBatchAddTag = () => {
    if (selectedItems.length === 0) return
    setTagModalOpen(true)
  }

  const handleBatchViewProfile = () => {
    if (selectedItems.length === 0) return
    // Open drawer for the first selected customer; user can navigate
    setDrawerId(selectedItems[0].contactId)
  }

  const handleBatchEnableAI = async () => {
    if (selectedContactIds.length === 0) return
    try {
      await customersApi.batchUpdateAiSummary({ contactIds: selectedContactIds, enabled: true })
      toast('已批量开启 AI 沟通总结')
      setSelectedIds(new Set())
      load()
    } catch {
      toast('操作失败')
    }
  }

  const handleBatchDisableAI = async () => {
    if (selectedContactIds.length === 0) return
    try {
      await customersApi.batchUpdateAiSummary({ contactIds: selectedContactIds, enabled: false })
      toast('已批量关闭 AI 沟通总结')
      setSelectedIds(new Set())
      load()
    } catch {
      toast('操作失败')
    }
  }

  const handleAddToExistingGroup = async (groupId: string) => {
    setGroupDropdownOpen(false)
    if (selectedProfileIds.length === 0) return
    try {
      await customerGroupsApi.addMembers(groupId, { contactIds: selectedProfileIds })
      toast('已添加到分组')
      setSelectedIds(new Set())
    } catch {
      toast('添加失败')
    }
  }

  const handleSearch = () => {
    setAppliedKeyword(keyword)
    setPage(1)
  }

  const handleReset = () => {
    setKeyword('')
    setAppliedKeyword('')
    setChannelFilter('触达渠道')
    setPage(1)
  }

  const handleAIToggle = async (item: CustomerListItem) => {
    try {
      await customersApi.updateProfile(item.contactId, {
        aiSummaryEnabled: !item.aiSummaryEnabled,
      })
      load()
    } catch {
      toast('更新失败')
    }
  }

  const handleTabChange = (t: 'external' | 'internal') => {
    setTab(t)
    setPage(1)
    setSelectedIds(new Set())
  }

  const toggleSelectAll = () => {
    if (selectedIds.size === items.length) {
      setSelectedIds(new Set())
    } else {
      setSelectedIds(new Set(items.map((i) => i.id)))
    }
  }

  const toggleSelect = (id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) { next.delete(id) } else { next.add(id) }
      return next
    })
  }

  const totalPages = Math.max(1, Math.ceil(total / pageSize))
  const hasMore = page < totalPages

  // Generate page buttons
  const pageButtons: number[] = []
  if (totalPages <= 7) {
    for (let i = 1; i <= totalPages; i++) pageButtons.push(i)
  } else {
    pageButtons.push(1)
    if (page > 3) pageButtons.push(-1)
    for (let i = Math.max(2, page - 1); i <= Math.min(totalPages - 1, page + 1); i++) pageButtons.push(i)
    if (page < totalPages - 2) pageButtons.push(-2)
    pageButtons.push(totalPages)
  }

  const startItem = (page - 1) * pageSize + 1
  const endItem = Math.min(page * pageSize, total)

  return (
    <div className="proto-page">
      <div className="proto-card customer-list">
        {/* Tabs */}
        <div className="tabs" style={{ display: 'flex', marginBottom: 12, borderBottom: '1px solid var(--border)' }}>
          <div
            className={`tab${tab === 'external' ? ' active' : ''}`}
            onClick={() => handleTabChange('external')}
            style={{ padding: '8px 16px', cursor: 'pointer', borderBottom: tab === 'external' ? '2px solid var(--primary)' : '2px solid transparent', color: tab === 'external' ? 'var(--primary)' : 'var(--text-secondary)', fontWeight: 500, fontSize: 14 }}
          >
            外部客户
          </div>
          <div
            className={`tab${tab === 'internal' ? ' active' : ''}`}
            onClick={() => handleTabChange('internal')}
            style={{ padding: '8px 16px', cursor: 'pointer', borderBottom: tab === 'internal' ? '2px solid var(--primary)' : '2px solid transparent', color: tab === 'internal' ? 'var(--primary)' : 'var(--text-secondary)', fontWeight: 500, fontSize: 14 }}
          >
            内部成员
          </div>
        </div>

        {/* Filter Bar */}
        <div className="filter-bar">
          <input
            className="input"
            placeholder="搜索..."
            style={{ width: 180 }}
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') handleSearch() }}
          />
          <div className="import-select" style={{ minWidth: 120, position: 'relative' }}>
            <div
              className="import-select-trigger"
              style={{ padding: '6px 12px', border: '1px solid var(--border)', borderRadius: 4, cursor: 'pointer', fontSize: 13 }}
              onClick={() => {
                const dd = document.getElementById('channel-dropdown')
                if (dd) dd.style.display = dd.style.display === 'block' ? 'none' : 'block'
              }}
            >
              {channelFilter}
            </div>
            <div
              id="channel-dropdown"
              className="import-select-dropdown"
              style={{ display: 'none', position: 'absolute', top: '100%', left: 0, zIndex: 60, background: '#fff', border: '1px solid var(--border)', borderRadius: 4, minWidth: 180, boxShadow: '0 4px 12px rgba(0,0,0,0.1)', padding: '4px 0' }}
            >
              {CHANNEL_GROUPS.map((g) => (
                <div key={g.label}>
                  <div style={{ padding: '4px 12px', fontSize: 11, color: 'var(--text-tertiary)', fontWeight: 600 }}>{g.label}</div>
                  {g.accounts.map((a) => (
                    <div
                      key={a}
                      style={{ padding: '6px 12px', fontSize: 13, cursor: 'pointer', color: 'var(--text-primary)' }}
                      onClick={() => {
                        setChannelFilter(a === '全选' ? g.label : a)
                        const dd = document.getElementById('channel-dropdown')
                        if (dd) dd.style.display = 'none'
                      }}
                      onMouseEnter={(e) => (e.currentTarget.style.background = '#f5f5f5')}
                      onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
                    >
                      {a}
                    </div>
                  ))}
                </div>
              ))}
            </div>
          </div>
          <CustomerFilterPopover open={filterOpen} onToggle={() => setFilterOpen(!filterOpen)} />
          <Button variant="secondary" size="sm" onClick={handleReset}>重置</Button>
          <Button variant="primary" size="sm" onClick={handleSearch}>搜索</Button>
          <Button
            variant="primary"
            size="sm"
            style={{ marginLeft: 'auto' }}
            icon={<Upload size={14} />}
            onClick={() => setCardImportOpen(true)}
          >
            名片导入
          </Button>
        </div>

        {/* Batch Toolbar — appears when ≥1 customer selected */}
        {selectedIds.size > 0 && (
          <div className="batch-toolbar">
            <div className="batch-toolbar-left">
              {/* 跨页全选 */}
              <label className="batch-checkbox-label">
                <input
                  type="checkbox"
                  checked={items.length > 0 && selectedIds.size === items.length}
                  onChange={toggleSelectAll}
                />
                <span>跨页全选</span>
              </label>

              {/* + 添加标签 */}
              <button className="batch-btn" onClick={handleBatchAddTag}>
                <Plus size={14} /> 添加标签
              </button>

              {/* 客户背景 */}
              <button className="batch-btn" onClick={handleBatchViewProfile}>
                客户背景
              </button>

              {/* 开启AI沟通总结 */}
              <button className="batch-btn" onClick={handleBatchEnableAI}>
                开启AI沟通总结
              </button>

              {/* 关闭AI沟通总结 */}
              <button className="batch-btn" onClick={handleBatchDisableAI}>
                关闭AI沟通总结
              </button>

              {/* 已选中客户数 */}
              <span className="batch-count">
                已选中客户数：{selectedIds.size}
              </span>
            </div>

            <div className="batch-toolbar-right" ref={groupDropdownRef}>
              {/* 群总分组下拉 */}
              <button
                className="batch-btn batch-group-btn"
                onClick={() => {
                  setGroupDropdownOpen(!groupDropdownOpen)
                  // Refresh group list
                  customerGroupsApi.list().then(setGroupList).catch(() => {})
                }}
              >
                添加到群总分组 <ChevronDown size={14} />
              </button>

              {groupDropdownOpen && (
                <div className="batch-group-dropdown">
                  {/* 创建新群总分组 */}
                  <div
                    className="batch-group-item batch-group-item-primary"
                    onClick={() => {
                      setGroupDropdownOpen(false)
                      setGroupCreateOpen(true)
                    }}
                  >
                    <Plus size={14} /> 创建新群总分组
                  </div>

                  {/* 添加到已有群总分组 */}
                  <div className="batch-group-section-title">添加到已有群总分组</div>
                  {groupList.length === 0 ? (
                    <div className="batch-group-item text-secondary" style={{ fontSize: 12 }}>
                      暂无分组
                    </div>
                  ) : (
                    groupList.map((g) => (
                      <div
                        key={g.id}
                        className="batch-group-item"
                        onClick={() => handleAddToExistingGroup(g.id)}
                      >
                        <span>{g.name}</span>
                        <span className="text-secondary" style={{ fontSize: 11 }}>
                          {g.count} 人
                        </span>
                      </div>
                    ))
                  )}

                  {/* 筛选条件为动态分组 */}
                  <div className="batch-group-divider" />
                  <div
                    className="batch-group-item text-secondary"
                    style={{ fontSize: 12, fontStyle: 'italic', cursor: 'default' }}
                  >
                    筛选条件为动态分组 →
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Select-all row */}
        <div className="bulk-row">
          <input
            type="checkbox"
            checked={items.length > 0 && selectedIds.size === items.length}
            onChange={toggleSelectAll}
          />
          <span>跨页全选</span>
        </div>

        {/* Tables */}
        <div className="table-wrap" style={{ overflowX: 'auto' }}>
          {tab === 'external' ? (
            <table className="table" style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr>
                  <th style={{ width: 32 }}><input type="checkbox" /></th>
                  <th>客户名</th>
                  <th>所属私域账号</th>
                  <th>是否开启AI总结</th>
                  <th>最后沟通时间</th>
                  <th>最后沟通记录</th>
                  <th>添加时间</th>
                  <th>标签</th>
                  <th>备注</th>
                  <th>操作</th>
                </tr>
              </thead>
              <tbody>
                {loading ? (
                  <tr><td colSpan={10} style={{ textAlign: 'center', padding: 40, color: 'var(--text-tertiary)' }}>加载中...</td></tr>
                ) : items.length === 0 ? (
                  <tr><td colSpan={10} style={{ textAlign: 'center', padding: 40, color: 'var(--text-tertiary)' }}>暂无数据</td></tr>
                ) : (
                  items.map((item) => (
                    <tr key={item.id} onClick={(e) => {
                      const target = e.target as HTMLElement
                      if (target.tagName === 'INPUT' || target.closest('button') || target.closest('.switch')) return
                      setDrawerId(item.contactId)
                    }} style={{ cursor: 'pointer' }}>
                      <td>
                        <input
                          type="checkbox"
                          checked={selectedIds.has(item.id)}
                          onChange={() => toggleSelect(item.id)}
                          onClick={(e) => e.stopPropagation()}
                        />
                      </td>
                      <td>
                        <div className="customer-name-cell">
                          <div className="avatar" style={{ background: avatarColor(item.name) }}>
                            {item.name.slice(0, 1)}
                          </div>
                          <div className="customer-name-text">
                            <span className="name">{item.name}</span>
                            <span className="note">{item.nickname || item.name}@{item.channel}</span>
                          </div>
                        </div>
                      </td>
                      <td><span className="customer-channel">{fillEmpty(item.accountId)}</span></td>
                      <td>
                        <label className="switch" onClick={(e) => e.stopPropagation()}>
                          <input
                            type="checkbox"
                            checked={item.aiSummaryEnabled}
                            onChange={() => handleAIToggle(item)}
                          />
                          <span className="slider" />
                        </label>
                      </td>
                      <td style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
                        {fillEmpty(item.lastCommunicationTime)}
                      </td>
                      <td>
                        {item.lastCommunicationAiSummary ? (
                          <div className="customer-last-msg has-summary">
                            <span className="ai-label">AI总结:</span>
                            {item.lastCommunicationAiSummary.slice(0, 60)}...
                            <div className="ai-summary-popover">
                              <div className="title">AI总结</div>
                              <div>{item.lastCommunicationAiSummary}</div>
                            </div>
                          </div>
                        ) : item.lastCommunicationContent ? (
                          <div className="customer-last-msg">
                            {item.lastCommunicationContent.slice(0, 40)}
                          </div>
                        ) : (
                          <span style={{ color: 'var(--text-tertiary)' }}>-</span>
                        )}
                      </td>
                      <td style={{ fontSize: 13, color: 'var(--text-secondary)' }}>{fillEmpty(item.addTime)}</td>
                      <td>
                        {item.tags && item.tags.length > 0 ? (
                          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                            {item.tags.slice(0, 3).map((t) => (
                              <span key={t.id} className="tag-chip" style={{ fontSize: 11, padding: '2px 6px' }}>
                                {t.name}
                              </span>
                            ))}
                            {item.tags.length > 3 && (
                              <span className="tag-chip" style={{ fontSize: 11, padding: '2px 6px' }}>
                                +{item.tags.length - 3}
                              </span>
                            )}
                          </div>
                        ) : (
                          <span style={{ color: 'var(--text-tertiary)' }}>-</span>
                        )}
                      </td>
                      <td style={{ fontSize: 13, color: 'var(--text-secondary)', maxWidth: 120, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {fillEmpty(item.remark)}
                      </td>
                      <td>
                        <span
                          className="customer-op"
                          onClick={(e) => {
                            e.stopPropagation()
                            setDrawerId(item.contactId)
                          }}
                        >
                          详情
                        </span>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          ) : (
            <table className="table" style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr>
                  <th>内部成员</th>
                  <th>所属渠道</th>
                </tr>
              </thead>
              <tbody>
                {loading ? (
                  <tr><td colSpan={2} style={{ textAlign: 'center', padding: 40, color: 'var(--text-tertiary)' }}>加载中...</td></tr>
                ) : items.length === 0 ? (
                  <tr><td colSpan={2} style={{ textAlign: 'center', padding: 40, color: 'var(--text-tertiary)' }}>暂无数据</td></tr>
                ) : (
                  items.map((item) => (
                    <tr key={item.id} onClick={() => setDrawerId(item.contactId)} style={{ cursor: 'pointer' }}>
                      <td>
                        <div className="customer-member-cell">
                          <div className="avatar" style={{ background: avatarColor(item.name), width: 32, height: 32, borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#fff', fontSize: 14, fontWeight: 600 }}>
                            {item.name.slice(0, 1)}
                          </div>
                          <span style={{ fontWeight: 500 }}>{item.name}@医林通</span>
                        </div>
                      </td>
                      <td><span className="customer-channel">{fillEmpty(item.accountId)}</span></td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          )}
        </div>

        {/* Pagination */}
        <div className="customer-pagination">
          <span>第 {startItem}-{endItem} 条/共 {total} 条</span>
          <div className="customer-pagination-pages">
            <button disabled={page <= 1} onClick={() => setPage(p => Math.max(1, p - 1))}>
              <ChevronLeft size={12} />
            </button>
            {pageButtons.map((n, i) =>
              n < 0 ? (
                <button key={`dot-${i}`} disabled>...</button>
              ) : (
                <button key={n} className={n === page ? 'active' : ''} onClick={() => setPage(n)}>
                  {n}
                </button>
              )
            )}
            <button disabled={!hasMore} onClick={() => setPage(p => p + 1)}>
              <ChevronRight size={12} />
            </button>
          </div>
          <div className="customer-page-size">
            <select value={pageSize} onChange={(e) => { setPageSize(Number(e.target.value)); setPage(1) }}>
              {PAGE_SIZE_OPTS.map((n) => (
                <option key={n} value={n}>{n}条/页</option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {/* Drawer */}
      <CustomerDetailDrawer contactId={drawerId} onClose={() => setDrawerId(null)} />

      {/* Card Import Modal */}
      <CardImportModal open={cardImportOpen} onClose={() => setCardImportOpen(false)} />

      {/* Batch Tag Modal — batch mode when multiple customers selected */}
      {tagModalOpen && selectedItems.length > 0 && (
        <CustomerTagModal
          open={tagModalOpen}
          customerId={selectedItems[0].contactId}
          initialTagIds={[]}
          onClose={() => setTagModalOpen(false)}
          onSaved={() => {
            setSelectedIds(new Set())
            load()
          }}
          batchMode
          batchCustomerIds={selectedProfileIds}
        />
      )}

      {/* Group Create Modal */}
      <CustomerGroupCreateModal
        open={groupCreateOpen}
        selectedCustomers={selectedNames.map((name, i) => ({
          id: selectedProfileIds[i],
          name,
        }))}
        onClose={() => setGroupCreateOpen(false)}
        onSaved={() => {
          setSelectedIds(new Set())
          load()
        }}
      />
    </div>
  )
}

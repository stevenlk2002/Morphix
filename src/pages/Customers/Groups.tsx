import { useEffect, useMemo, useState } from 'react'
import { Folder, UsersRound, X } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import Button from '../../components/common/Button'
import { customerGroupsApi } from '../../api/client'
import type { CustomerGroupDTO, CustomerGroupWithMembersDTO, CustomerGroupMemberDetail } from '../../types/customers'
import '../../pages/prototype.css'
import './Groups.css'

/** 类型筛选可选项。 */
const TYPE_OPTIONS: Array<{ value: string; label: string }> = [
  { value: '', label: '请选择' },
  { value: 'system', label: '系统' },
  { value: 'custom', label: '自定义' },
]

/** 类型中文展示。 */
const TYPE_LABEL: Record<string, string> = {
  system: '系统',
  custom: '自定义',
}

/** 根据类型返回徽标样式类名。 */
function typeBadgeClass(type: string): string {
  return type === 'system' ? 'proto-badge-info' : 'proto-badge-success'
}

/** 头像颜色算法。 */
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

/**
 * 客户分组管理页（/customers/groups）。
 *
 * 功能：
 * - 行 checkbox + 表头全选 / 跨页全选
 * - 批量工具栏（选中 ≥1 显示）：跨页全选 + 删除 + 已选中计数
 * - 删除按钮 → confirm 弹窗 → 调批量删除 API → 刷新列表
 * - 行点击 → 打开详情抽屉（从右侧滑入，~50% 视口宽）
 * - 抽屉内展示该分组的成员客户列表（含聚合数据）
 */
export default function CustomerGroupsPage() {
  const navigate = useNavigate()

  // ---- 数据 ----
  const [groups, setGroups] = useState<CustomerGroupDTO[]>([])
  const [loading, setLoading] = useState(true)

  const refreshGroups = () => {
    setLoading(true)
    customerGroupsApi
      .list()
      .then((data) => setGroups(data))
      .catch(() => setGroups([]))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    refreshGroups()
  }, [])

  // ---- 筛选 ----
  const [nameInput, setNameInput] = useState('')
  const [typeInput, setTypeInput] = useState('')
  const [appliedName, setAppliedName] = useState('')
  const [appliedType, setAppliedType] = useState('')

  const filtered = useMemo(() => {
    const kw = appliedName.trim().toLowerCase()
    return groups.filter((g) => {
      if (kw && !g.name.toLowerCase().includes(kw)) return false
      if (appliedType && g.type !== appliedType) return false
      return true
    })
  }, [groups, appliedName, appliedType])

  const handleQuery = () => {
    setAppliedName(nameInput)
    setAppliedType(typeInput)
  }

  const handleReset = () => {
    setNameInput('')
    setTypeInput('')
    setAppliedName('')
    setAppliedType('')
  }

  // ---- 选择 ----
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())

  const toggleSelect = (id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const toggleSelectAll = () => {
    if (filtered.length > 0 && selectedIds.size === filtered.length) {
      setSelectedIds(new Set())
    } else {
      setSelectedIds(new Set(filtered.map((g) => g.id)))
    }
  }

  const clearSelection = () => setSelectedIds(new Set())

  // ---- 删除 ----
  const [deleting, setDeleting] = useState(false)

  const handleDelete = () => {
    if (selectedIds.size === 0) return
    const ok = window.confirm(
      `确定要删除选中的 ${selectedIds.size} 个客户分组吗？\n删除后不可恢复，请确认操作。`
    )
    if (!ok) return
    setDeleting(true)
    customerGroupsApi
      .delete(Array.from(selectedIds))
      .then(() => {
        clearSelection()
        refreshGroups()
      })
      .catch((err) => {
        alert('删除失败：' + (err?.message || '未知错误'))
      })
      .finally(() => setDeleting(false))
  }

  // ---- 详情抽屉 ----
  const [drawerGroup, setDrawerGroup] = useState<CustomerGroupWithMembersDTO | null>(null)
  const [drawerLoading, setDrawerLoading] = useState(false)

  const openDrawer = (id: string) => {
    setDrawerLoading(true)
    setDrawerGroup(null)
    customerGroupsApi
      .getWithMembers(id)
      .then((data) => setDrawerGroup(data))
      .catch(() => setDrawerGroup(null))
      .finally(() => setDrawerLoading(false))
  }

  const closeDrawer = () => {
    setDrawerGroup(null)
    setDrawerLoading(false)
  }

  // ---- 渲染 ----
  return (
    <div className="proto-page">
      <div className="proto-card">
        <div className="groups-tip proto-tip">
          <UsersRound size={16} />
          <span>
            新建客户分组请前往
            <span
              className="groups-tip-link"
              style={{ cursor: 'pointer', color: 'var(--primary)' }}
              onClick={() => navigate('/customers')}
            >
              客户列表
            </span>
            进行选择后，保存客户分组
          </span>
        </div>

        <div className="groups-filter-bar">
          <div className="form-group groups-filter-item">
            <label className="form-label">客户分组：</label>
            <input
              className="input"
              type="text"
              placeholder="请输入"
              value={nameInput}
              onChange={(e) => setNameInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') handleQuery()
              }}
            />
          </div>

          <div className="form-group groups-filter-item">
            <label className="form-label">类型：</label>
            <select
              className="select"
              value={typeInput}
              onChange={(e) => setTypeInput(e.target.value)}
            >
              {TYPE_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>

          <div className="groups-filter-actions">
            <Button variant="secondary" size="sm" onClick={handleReset}>
              重置
            </Button>
            <Button
              variant="primary"
              size="sm"
              className="btn-query"
              icon={<Folder size={14} />}
              onClick={handleQuery}
            >
              查询
            </Button>
          </div>
        </div>

        {/* ---- Batch Toolbar ---- */}
        {selectedIds.size > 0 && (
          <div className="batch-toolbar">
            <div className="batch-toolbar-left">
              <label className="batch-checkbox-label">
                <input
                  type="checkbox"
                  checked={filtered.length > 0 && selectedIds.size === filtered.length}
                  onChange={toggleSelectAll}
                />
                <span>跨页全选</span>
              </label>

              <button
                className="batch-btn batch-btn-danger"
                onClick={handleDelete}
                disabled={deleting}
              >
                {deleting ? '删除中...' : '🗑 删除'}
              </button>

              <span className="batch-count">
                已选中客户分组数：{selectedIds.size}
              </span>
            </div>
          </div>
        )}

        {loading ? (
          <div className="groups-empty">
            <p className="groups-empty-text">加载中...</p>
          </div>
        ) : filtered.length === 0 ? (
          <div className="groups-empty">
            <Folder size={48} className="groups-empty-icon" />
            <p className="groups-empty-text">暂无数据</p>
          </div>
        ) : (
          <table className="proto-table">
            <thead>
              <tr>
                <th style={{ width: 36 }}>
                  <input
                    type="checkbox"
                    checked={filtered.length > 0 && selectedIds.size === filtered.length}
                    onChange={toggleSelectAll}
                  />
                </th>
                <th>客户分组</th>
                <th>类型</th>
                <th className="groups-num-col">当前客户数</th>
                <th>创建时间</th>
                <th>编辑时间</th>
                <th>编辑人</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((g) => (
                <tr
                  key={g.id}
                  className="groups-row-clickable"
                  onClick={(e) => {
                    const target = e.target as HTMLElement
                    if (target.tagName === 'INPUT') return
                    openDrawer(g.id)
                  }}
                >
                  <td onClick={(e) => e.stopPropagation()}>
                    <input
                      type="checkbox"
                      checked={selectedIds.has(g.id)}
                      onChange={() => toggleSelect(g.id)}
                    />
                  </td>
                  <td>{g.name}</td>
                  <td>
                    <span className={`proto-badge ${typeBadgeClass(g.type)}`}>
                      {TYPE_LABEL[g.type] || g.type}
                    </span>
                  </td>
                  <td className="groups-num-cell">{g.count}</td>
                  <td className="text-secondary">{g.createdAt}</td>
                  <td className="text-secondary">{g.updatedAt}</td>
                  <td>{g.editor}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* ---- Detail Drawer ---- */}
      {drawerGroup !== null && (
        <div className="groups-drawer-overlay" onClick={closeDrawer}>
          <div
            className="groups-drawer"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Drawer Header */}
            <div className="groups-drawer-header">
              <h3 className="groups-drawer-title">客户分组详情</h3>
              <button className="groups-drawer-close" onClick={closeDrawer}>
                <X size={20} />
              </button>
            </div>

            {/* Drawer Body */}
            <div className="groups-drawer-body">
              {/* Group metadata */}
              <div className="groups-drawer-meta">
                <span className="groups-drawer-group-name">{drawerGroup.name}</span>
                <span className={`proto-badge ${typeBadgeClass(drawerGroup.type)}`}>
                  {TYPE_LABEL[drawerGroup.type] || drawerGroup.type}
                </span>
              </div>

              {/* Members table */}
              {drawerLoading ? (
                <div className="groups-empty">
                  <p className="groups-empty-text">加载中...</p>
                </div>
              ) : drawerGroup.members.length === 0 ? (
                <div className="groups-empty">
                  <Folder size={36} className="groups-empty-icon" />
                  <p className="groups-empty-text">暂无成员</p>
                </div>
              ) : (
                <div className="groups-drawer-table-wrap">
                  <table className="proto-table">
                    <thead>
                      <tr>
                        <th style={{ width: 32 }}></th>
                        <th>客户名</th>
                        <th>所属私域账号</th>
                        <th>最后沟通时间</th>
                        <th>最后沟通记录</th>
                        <th>添加时间</th>
                        <th>标签</th>
                        <th>备注</th>
                      </tr>
                    </thead>
                    <tbody>
                      {drawerGroup.members.map((m: CustomerGroupMemberDetail) => (
                        <tr key={m.customerId}>
                          <td>
                            <input type="checkbox" />
                          </td>
                          <td>
                            <div className="customer-name-cell">
                              <div
                                className="avatar"
                                style={{ background: avatarColor(m.customerName) }}
                              >
                                {m.customerName.slice(0, 1)}
                              </div>
                              <div className="customer-name-text">
                                <span className="name">{m.customerName}</span>
                                <span className="note">
                                  {m.nickname || m.customerName}@{m.channel || '--'}
                                </span>
                              </div>
                            </div>
                          </td>
                          <td>
                            <span className="customer-channel">{fillEmpty(m.accountId)}</span>
                          </td>
                          <td style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
                            {fillEmpty(m.lastCommunicationTime)}
                          </td>
                          <td>
                            {m.lastCommunicationAiSummary ? (
                              <div className="customer-last-msg has-summary">
                                <span className="ai-label">AI总结:</span>
                                {m.lastCommunicationAiSummary.slice(0, 40)}...
                              </div>
                            ) : m.lastCommunicationContent ? (
                              <div className="customer-last-msg">
                                {m.lastCommunicationContent.slice(0, 30)}
                              </div>
                            ) : (
                              <span style={{ color: 'var(--text-tertiary)' }}>-</span>
                            )}
                          </td>
                          <td style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
                            {fillEmpty(m.addTime)}
                          </td>
                          <td>
                            {m.tags && m.tags.length > 0 ? (
                              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                                {m.tags.slice(0, 3).map((t) => (
                                  <span
                                    key={t.id}
                                    className="tag-chip"
                                    style={{ fontSize: 11, padding: '2px 6px' }}
                                  >
                                    {t.name}
                                  </span>
                                ))}
                                {m.tags.length > 3 && (
                                  <span
                                    className="tag-chip"
                                    style={{ fontSize: 11, padding: '2px 6px' }}
                                  >
                                    +{m.tags.length - 3}
                                  </span>
                                )}
                              </div>
                            ) : (
                              <span style={{ color: 'var(--text-tertiary)' }}>-</span>
                            )}
                          </td>
                          <td
                            style={{
                              fontSize: 13,
                              color: 'var(--text-secondary)',
                              maxWidth: 100,
                              overflow: 'hidden',
                              textOverflow: 'ellipsis',
                              whiteSpace: 'nowrap',
                            }}
                          >
                            {fillEmpty(m.remark)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

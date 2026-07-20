/**
 * 运营SOP列表页（/operations/sops）。
 *
 * 功能：
 * - Banner + SVG 装饰
 * - 筛选栏（搜索/类型/启用/运行状态/排序）
 * - 空态插画 + "去创建"弹 Modal（客户SOP / 群聊SOP 两张卡片）
 * - 有数据时显示卡片列表（标题+类型 badge+启用 Switch+运行状态+编辑/删除按钮）
 * - 真实 API 调用
 */
import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { Search, User, Users } from 'lucide-react'
import Button from '../../components/common/Button'
import Modal from '../../components/common/Modal'
import { sopsApi } from '../../api/sops'
import type { SopItem } from '../../types/sops'
import { SOP_TYPE_LABELS, SOP_STATUS_LABELS } from '../../types/sops'
import '../../pages/prototype.css'
import './SopList.css'

const BANNER_SVG = (
  <svg width="120" height="80" viewBox="0 0 120 80" fill="none" aria-hidden="true">
    <rect x="20" y="12" width="80" height="56" rx="8" fill="rgba(255,255,255,0.15)" />
    <rect x="32" y="24" width="56" height="8" rx="4" fill="rgba(255,255,255,0.3)" />
    <rect x="32" y="38" width="40" height="6" rx="3" fill="rgba(255,255,255,0.2)" />
    <rect x="32" y="50" width="48" height="6" rx="3" fill="rgba(255,255,255,0.2)" />
    <circle cx="92" cy="28" r="12" fill="rgba(255,255,255,0.12)" />
    <path d="M88 26l3 4 5-6" stroke="rgba(255,255,255,0.5)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
)

export default function SopListPage() {
  const navigate = useNavigate()
  const [sops, setSops] = useState<SopItem[]>([])
  const [loading, setLoading] = useState(true)

  // 筛选状态
  const [keyword, setKeyword] = useState('')
  const [typeFilter, setTypeFilter] = useState('全部')
  const [enabledFilter, setEnabledFilter] = useState('全部')
  const [runningFilter, setRunningFilter] = useState('全部')
  const [sortBy, setSortBy] = useState('创建日期-降序')

  // Modal 状态
  const [createModalOpen, setCreateModalOpen] = useState(false)

  // 卡片菜单
  const [menuOpenId, setMenuOpenId] = useState<string | null>(null)

  // 加载数据
  const loadSops = useCallback(async () => {
    setLoading(true)
    try {
      const data = await sopsApi.list({
        search: keyword || undefined,
        type: typeFilter !== '全部' ? typeFilter : undefined,
        enabled: enabledFilter !== '全部' ? enabledFilter : undefined,
        status: runningFilter !== '全部' ? runningFilter : undefined,
        sortBy,
      })
      setSops(data)
    } catch (err) {
      console.error('加载 SOP 列表失败:', err)
    } finally {
      setLoading(false)
    }
  }, [keyword, typeFilter, enabledFilter, runningFilter, sortBy])

  useEffect(() => {
    loadSops()
  }, [loadSops])

  // 创建
  const openCreate = () => setCreateModalOpen(true)

  const handleCreateChoice = (type: 'customer' | 'group') => {
    setCreateModalOpen(false)
    if (type === 'customer') {
      navigate('/operations/sops/create-customer')
    } else {
      navigate('/operations/sops/create-group')
    }
  }

  // 编辑（跳转到编辑器）
  const goEditPage = (sop: SopItem) => {
    const path = sop.type === 'group'
      ? '/operations/sops/create-group'
      : '/operations/sops/create-customer'
    navigate(`${path}?id=${sop.id}`)
  }

  const toggleEnabled = async (sop: SopItem) => {
    try {
      await sopsApi.toggle(sop.id, !sop.enabled)
      loadSops()
    } catch (err) {
      console.error('切换 SOP 状态失败:', err)
    }
  }

  const openMenu = (id: string) => setMenuOpenId(menuOpenId === id ? null : id)

  // 删除
  const deleteSop = async (sop: SopItem) => {
    if (!window.confirm(`确定删除 SOP「${sop.name}」？`)) return
    try {
      await sopsApi.delete(sop.id)
      loadSops()
    } catch (err) {
      console.error('删除 SOP 失败:', err)
    }
  }

  // 跳转编辑页（已在上面定义，此处删除重复）

  const typeBadge = (type: string) =>
    type === 'customer' ? 'proto-badge-info' : 'proto-badge-success'
  const statusBadge = (status: string) =>
    status === 'running' ? 'proto-badge-success' : 'proto-badge-neutral'

  return (
    <div className="proto-page">
      {/* Banner */}
      <div className="sop-banner">
        <div>
          <h2 className="sop-banner-title">运营SOP</h2>
          <p className="sop-banner-desc">设置自动化营销流程，实现客户/群聊高效运营</p>
        </div>
        <div className="sop-banner-right">
          {BANNER_SVG}
        </div>
      </div>

      {/* 筛选栏 */}
      <div className="sop-filter-bar">
        <div className="material-search sop-search">
          <Search size={16} className="search-icon" />
          <input
            type="text"
            placeholder="搜索 SOP 名称"
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
          />
        </div>
        <select className="select" value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)}>
          <option value="全部">全部类型</option>
          <option value="客户SOP">客户SOP</option>
          <option value="群聊SOP">群聊SOP</option>
        </select>
        <select
          className="select"
          value={enabledFilter}
          onChange={(e) => setEnabledFilter(e.target.value)}
        >
          <option value="全部">启用状态</option>
          <option value="开启">开启</option>
          <option value="停用">停用</option>
        </select>
        <select
          className="select"
          value={runningFilter}
          onChange={(e) => setRunningFilter(e.target.value)}
        >
          <option value="全部">运行状态</option>
          <option value="待运行">待运行</option>
          <option value="运行中">运行中</option>
          <option value="已完成">已完成</option>
        </select>
        <select className="select" value={sortBy} onChange={(e) => setSortBy(e.target.value)}>
          <optgroup label="排序方式">
            <option value="创建日期-降序">创建日期</option>
            <option value="修改日期-降序">修改日期</option>
            <option value="名称排序-升序">名称排序</option>
          </optgroup>
          <optgroup label="排序顺序">
            <option value="升序">升序</option>
            <option value="降序">降序</option>
          </optgroup>
        </select>
      </div>

      {/* 卡片网格 / 空态 */}
      <div className="sop-card-grid">
        {loading ? (
          <div className="sop-empty">
            <p className="sop-empty-text">加载中...</p>
          </div>
        ) : sops.length === 0 ? (
          <>
            {/* "创建 SOP" 虚线卡 + 空态 */}
            <div className="sop-card sop-card--create" onClick={openCreate}>
              <div className="sop-card-create-icon">+</div>
              <div className="sop-card-create-label">创建 SOP</div>
            </div>
            <div className="sop-empty">
              <svg width="96" height="96" viewBox="0 0 96 96" fill="none" className="sop-empty-illustration" aria-hidden="true">
                <rect x="22" y="30" width="52" height="44" rx="6" fill="#eef2ff" stroke="#c7d2fe" strokeWidth="2" />
                <rect x="34" y="22" width="28" height="14" rx="4" fill="#ffffff" stroke="#c7d2fe" strokeWidth="2" />
                <line x1="34" y1="46" x2="62" y2="46" stroke="#c7d2fe" strokeWidth="2" strokeLinecap="round" />
                <line x1="34" y1="56" x2="54" y2="56" stroke="#c7d2fe" strokeWidth="2" strokeLinecap="round" />
                <line x1="34" y1="66" x2="58" y2="66" stroke="#c7d2fe" strokeWidth="2" strokeLinecap="round" />
              </svg>
              <p className="sop-empty-text">暂无运营SOP</p>
            </div>
          </>
        ) : (
          <>
            {/* 第一个卡：创建 SOP 入口 */}
            <div className="sop-card sop-card--create" onClick={openCreate}>
              <div className="sop-card-create-icon">+</div>
              <div className="sop-card-create-label">创建 SOP</div>
            </div>
            {/* SOP 卡片 */}
            {sops.map((s) => (
              <div key={s.id} className="sop-card">
                <div className="sop-card-header">
                  <div className="sop-card-header-left">
                    <span className={`proto-badge ${typeBadge(s.type)}`}>
                      {SOP_TYPE_LABELS[s.type] || s.type}
                    </span>
                    <span className="sop-card-name">{s.name}</span>
                  </div>
                  <div className="sop-card-header-right">
                    <button
                      type="button"
                      className={`proto-switch ${s.enabled ? 'on' : ''}`}
                      role="switch"
                      aria-checked={s.enabled}
                      onClick={() => toggleEnabled(s)}
                    >
                      <span className="proto-switch-knob" />
                    </button>
                    <span className={`proto-badge ${statusBadge(s.status)} sop-card-status`}>
                      {SOP_STATUS_LABELS[s.status] || s.status}
                    </span>
                  </div>
                </div>
                <div className="sop-card-meta">
                  <span>触发类型：{s.trigger_type || '属性变化'}</span>
                  <span>客户属性：{s.type === 'group' ? '群聊触达' : '客户触达'}</span>
                </div>
                <div className="sop-card-footer">
                  <div className="sop-card-actions">
                    <Button variant="ghost" size="sm" onClick={() => goEditPage(s)}>编辑</Button>
                    <Button variant="ghost" size="sm" onClick={() => navigate(`/operations/sops/${s.id}/records`)}>运营记录</Button>
                  </div>
                  <div className="sop-card-menu-wrap">
                    <button className="sop-card-menu-btn" onClick={(e) => { e.stopPropagation(); openMenu(s.id) }} aria-label="更多操作">
                      ⋯
                    </button>
                    {menuOpenId === s.id && (
                      <div className="sop-card-menu">
                        <button onClick={() => { goEditPage(s); setMenuOpenId(null) }}>编辑</button>
                        <button onClick={() => { deleteSop(s); setMenuOpenId(null) }} className="danger">删除</button>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </>
        )}
      </div>

      {/* 创建 SOP Modal：两张卡片 */}
      <Modal
        open={createModalOpen}
        title="创建运营SOP"
        onClose={() => setCreateModalOpen(false)}
        footer={null}
      >
        <div className="sop-create-cards">
          <button
            type="button"
            className="sop-create-card"
            onClick={() => handleCreateChoice('customer')}
          >
            <div className="sop-create-card-icon">
              <User size={32} />
            </div>
            <div className="sop-create-card-title">客户SOP</div>
            <div className="sop-create-card-desc">
              针对单个客户的自动化运营流程，如新客关怀、复购唤醒等
            </div>
          </button>
          <button
            type="button"
            className="sop-create-card"
            onClick={() => handleCreateChoice('group')}
          >
            <div className="sop-create-card-icon">
              <Users size={32} />
            </div>
            <div className="sop-create-card-title">群聊SOP</div>
            <div className="sop-create-card-desc">
              针对群聊的自动化运营流程，如社群打卡、群发通知等
            </div>
          </button>
        </div>
      </Modal>
    </div>
  )
}

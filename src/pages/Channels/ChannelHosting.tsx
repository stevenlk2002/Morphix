/** 批量托管管理（ChannelHosting）：按设计稿改造 —— 多条件筛选 + 动态下拉 + 标签多选 + 数据表格。 */

import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import {
  Check,
  ChevronDown,
  Pencil,
  RefreshCw,
  Search,
} from 'lucide-react'
import { channelsApi, tagGroupsApi } from '../../api/client'
import type { AccountDTO, HostingBotDTO, HostingSessionDTO } from '../../types/channels'
import type { TagGroupDTO } from '../../types/customers'
import { avatarColor, avatarChar } from './shared/avatarUtils'
import { toast, errText } from '../../utils/toast'
import '../../pages/prototype.css'
import './Channels.css'

// ── 类型 ──
type Tab = 'batch' | 'rules'

interface AccountOption extends AccountDTO {
  label: string // "name" for display
}

interface TagOption {
  id: string       // tag id
  name: string     // tag display name
  groupId: string
  groupName: string
  fullName: string // "分组名-标签"
}

// ── 常量 ──
const SESSION_TYPES = [
  { value: '', label: '外部联系人' },
  { value: 'person', label: '外部联系人' },
  { value: 'group', label: '外部群聊' },
] as const

const TAG_RELATIONS = [
  { value: 'or', label: '或关系' },
  { value: 'and', label: '与关系' },
] as const

// ── 自定义 Select 组件（复用，避免每处手写 DOM 操作）──
function useSelect() {
  const [open, setOpen] = useState(false)

  const toggle = useCallback(
    (e?: React.MouseEvent) => {
      if (e) e.stopPropagation()
      setOpen((v) => !v)
    },
    [],
  )

  const close = useCallback(() => {
    setOpen(false)
  }, [])

  useEffect(() => {
    if (!open) return
    const handler = (e: MouseEvent) => {
      const target = e.target as HTMLElement
      if (!target.closest('.custom-select')) close()
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [open])

  return { open, toggle, close }
}

// ── 主组件 ──
export default function ChannelHostingPage() {
  const { id: accountId = '' } = useParams()
  const navigate = useNavigate()
  const [tab, setTab] = useState<Tab>('batch')

  // ── 数据列表 ──
  const [sessions, setSessions] = useState<HostingSessionDTO[]>([])
  const [bots, setBots] = useState<HostingBotDTO[]>([])
  const [accounts, setAccounts] = useState<AccountOption[]>([])
  const [tagOptions, setTagOptions] = useState<TagOption[]>([])

  const [selectedIds, setSelectedIds] = useState<string[]>([])
  const [loading, setLoading] = useState(true)

  // ── 筛选条件 ──
  const [nickname, setNickname] = useState('')
  const [selectedAccountIds, setSelectedAccountIds] = useState<string[]>([])
  const [botId, setBotId] = useState<string>('')
  const [sessionType, setSessionType] = useState('')
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')
  const [selectedTagIds, setSelectedTagIds] = useState<string[]>([])
  const [tagRelation, setTagRelation] = useState('or')

  // ── 下拉状态 ──
  const accountSelect = useSelect()
  const botSelect = useSelect()
  const sessionTypeSelect = useSelect()
  const tagRelationSelect = useSelect()
  const tagSelect = useSelect()

  // ── Bot 搜索 ──
  const [botSearch, setBotSearch] = useState('')

  // ── 批量编辑弹层 ──
  const [editOpen, setEditOpen] = useState(false)
  const [editHosted, setEditHosted] = useState<'hosted' | 'unhosted'>('hosted')
  const [editChain, setEditChain] = useState<string>('')

  // ── 规则配置 ──
  const [resume, setResume] = useState<string>('')
  const [autoCancel, setAutoCancel] = useState(false)
  const [savingRule, setSavingRule] = useState(false)

  // ── 加载函数 ──
  const loadSessions = () => {
    setLoading(true)
    const params: Record<string, string> = {}
    if (accountId) params.accountId = accountId
    if (nickname) params.nickname = nickname
    if (selectedAccountIds.length > 0) params.accountIds = selectedAccountIds.join(',')
    if (botId) params.botId = botId
    if (sessionType) params.sessionType = sessionType
    if (startDate) params.start = startDate
    if (endDate) params.end = endDate
    if (selectedTagIds.length > 0) params.tagIds = selectedTagIds.join(',')
    if (tagRelation) params.tagRelation = tagRelation

    channelsApi
      .listHostingSessions(params)
      .then(setSessions)
      .catch((e) => toast(`加载托管会话失败：${errText(e)}`))
      .finally(() => setLoading(false))
  }

  // ── 初始化加载 ──
  useEffect(() => {
    // 渠道账号列表
    channelsApi
      .listAccounts()
      .then((list) =>
        setAccounts(
          list.map((a) => ({
            ...a,
            label: a.name || a.id,
          })),
        ),
      )
      .catch(() => undefined)

    // 机器人列表
    channelsApi
      .listHostingBots()
      .then(setBots)
      .catch(() => undefined)

    // 标签组 → 展平为选项
    tagGroupsApi
      .list()
      .then((groups: TagGroupDTO[]) => {
        const options: TagOption[] = []
        for (const g of groups) {
          for (const t of g.tags || []) {
            options.push({
              id: t.id,
              name: t.name,
              groupId: g.id,
              groupName: g.name,
              fullName: `${g.name}-${t.name}`,
            })
          }
        }
        setTagOptions(options)
      })
      .catch(() => undefined)

    // 托管规则
    channelsApi
      .getHostingRules({ accountId })
      .then((r) => {
        setResume(r.autoResumeSeconds != null ? String(r.autoResumeSeconds) : '')
        setAutoCancel(r.autoCancelEnabled)
      })
      .catch(() => undefined)

    loadSessions()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [accountId])

  // ── 选择逻辑 ──
  const allSelected = sessions.length > 0 && selectedIds.length === sessions.length

  const toggleAll = () => setSelectedIds(allSelected ? [] : sessions.map((s) => s.id))

  const toggleOne = (sid: string) =>
    setSelectedIds((prev) => (prev.includes(sid) ? prev.filter((x) => x !== sid) : [...prev, sid]))

  // ── 账号多选 ──
  const toggleAccountId = (aid: string) => {
    setSelectedAccountIds((prev) =>
      prev.includes(aid) ? prev.filter((x) => x !== aid) : [...prev, aid],
    )
  }

  // ── 标签多选 ──
  const toggleTagId = (tid: string) => {
    setSelectedTagIds((prev) =>
      prev.includes(tid) ? prev.filter((x) => x !== tid) : [...prev, tid],
    )
  }

  // ── 批量操作 ──
  const applyBatch = async () => {
    if (selectedIds.length === 0) {
      toast('请先选择会话')
      return
    }
    try {
      await channelsApi.batchUpdateHosting({
        ids: selectedIds,
        hostedStatus: editHosted,
        hostingChain: editChain || undefined,
      })
      toast(`已更新 ${selectedIds.length} 个会话`)
      setEditOpen(false)
      setSelectedIds([])
      loadSessions()
    } catch (e) {
      toast(`批量更新失败：${errText(e)}`)
    }
  }

  const saveRule = async () => {
    setSavingRule(true)
    try {
      await channelsApi.upsertHostingRules({
        accountId: accountId || undefined,
        autoResumeSeconds: resume ? Number(resume) : null,
        autoCancelEnabled: autoCancel,
      })
      toast('托管规则已保存')
    } catch (e) {
      toast(`保存失败：${errText(e)}`)
    } finally {
      setSavingRule(false)
    }
  }

  const resetFilters = () => {
    setNickname('')
    setSelectedAccountIds([])
    setBotId('')
    setSessionType('')
    setStartDate('')
    setEndDate('')
    setSelectedTagIds([])
    setTagRelation('or')
    setBotSearch('')
  }

  // ── 过滤后的 Bots（搜索） ──
  const filteredBots = useMemo(
    () =>
      botSearch
        ? bots.filter((b) => b.name.toLowerCase().includes(botSearch.toLowerCase()))
        : bots,
    [bots, botSearch],
  )

  // ── 已选标签显示名 ──
  const selectedTagLabels = useMemo(
    () =>
      selectedTagIds
        .map((id) => tagOptions.find((t) => t.id === id)?.fullName)
        .filter(Boolean) as string[],
    [selectedTagIds, tagOptions],
  )

  // ── 已选账号显示 ──
  const selectedAccountLabels = useMemo(
    () =>
      selectedAccountIds
        .map((id) => accounts.find((a) => a.id === id)?.label)
        .filter(Boolean) as string[],
    [selectedAccountIds, accounts],
  )

  return (
    <div className="channel-hosting-page">
      {/* 头部 */}
      <div className="filter-bar channel-accounts-header">
        <div className="channel-team-info">
          <button
            className="btn-back-link"
            onClick={() => navigate(-1)}
            style={{ border: 'none', background: 'none', cursor: 'pointer', fontSize: 14 }}
          >
            ‹ 返回
          </button>
        </div>
      </div>

      {/* Tab 切换 */}
      <div className="channel-hosting-tabs" style={{ justifyContent: 'center', marginTop: 8 }}>
        <button
          className={`channel-hosting-tab${tab === 'batch' ? ' active' : ''}`}
          onClick={() => setTab('batch')}
        >
          批量托管
        </button>
        <button
          className={`channel-hosting-tab${tab === 'rules' ? ' active' : ''}`}
          onClick={() => setTab('rules')}
        >
          托管规则配置
        </button>
      </div>

      {/* ═══ 批量托管 Tab ═══ */}
      <div className={`channel-hosting-pane${tab === 'batch' ? ' active' : ''}`}>
        {/* 筛选区域 */}
        <div className="hosting-filters">
          {/* 第一行：昵称 / 托管账号 / 托管AI机器人 */}
          <div className="hosting-filter-row">
            {/* 用户昵称 */}
            <div className="hosting-filter-item hosting-filter-nickname">
              <label>用户昵称：</label>
              <input
                className="input"
                placeholder="请输入"
                value={nickname}
                onChange={(e) => setNickname(e.target.value)}
              />
            </div>

            {/* 托管账号（多选） */}
            <div className="hosting-filter-item hosting-filter-account">
              <label>托管账号：</label>
              <div className="custom-select">
                <div
                  className="import-select-trigger"
                  onClick={accountSelect.toggle}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 4,
                    flexWrap: 'wrap',
                    minHeight: 32,
                    padding: '4px 8px',
                  }}
                >
                  {selectedAccountLabels.length > 0 ? (
                    <>
                      {selectedAccountLabels.map((lbl) => (
                        <span key={lbl} className="hosting-selected-chip">
                          {lbl}
                          <span
                            className="hosting-chip-remove"
                            onClick={(e) => {
                              e.stopPropagation()
                              const acc = accounts.find((a) => a.label === lbl)
                              if (acc) toggleAccountId(acc.id)
                            }}
                          >
                            ×
                          </span>
                        </span>
                      ))}
                    </>
                  ) : (
                    <span style={{ color: 'var(--muted)' }}>请选择</span>
                  )}
                  <ChevronDown size={14} style={{ marginLeft: 'auto', color: 'var(--muted)' }} />
                </div>
                {accountSelect.open && (
                  <div className="import-select-dropdown hosting-account-dropdown">
                    {accounts.map((a) => (
                      <div
                        key={a.id}
                        className={`import-select-option${
                          selectedAccountIds.includes(a.id) ? ' active' : ''
                        }`}
                        style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '6px 10px' }}
                        onClick={() => toggleAccountId(a.id)}
                      >
                        <span
                          className="avatar-xs"
                          style={{
                            background: avatarColor(a.name),
                            fontSize: 11,
                            width: 22,
                            height: 22,
                            flexShrink: 0,
                          }}
                        >
                          {avatarChar(a.name)}
                        </span>
                        <span>{a.label}</span>
                        {selectedAccountIds.includes(a.id) && (
                          <Check size={14} style={{ marginLeft: 'auto', color: 'var(--blue)' }} />
                        )}
                      </div>
                    ))}
                    {accounts.length === 0 && (
                      <div className="import-select-option" style={{ color: 'var(--muted)' }}>
                        暂无渠道账号
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>

            {/* 托管AI机器人（可搜索） */}
            <div className="hosting-filter-item hosting-filter-bot">
              <label>托管AI机器人：</label>
              <div className="custom-select">
                <div className="import-select-trigger" onClick={botSelect.toggle}>
                  <span>{bots.find((b) => b.id === botId)?.name || '请选择'}</span>
                  <ChevronDown size={14} style={{ marginLeft: 'auto', color: 'var(--muted)' }} />
                </div>
                {botSelect.open && (
                  <div className="import-select-dropdown hosting-bot-dropdown">
                    {/* 搜索框 */}
                    <div className="hosting-bot-search" onClick={(e) => e.stopPropagation()}>
                      <Search size={14} />
                      <input
                        placeholder="请选择"
                        value={botSearch}
                        onChange={(e) => setBotSearch(e.target.value)}
                        autoFocus
                      />
                    </div>
                    {/* 无选项 */}
                    <div
                      className={`import-select-option${!botId ? ' active' : ''}`}
                      onClick={() => {
                        setBotId('')
                        botSelect.close()
                        setBotSearch('')
                      }}
                    >
                      无
                    </div>
                    {/* 机器人列表 */}
                    {filteredBots.map((b) => (
                      <div
                        key={b.id}
                        className={`import-select-option${b.id === botId ? ' active' : ''}`}
                        onClick={() => {
                          setBotId(b.id)
                          botSelect.close()
                          setBotSearch('')
                        }}
                      >
                        {b.name}
                      </div>
                    ))}
                    {filteredBots.length === 0 && botSearch && (
                      <div className="import-select-option" style={{ color: 'var(--muted)' }}>
                        无匹配结果
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* 第二行：会话类型 / 添加时间 / 用户标签 */}
          <div className="hosting-filter-row">
            {/* 会话类型 */}
            <div className="hosting-filter-item hosting-filter-type">
              <label>会话类型：</label>
              <div className="custom-select">
                <div className="import-select-trigger" onClick={sessionTypeSelect.toggle}>
                  <span>
                    {SESSION_TYPES.find((t) => t.value === sessionType)?.label ||
                      '外部联系人'}
                  </span>
                  <ChevronDown size={14} style={{ marginLeft: 'auto', color: 'var(--muted)' }} />
                </div>
                {sessionTypeSelect.open && (
                  <div className="import-select-dropdown">
                    {SESSION_TYPES.map((t) => (
                      <div
                        key={t.value}
                        className={`import-select-option${t.value === sessionType ? ' active' : ''}`}
                        onClick={() => {
                          setSessionType(t.value)
                          sessionTypeSelect.close()
                        }}
                      >
                        {t.label}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>

            {/* 添加时间（日期范围） */}
            <div className="hosting-filter-item hosting-filter-date">
              <label>添加时间：</label>
              <div className="hosting-date-range">
                <input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} />
                <span style={{ color: 'var(--muted)' }}>→</span>
                <input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} />
              </div>
            </div>

            {/* 用户标签（多选） */}
            <div className="hosting-filter-item hosting-filter-tags">
              <label>用户标签：</label>
              <div className="custom-select">
                <div
                  className="import-select-trigger"
                  onClick={tagSelect.toggle}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 4,
                    flexWrap: 'wrap',
                    minHeight: 32,
                    padding: '4px 8px',
                  }}
                >
                  {selectedTagLabels.length > 0 ? (
                    <>
                      {selectedTagLabels.map((lbl) => (
                        <span key={lbl} className="hosting-selected-chip">
                          {lbl}
                          <span
                            className="hosting-chip-remove"
                            onClick={(e) => {
                              e.stopPropagation()
                              const opt = tagOptions.find((t) => t.fullName === lbl)
                              if (opt) toggleTagId(opt.id)
                            }}
                          >
                            ×
                          </span>
                        </span>
                      ))}
                    </>
                  ) : (
                    <span style={{ color: 'var(--muted)' }}>请选择</span>
                  )}
                  <ChevronDown size={14} style={{ marginLeft: 'auto', color: 'var(--muted)' }} />
                </div>
                {tagSelect.open && (
                  <div className="import-select-dropdown hosting-tag-dropdown">
                    {/* 搜索框 */}
                    <div className="hosting-tag-search" onClick={(e) => e.stopPropagation()}>
                      <Search size={14} />
                      <input placeholder="请选择" autoFocus />
                    </div>
                    {/* 按分组渲染标签选项 */}
                    {(() => {
                      const grouped = new Map<string, TagOption[]>()
                      for (const opt of tagOptions) {
                        const list = grouped.get(opt.groupName) || []
                        list.push(opt)
                        grouped.set(opt.groupName, list)
                      }
                      return Array.from(grouped.entries()).map(([groupName, opts]) => (
                        <div key={groupName} className="hosting-tag-group">
                          <div className="hosting-tag-group-name">{groupName}</div>
                          {opts.map((opt) => (
                            <div
                              key={opt.id}
                              className={`import-select-option hosting-tag-option${
                                selectedTagIds.includes(opt.id) ? ' active' : ''
                              }`}
                              onClick={() => toggleTagId(opt.id)}
                            >
                              {opt.name}
                              {selectedTagIds.includes(opt.id) && (
                                <Check size={13} style={{ marginLeft: 'auto', color: 'var(--blue)' }} />
                              )}
                            </div>
                          ))}
                        </div>
                      ))
                    })()}
                    {tagOptions.length === 0 && (
                      <div className="import-select-option" style={{ color: 'var(--muted)' }}>
                        暂无标签数据
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* 第三行：标签关系 + 按钮 */}
          <div className="hosting-filter-row hosting-filter-row-last">
            {/* 标签关系 */}
            <div className="hosting-filter-item hosting-filter-relation">
              <label>标签关系：</label>
              <div className="custom-select">
                <div className="import-select-trigger" onClick={tagRelationSelect.toggle}>
                  <span>{TAG_RELATIONS.find((r) => r.value === tagRelation)?.label || '或关系'}</span>
                  <ChevronDown size={14} style={{ marginLeft: 'auto', color: 'var(--muted)' }} />
                </div>
                {tagRelationSelect.open && (
                  <div className="import-select-dropdown">
                    {TAG_RELATIONS.map((r) => (
                      <div
                        key={r.value}
                        className={`import-select-option${r.value === tagRelation ? ' active' : ''}`}
                        onClick={() => {
                          setTagRelation(r.value)
                          tagRelationSelect.close()
                        }}
                      >
                        {r.label}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>

            {/* 重置 + 查询按钮 */}
            <div className="hosting-filter-actions">
              <button className="btn-hosting-reset" onClick={resetFilters}>
                重置
              </button>
              <button className="btn-hosting-query" onClick={loadSessions}>
                查询
              </button>
            </div>
          </div>
        </div>

        {/* 操作栏 */}
        <div className="hosting-table-actions">
          <button className="btn-hosting-select-all" onClick={toggleAll}>
            <Check size={14} /> 跨页全选
          </button>
          <button className="btn-hosting-batch" onClick={() => setEditOpen((v) => !v)}>
            <RefreshCw size={14} /> 批量编辑托管链
          </button>
          <button className="btn-hosting-edit" onClick={() => setEditOpen((v) => !v)}>
            <Pencil size={14} /> 编辑
          </button>
        </div>

        {/* 批量编辑弹层 */}
        {editOpen && (
          <div className="hosting-filters" style={{ marginBottom: 12 }}>
            <div className="hosting-filter-row">
              <div className="hosting-filter-item">
                <label>托管状态</label>
                <div className="custom-select">
                  <div className="import-select-trigger">
                    {editHosted === 'hosted' ? '托管中' : '未托管'}
                    <ChevronDown size={14} style={{ marginLeft: 'auto', color: 'var(--muted)' }} />
                  </div>
                  <div className="import-select-dropdown" style={{ display: 'block' }}>
                    {(['hosted', 'unhosted'] as const).map((s) => (
                      <div
                        key={s}
                        className={`import-select-option${s === editHosted ? ' active' : ''}`}
                        onClick={() => setEditHosted(s)}
                      >
                        {s === 'hosted' ? '托管中' : '未托管'}
                      </div>
                    ))}
                  </div>
                </div>
              </div>
              <div className="hosting-filter-item">
                <label>托管链（机器人）</label>
                <div className="custom-select">
                  <div className="import-select-trigger">
                    {bots.find((b) => b.id === editChain)?.name || '请选择'}
                    <ChevronDown size={14} style={{ marginLeft: 'auto', color: 'var(--muted)' }} />
                  </div>
                  <div className="import-select-dropdown" style={{ display: 'block' }}>
                    <div className="import-select-option" onClick={() => setEditChain('')}>
                      请选择
                    </div>
                    {bots.map((b) => (
                      <div
                        key={b.id}
                        className={`import-select-option${b.id === editChain ? ' active' : ''}`}
                        onClick={() => setEditChain(b.id)}
                      >
                        {b.name}
                      </div>
                    ))}
                  </div>
                </div>
              </div>
              <div className="hosting-filter-actions">
                <button className="btn-hosting-query" onClick={applyBatch}>
                  应用到选中（{selectedIds.length}）
                </button>
              </div>
            </div>
          </div>
        )}

        {/* 数据表格 */}
        <div className="hosting-table-wrap">
          <table className="hosting-table">
            <thead>
              <tr>
                <th style={{ width: 40 }}>
                  <input type="checkbox" checked={allSelected} onChange={toggleAll} />
                </th>
                <th style={{ width: 70 }}>会话</th>
                <th>相关客户昵称/备注</th>
                <th style={{ width: 140 }}>所属托管账号</th>
                <th style={{ width: 150 }}>添加时间</th>
                <th style={{ width: 110 }}>当前托管状态</th>
                <th style={{ width: 100 }}>托管链</th>
              </tr>
            </thead>
            <tbody>
              {sessions.map((s) => (
                <tr key={s.id}>
                  <td>
                    <input
                      type="checkbox"
                      checked={selectedIds.includes(s.id)}
                      onChange={() => toggleOne(s.id)}
                    />
                  </td>
                  <td>{s.customerName || '—'}</td>
                  <td>
                    <div className="hosting-user-cell">
                      <span className="avatar-xs" style={{ background: avatarColor(s.customerName || s.customerRemark) }}>
                        {avatarChar(s.customerName || s.customerRemark)}
                      </span>
                      <span>{s.customerRemark || s.customerName || '—'}</span>
                    </div>
                  </td>
                  <td>{s.accountId || accountId || '—'}</td>
                  <td>{s.addTime || '—'}</td>
                  <td>
                    <span className={`hosting-status${s.hostedStatus === 'hosted' ? ' hosted' : ''}`}>
                      {s.hostedStatus === 'hosted' ? '托管中' : '未托管'}
                    </span>
                  </td>
                  <td>{s.hostingChain && s.hostingChain !== '-' ? s.hostingChain : '—'}</td>
                </tr>
              ))}
              {!loading && sessions.length === 0 && (
                <tr>
                  <td colSpan={7} style={{ textAlign: 'center', color: 'var(--muted)', padding: 24 }}>
                    无匹配会话
                  </td>
                </tr>
              )}
              {loading && (
                <tr>
                  <td colSpan={7} style={{ textAlign: 'center', color: 'var(--muted)', padding: 24 }}>
                    加载中…
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
        <div className="hosting-pagination">
          <span>
            第 1-{sessions.length} 条 / 总共 {sessions.length} 条
          </span>
        </div>
      </div>

      {/* ═══ 托管规则配置 Tab ═══ */}
      <div className={`channel-hosting-pane${tab === 'rules' ? ' active' : ''}`}>
        <div className="hosting-rules-card">
          <div className="hosting-rule-item">
            <div className="hosting-rule-title">手动取消托管后恢复时间</div>
            <div className="hosting-rule-desc">
              手动取消机器人托管后，多长时间会恢复最近的机器人托管，以 s 为单位，最长 3600s。不填则不会恢复托管。
            </div>
            <div className="hosting-rule-input">
              <input
                className="input"
                type="number"
                placeholder="请输入手动取消托管后恢复时间"
                value={resume}
                onChange={(e) => setResume(e.target.value)}
              />
              <span>秒</span>
            </div>
          </div>
          <div className="hosting-rule-item">
            <div className="hosting-rule-title" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              自动取消托管
              <label className="switch">
                <input type="checkbox" checked={autoCancel} onChange={(e) => setAutoCancel(e.target.checked)} />
                <span className="slider" />
              </label>
            </div>
            <div className="hosting-rule-desc">
              开启后，当托管账号在其他非 12Times 渠道发送内容时，会自动取消对应会话的机器人托管。
            </div>
          </div>
          <div className="hosting-rule-footer">
            <button className="btn-hosting-save" onClick={saveRule} disabled={savingRule}>
              {savingRule ? '保存中…' : '保存'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

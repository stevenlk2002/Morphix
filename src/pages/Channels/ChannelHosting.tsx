/** 托管管理（ChannelHosting）：按账号维度做批量托管 + 托管规则配置。 */

import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { Check, RefreshCw, Pencil } from 'lucide-react'
import Button from '../../components/common/Button'
import { channelsApi } from '../../api/client'
import type { HostingBotDTO, HostingSessionDTO } from '../../types/channels'
import { avatarColor, avatarChar } from './shared/avatar'
import { toast, errText } from '../../utils/toast'
import '../../pages/prototype.css'
import './Channels.css'

type Tab = 'batch' | 'rules'

export default function ChannelHostingPage() {
  const { id: accountId = '' } = useParams()
  const navigate = useNavigate()
  const [tab, setTab] = useState<Tab>('batch')

  const [sessions, setSessions] = useState<HostingSessionDTO[]>([])
  const [bots, setBots] = useState<HostingBotDTO[]>([])
  const [selectedIds, setSelectedIds] = useState<string[]>([])
  const [loading, setLoading] = useState(true)

  // 筛选条件
  const [nickname, setNickname] = useState('')
  const [botId, setBotId] = useState<string>('')
  const [sessionType, setSessionType] = useState<string>('')
  const [start, setStart] = useState('')
  const [end, setEnd] = useState('')

  // 批量编辑托管链（弹层）
  const [editOpen, setEditOpen] = useState(false)
  const [editHosted, setEditHosted] = useState<'hosted' | 'unhosted'>('hosted')
  const [editChain, setEditChain] = useState<string>('')

  // 规则
  const [resume, setResume] = useState<string>('')
  const [autoCancel, setAutoCancel] = useState(false)
  const [savingRule, setSavingRule] = useState(false)

  const loadSessions = () => {
    setLoading(true)
    const params: Record<string, string> = { accountId }
    if (nickname) params.nickname = nickname
    if (botId) params.botId = botId
    if (sessionType) params.sessionType = sessionType
    if (start) params.start = start
    if (end) params.end = end
    channelsApi
      .listHostingSessions(params)
      .then(setSessions)
      .catch((e) => toast(`加载托管会话失败：${errText(e)}`))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    channelsApi
      .listHostingBots()
      .then(setBots)
      .catch(() => undefined)
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

  const allSelected = sessions.length > 0 && selectedIds.length === sessions.length

  const toggleAll = () => {
    setSelectedIds(allSelected ? [] : sessions.map((s) => s.id))
  }
  const toggleOne = (sid: string) => {
    setSelectedIds((prev) => (prev.includes(sid) ? prev.filter((x) => x !== sid) : [...prev, sid]))
  }

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

  const filtered = useMemo(() => sessions, [sessions])

  return (
    <div className="channel-hosting-page">
      <div className="filter-bar channel-accounts-header">
        <div className="channel-team-info">
          <span className="channel-team-name">托管管理</span>
          <span className="badge badge-default">{accountId || '全部账号'}</span>
        </div>
        <div className="channel-header-actions">
          <Button variant="outline" size="sm" onClick={() => navigate('/channels/accounts')}>
            返回账号列表
          </Button>
        </div>
      </div>

      <div className="channel-hosting-tabs">
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

      {/* 批量托管 */}
      <div className={`channel-hosting-pane${tab === 'batch' ? ' active' : ''}`}>
        <div className="hosting-filters">
          <div className="hosting-filter-row">
            <div className="hosting-filter-item">
              <label>用户昵称</label>
              <input
                className="input"
                placeholder="请输入"
                value={nickname}
                onChange={(e) => setNickname(e.target.value)}
              />
            </div>
            <div className="hosting-filter-item">
              <label>托管AI机器人</label>
              <div className="import-select">
                <div
                  className="import-select-trigger"
                  onClick={(e) => {
                    const dd = (e.currentTarget.nextElementSibling as HTMLElement)
                    dd.style.display = dd.style.display === 'block' ? 'none' : 'block'
                  }}
                >
                  {bots.find((b) => b.id === botId)?.name ?? '请选择'}
                </div>
                <div className="import-select-dropdown" style={{ display: 'none' }}>
                  <div
                    className="import-select-option active"
                    onClick={(e) => {
                      setBotId('')
                      ;(e.currentTarget.parentElement as HTMLElement).style.display = 'none'
                      ;(e.currentTarget.parentElement?.previousElementSibling as HTMLElement).textContent =
                        '请选择'
                    }}
                  >
                    请选择
                  </div>
                  {bots.map((b) => (
                    <div
                      key={b.id}
                      className="import-select-option"
                      onClick={(e) => {
                        setBotId(b.id)
                        ;(e.currentTarget.parentElement as HTMLElement).style.display = 'none'
                        ;(e.currentTarget.parentElement?.previousElementSibling as HTMLElement).textContent =
                          b.name
                      }}
                    >
                      {b.name}
                    </div>
                  ))}
                </div>
              </div>
            </div>
            <div className="hosting-filter-item">
              <label>会话类型</label>
              <div className="import-select">
                <div
                  className="import-select-trigger"
                  onClick={(e) => {
                    const dd = e.currentTarget.nextElementSibling as HTMLElement
                    dd.style.display = dd.style.display === 'block' ? 'none' : 'block'
                  }}
                >
                  {sessionType || '外部联系人'}
                </div>
                <div className="import-select-dropdown" style={{ display: 'none' }}>
                  {[
                    { v: '', l: '外部联系人' },
                    { v: '外部联系人', l: '外部联系人' },
                    { v: '外部群聊', l: '外部群聊' },
                  ].map((o) => (
                    <div
                      key={o.l}
                      className="import-select-option"
                      onClick={(e) => {
                        setSessionType(o.v)
                        ;(e.currentTarget.parentElement as HTMLElement).style.display = 'none'
                        ;(e.currentTarget.parentElement?.previousElementSibling as HTMLElement).textContent =
                          o.l
                      }}
                    >
                      {o.l}
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
          <div className="hosting-filter-row">
            <div className="hosting-filter-item">
              <label>添加时间</label>
              <div className="hosting-date-range" style={{ display: 'inline-flex' }}>
                <input type="date" value={start} onChange={(e) => setStart(e.target.value)} style={{ border: 0, outline: 0 }} />
                <span>→</span>
                <input type="date" value={end} onChange={(e) => setEnd(e.target.value)} style={{ border: 0, outline: 0 }} />
              </div>
            </div>
            <div className="hosting-filter-actions">
              <button className="btn-hosting-reset" onClick={() => { setNickname(''); setBotId(''); setSessionType(''); setStart(''); setEnd('') }}>
                重置
              </button>
              <button className="btn-hosting-query" onClick={loadSessions}>
                查询
              </button>
            </div>
          </div>
        </div>

        <div className="hosting-table-actions">
          <button className="btn-hosting-select-all" onClick={toggleAll}>
            <Check size={14} /> {allSelected ? '取消全选' : '跨页全选'}
          </button>
          <button className="btn-hosting-batch" onClick={() => setEditOpen((v) => !v)}>
            <RefreshCw size={14} /> 批量编辑托管链
          </button>
          <button className="btn-hosting-edit" onClick={() => setEditOpen((v) => !v)}>
            <Pencil size={14} /> 编辑
          </button>
        </div>

        {editOpen && (
          <div className="hosting-filters" style={{ marginBottom: 12 }}>
            <div className="hosting-filter-row">
              <div className="hosting-filter-item">
                <label>托管状态</label>
                <div className="import-select">
                  <div
                    className="import-select-trigger"
                    onClick={(e) => {
                      const dd = e.currentTarget.nextElementSibling as HTMLElement
                      dd.style.display = dd.style.display === 'block' ? 'none' : 'block'
                    }}
                  >
                    {editHosted === 'hosted' ? '托管中' : '未托管'}
                  </div>
                  <div className="import-select-dropdown" style={{ display: 'none' }}>
                    {(['hosted', 'unhosted'] as const).map((s) => (
                      <div
                        key={s}
                        className="import-select-option"
                        onClick={(e) => {
                          setEditHosted(s)
                          ;(e.currentTarget.parentElement as HTMLElement).style.display = 'none'
                          ;(e.currentTarget.parentElement?.previousElementSibling as HTMLElement).textContent =
                            s === 'hosted' ? '托管中' : '未托管'
                        }}
                      >
                        {s === 'hosted' ? '托管中' : '未托管'}
                      </div>
                    ))}
                  </div>
                </div>
              </div>
              <div className="hosting-filter-item">
                <label>托管链（机器人）</label>
                <div className="import-select">
                  <div
                    className="import-select-trigger"
                    onClick={(e) => {
                      const dd = e.currentTarget.nextElementSibling as HTMLElement
                      dd.style.display = dd.style.display === 'block' ? 'none' : 'block'
                    }}
                  >
                    {bots.find((b) => b.id === editChain)?.name ?? '请选择'}
                  </div>
                  <div className="import-select-dropdown" style={{ display: 'none' }}>
                    <div
                      className="import-select-option"
                      onClick={(e) => {
                        setEditChain('')
                        ;(e.currentTarget.parentElement as HTMLElement).style.display = 'none'
                        ;(e.currentTarget.parentElement?.previousElementSibling as HTMLElement).textContent =
                          '请选择'
                      }}
                    >
                      请选择
                    </div>
                    {bots.map((b) => (
                      <div
                        key={b.id}
                        className="import-select-option"
                        onClick={(e) => {
                          setEditChain(b.id)
                          ;(e.currentTarget.parentElement as HTMLElement).style.display = 'none'
                          ;(e.currentTarget.parentElement?.previousElementSibling as HTMLElement).textContent =
                            b.name
                        }}
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

        <div className="hosting-table-wrap">
          <table className="hosting-table">
            <thead>
              <tr>
                <th style={{ width: 40 }}>
                  <input type="checkbox" checked={allSelected} onChange={toggleAll} />
                </th>
                <th>会话</th>
                <th>相关客户昵称/备注</th>
                <th>所属托管账号</th>
                <th>添加时间</th>
                <th>当前托管状态</th>
                <th>托管链</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((s) => (
                <tr key={s.id}>
                  <td>
                    <input
                      type="checkbox"
                      checked={selectedIds.includes(s.id)}
                      onChange={() => toggleOne(s.id)}
                    />
                  </td>
                  <td>{s.customerName}</td>
                  <td>
                    <div className="hosting-user-cell">
                      <span className="avatar-xs" style={{ background: avatarColor(s.customerName) }}>
                        {avatarChar(s.customerName)}
                      </span>
                      <span>{s.customerRemark || s.customerName}</span>
                    </div>
                  </td>
                  <td>{accountId || '—'}</td>
                  <td>{s.addTime}</td>
                  <td>
                    <span className={`hosting-status${s.hostedStatus === 'hosted' ? ' hosted' : ''}`}>
                      {s.hostedStatus === 'hosted' ? '托管中' : '未托管'}
                    </span>
                  </td>
                  <td>{s.hostingChain === '-' ? '未配置' : s.hostingChain}</td>
                </tr>
              ))}
              {!loading && filtered.length === 0 && (
                <tr>
                  <td colSpan={7} style={{ textAlign: 'center', color: 'var(--muted)', padding: 24 }}>
                    无匹配会话
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
        <div className="hosting-pagination">
          <span>第 1-{filtered.length} 条/总共 {filtered.length} 条</span>
        </div>
      </div>

      {/* 托管规则配置 */}
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
                <input
                  type="checkbox"
                  checked={autoCancel}
                  onChange={(e) => setAutoCancel(e.target.checked)}
                />
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

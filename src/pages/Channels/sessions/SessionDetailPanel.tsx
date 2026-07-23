/** 单聊详情面板（区域右栏）：客户详情/渠道客户详情 双 Tab + 详细抽屉 + 编辑弹窗 + 沟通记录 + AI 总结。 */

import { useEffect, useState } from 'react'
import { Plus, Pencil, X, Sparkles, ChevronRight } from 'lucide-react'
import type { ContactDetailDTO } from '../../../types/channels'
import { customersApi, llmConfigApi } from '../../../api/client'
import { avatarColor, avatarChar } from '../shared/avatar'
import { toast, errText } from '../../../utils/toast'

interface SessionDetailPanelProps {
  accountId: string
  contact: ContactDetailDTO | null
  onContactUpdated?: (c: ContactDetailDTO) => void
  onCommunicationAdded?: () => void
}

interface CommunicationDTO {
  id: string
  content: string
  type?: string
  aiSummary?: string
  createdAt: string
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="detail-row">
      <span className="detail-row-label">{label}</span>
      <span className="detail-row-value">{value || '--'}</span>
    </div>
  )
}

export default function SessionDetailPanel({
  accountId,
  contact,
  onContactUpdated,
  onCommunicationAdded,
}: SessionDetailPanelProps) {
  const [tab, setTab] = useState<'customer' | 'channel'>('customer')
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [remarkOpen, setRemarkOpen] = useState(false)
  const [basicOpen, setBasicOpen] = useState(false)
  const [commOpen, setCommOpen] = useState(false)
  const [comms, setComms] = useState<CommunicationDTO[]>([])
  const [commContent, setCommContent] = useState('')
  const [useAi, setUseAi] = useState(false)
  const [aiBusy, setAiBusy] = useState(false)
  const [remarkDraft, setRemarkDraft] = useState('')
  const [basicDraft, setBasicDraft] = useState({
    phone: '',
    email: '',
    company: '',
    position: '',
    region: '',
    birthday: '',
    sex: '',
  })

  const name = contact?.contact.name ?? '未选择联系人'
  const profile = contact?.profile
  const avatar = avatarColor(name)

  // 加载沟通记录
  useEffect(() => {
    if (!contact?.contact.id) {
      setComms([])
      return
    }
    customersApi
      .listCommunications(contact.contact.id)
      .then((list: unknown) => setComms(Array.isArray(list) ? (list as CommunicationDTO[]) : []))
      .catch(() => setComms([]))
  }, [contact?.contact.id])

  // 打开弹窗时回填初值
  const openRemark = () => {
    setRemarkDraft(contact?.contact.remark ?? '')
    setRemarkOpen(true)
  }
  const openBasic = () => {
    setBasicDraft({
      phone: profile?.phone ?? '',
      email: profile?.email ?? '',
      company: profile?.company ?? '',
      position: profile?.position ?? '',
      region: profile?.region ?? '',
      birthday: profile?.birthday ?? '',
      sex: '',
    })
    setBasicOpen(true)
  }

  // 提交编辑
  const saveRemark = async () => {
    if (!contact) return
    try {
      await customersApi.updateProfile(contact.contact.id, {
        remark: remarkDraft,
      } as any)
      onContactUpdated?.({ ...contact, contact: { ...contact.contact, remark: remarkDraft } })
      toast('备注已更新')
      setRemarkOpen(false)
    } catch (e) {
      toast(`保存失败：${errText(e)}`)
    }
  }

  const saveBasic = async () => {
    if (!contact) return
    try {
      const updated = await customersApi.updateProfile(
        contact.contact.id,
        basicDraft as any
      )
      onContactUpdated?.({
        ...contact,
        profile: (updated as any)?.profile ?? { ...contact.profile, ...basicDraft },
      })
      toast('基本信息已更新')
      setBasicOpen(false)
    } catch (e) {
      toast(`保存失败：${errText(e)}`)
    }
  }

  // AI 总结（前端直接调 LLM）
  const runAiSummary = async (text: string): Promise<string> => {
    try {
      const cfg = await llmConfigApi.getAll()
      const useCfg = cfg?.primary?.enabled ? cfg.primary : cfg?.secondary
      if (!useCfg?.apiKey) {
        toast('未配置 LLM API Key，跳过 AI 总结')
        return ''
      }
      const prompt = `请针对这段话进行总结提炼：${text}`
      // 兼容 OpenAI 协议
      const base = useCfg.apiBaseUrl?.replace(/\/+$/, '') || 'https://api.openai.com/v1'
      const resp = await fetch(`${base}/chat/completions`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${useCfg.apiKey}`,
        },
        body: JSON.stringify({
          model: useCfg.model,
          messages: [
            { role: 'system', content: '你是一个专业的沟通总结助手。' },
            { role: 'user', content: prompt },
          ],
        }),
      })
      if (!resp.ok) throw new Error(`LLM HTTP ${resp.status}`)
      const data = await resp.json()
      const content = data?.choices?.[0]?.message?.content ?? ''
      return String(content).trim()
    } catch (e) {
      toast(`AI 总结失败：${errText(e)}`)
      return ''
    }
  }

  const submitComm = async () => {
    if (!contact) return
    const content = commContent.trim()
    if (!content) {
      toast('请填写沟通内容')
      return
    }
    let aiSummary = ''
    if (useAi) {
      setAiBusy(true)
      aiSummary = await runAiSummary(content)
      setAiBusy(false)
    }
    try {
      await customersApi.createCommunication(contact.contact.id, {
        content,
        type: '沟通',
        aiSummary,
      })
      toast('已添加沟通记录')
      setCommOpen(false)
      setCommContent('')
      setUseAi(false)
      onCommunicationAdded?.()
      // 重新拉取
      const list = await customersApi.listCommunications(contact.contact.id)
      setComms(Array.isArray(list) ? (list as CommunicationDTO[]) : [])
    } catch (e) {
      toast(`添加失败：${errText(e)}`)
    }
  }

  if (!contact) {
    return (
      <aside className="session-detail">
        <div className="detail-empty">
          <div style={{ fontSize: 32, opacity: 0.3 }}>👤</div>
          <div>请先选择一个会话</div>
        </div>
      </aside>
    )
  }

  return (
    <>
      <aside className="session-detail session-detail-panel">
        <div className="detail-tabs">
          <button
            className={`detail-tab${tab === 'customer' ? ' active' : ''}`}
            onClick={() => setTab('customer')}
          >
            客户详情
          </button>
          <button
            className={`detail-tab${tab === 'channel' ? ' active' : ''}`}
            onClick={() => setTab('channel')}
          >
            渠道客户详情
          </button>
        </div>

        {tab === 'customer' ? (
          <div className="detail-pane active">
            {/* 好友卡片 */}
            <div className="detail-avatar detail-avatar-row">
              <div className="avatar-sm" style={{ background: avatar }}>
                {avatarChar(name)}
              </div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div className="detail-name">{name}</div>
                <div className="detail-channel">{contact.contact.channel}</div>
              </div>
              <button className="detail-action" onClick={() => setDrawerOpen(true)}>
                详细 <ChevronRight size={12} />
              </button>
            </div>

            <div className="detail-section">
              <div className="detail-action">
                <Plus size={13} /> 添加标签
              </div>
              <div className="detail-row">
                <span className="detail-row-label">备注</span>
                <span className="detail-row-value">{contact.contact.remark || '--'}</span>
                <button className="detail-edit" onClick={openRemark}>
                  <Pencil size={12} /> 编辑
                </button>
              </div>
            </div>

            <div className="detail-section">
              <div className="detail-section-title">
                基本信息
                <button className="detail-edit" style={{ float: 'right' }} onClick={openBasic}>
                  <Pencil size={12} /> 编辑
                </button>
              </div>
              <Row label="电话" value={profile?.phone ?? ''} />
              <Row label="邮箱" value={profile?.email ?? ''} />
              <Row label="公司" value={profile?.company ?? ''} />
              <Row label="职位" value={profile?.position ?? ''} />
              <Row label="区域" value={profile?.region ?? ''} />
              <Row label="年龄" value={profile?.age != null ? String(profile.age) : ''} />
              <Row label="出生日期" value={profile?.birthday ?? ''} />
              <Row label="添加时间" value={contact.contact.addTime ?? ''} />
            </div>

            <div className="detail-section" style={{ borderBottom: 'none' }}>
              <div className="detail-section-title">
                沟通记录（{comms.length}）
                <label className="ai-toggle" style={{ float: 'right' }}>
                  <input type="checkbox" checked={useAi} onChange={(e) => setUseAi(e.target.checked)} />
                  <Sparkles size={12} /> AI 总结
                </label>
              </div>
              <button className="btn btn-primary btn-sm" style={{ width: '100%' }} onClick={() => setCommOpen(true)}>
                <Plus size={13} /> 添加新沟通记录
              </button>
              {comms.length === 0 ? (
                <div className="detail-empty">📝 暂无沟通记录</div>
              ) : (
                <div className="comm-list" style={{ marginTop: 12 }}>
                  {comms.map((c) => (
                    <div className="comm-item" key={c.id}>
                      <div className="comm-meta">
                        <span>{c.type ?? '沟通'}</span>
                        <span>{c.createdAt?.slice(0, 16) ?? ''}</span>
                      </div>
                      <div className="comm-content">{c.content}</div>
                      {c.aiSummary && <div className="comm-summary">AI：{c.aiSummary}</div>}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        ) : (
          <div className="detail-pane active">
            <div className="detail-avatar">
              <div className="avatar-sm" style={{ background: avatar }}>
                {avatarChar(name)}
              </div>
              <div className="detail-name">{name}</div>
              <div className="detail-channel">{contact.contact.channel}</div>
            </div>
            <div className="detail-section">
              <div className="detail-section-title">关联私域渠道</div>
              <div className="detail-row"><span className="detail-row-label">渠道类型</span><span className="detail-row-value">企业微信</span></div>
              <div className="detail-row"><span className="detail-row-label">昵称</span><span className="detail-row-value">{contact.contact.nickname || name}</span></div>
              <div className="detail-row"><span className="detail-row-label">关联渠道账号</span><span className="detail-row-value">{accountId}</span></div>
              <div className="detail-row"><span className="detail-row-label">备注名</span><span className="detail-row-value">{contact.contact.remark || '--'}</span></div>
              <div className="detail-row"><span className="detail-row-label">渠道备注</span><span className="detail-row-value">{contact.contact.description || '--'}</span></div>
            </div>
            <div className="detail-section" style={{ borderBottom: 'none' }}>
              <div className="detail-section-title">自定义属性</div>
              <div className="detail-empty">暂无自定义属性</div>
              <button className="btn btn-outline btn-sm" style={{ width: '100%' }}>
                <Plus size={12} /> 新建
              </button>
            </div>
          </div>
        )}
      </aside>

      {/* 详细信息抽屉 */}
      {drawerOpen && (
        <div className="drawer-overlay" onMouseDown={() => setDrawerOpen(false)}>
          <div className="drawer-panel" onMouseDown={(e) => e.stopPropagation()}>
            <div className="drawer-header">
              <h3>详细信息</h3>
              <button className="modal-close" onClick={() => setDrawerOpen(false)}><X size={16} /></button>
            </div>
            <div className="drawer-body">
              <div className="detail-avatar">
                <div className="avatar-sm" style={{ background: avatar }}>{avatarChar(name)}</div>
                <div className="detail-name">{name}</div>
                <div className="detail-channel">{contact.contact.channel}</div>
              </div>
              <div className="detail-section">
                <div className="detail-section-title">标签</div>
                <div className="detail-empty">（无标签）</div>
              </div>
              <div className="detail-section">
                <div className="detail-section-title">沟通记录（{comms.length}）</div>
                {comms.length === 0 ? <div className="detail-empty">暂无</div> : comms.map((c) => (
                  <div className="comm-item" key={c.id}>
                    <div className="comm-meta"><span>{c.type ?? '沟通'}</span><span>{c.createdAt?.slice(0, 16)}</span></div>
                    <div className="comm-content">{c.content}</div>
                    {c.aiSummary && <div className="comm-summary">AI：{c.aiSummary}</div>}
                  </div>
                ))}
              </div>
              <div className="detail-section" style={{ borderBottom: 'none' }}>
                <div className="detail-section-title">历史备注</div>
                <div className="detail-empty">（无历史备注）</div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* 修改备注 */}
      {remarkOpen && (
        <div className="modal-overlay" onMouseDown={() => setRemarkOpen(false)}>
          <div className="modal-panel" onMouseDown={(e) => e.stopPropagation()}
            style={{ width: 'min(440px, calc(100vw - 32px))' }}>
            <div className="modal-header">
              <h3>修改备注</h3>
              <button className="modal-close" onClick={() => setRemarkOpen(false)}><X size={16} /></button>
            </div>
            <div className="modal-body">
              <textarea
                className="input"
                rows={4}
                placeholder="请填写备注"
                value={remarkDraft}
                onChange={(e) => setRemarkDraft(e.target.value)}
                style={{ resize: 'vertical' }}
                maxLength={1000}
              />
              <div style={{ textAlign: 'right', color: 'var(--muted)', fontSize: 12, marginTop: 4 }}>
                {remarkDraft.length} / 1000
              </div>
            </div>
            <div className="modal-footer" style={{ justifyContent: 'flex-end' }}>
              <button className="btn btn-ghost btn-sm" onClick={() => setRemarkOpen(false)}>取消</button>
              <button className="btn btn-primary btn-sm" onClick={saveRemark}>确认</button>
            </div>
          </div>
        </div>
      )}

      {/* 编辑基本信息 */}
      {basicOpen && (
        <div className="modal-overlay" onMouseDown={() => setBasicOpen(false)}>
          <div className="modal-panel" onMouseDown={(e) => e.stopPropagation()}
            style={{ width: 'min(560px, calc(100vw - 32px))' }}>
            <div className="modal-header">
              <h3>编辑基本信息</h3>
              <button className="modal-close" onClick={() => setBasicOpen(false)}><X size={16} /></button>
            </div>
            <div className="modal-body" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
              <div className="form-field">
                <label>电话</label>
                <input className="input" value={basicDraft.phone} onChange={(e) => setBasicDraft({ ...basicDraft, phone: e.target.value })} />
              </div>
              <div className="form-field">
                <label>邮箱</label>
                <input className="input" value={basicDraft.email} onChange={(e) => setBasicDraft({ ...basicDraft, email: e.target.value })} />
              </div>
              <div className="form-field">
                <label>公司</label>
                <input className="input" value={basicDraft.company} onChange={(e) => setBasicDraft({ ...basicDraft, company: e.target.value })} />
              </div>
              <div className="form-field">
                <label>职位</label>
                <input className="input" value={basicDraft.position} onChange={(e) => setBasicDraft({ ...basicDraft, position: e.target.value })} />
              </div>
              <div className="form-field">
                <label>出生日期</label>
                <input className="input" type="date" value={basicDraft.birthday} onChange={(e) => setBasicDraft({ ...basicDraft, birthday: e.target.value })} />
              </div>
              <div className="form-field">
                <label>区域</label>
                <input className="input" value={basicDraft.region} onChange={(e) => setBasicDraft({ ...basicDraft, region: e.target.value })} />
              </div>
              <div className="form-field" style={{ gridColumn: '1 / -1' }}>
                <label>性别</label>
                <select className="input" value={basicDraft.sex} onChange={(e) => setBasicDraft({ ...basicDraft, sex: e.target.value })}>
                  <option value="">请选择</option>
                  <option value="男">男</option>
                  <option value="女">女</option>
                </select>
              </div>
            </div>
            <div className="modal-footer" style={{ justifyContent: 'flex-end' }}>
              <button className="btn btn-ghost btn-sm" onClick={() => setBasicOpen(false)}>取消</button>
              <button className="btn btn-primary btn-sm" onClick={saveBasic}>保存</button>
            </div>
          </div>
        </div>
      )}

      {/* 添加沟通记录 + AI 总结 */}
      {commOpen && (
        <div className="modal-overlay" onMouseDown={() => setCommOpen(false)}>
          <div className="modal-panel" onMouseDown={(e) => e.stopPropagation()}
            style={{ width: 'min(520px, calc(100vw - 32px))' }}>
            <div className="modal-header">
              <h3>添加沟通记录</h3>
              <button className="modal-close" onClick={() => setCommOpen(false)}><X size={16} /></button>
            </div>
            <div className="modal-body">
              <div className="form-field" style={{ marginBottom: 10 }}>
                <label><span style={{ color: '#ef4444' }}>*</span> 沟通记录</label>
                <textarea
                  className="input"
                  rows={6}
                  placeholder="请填写沟通记录"
                  value={commContent}
                  onChange={(e) => setCommContent(e.target.value)}
                  style={{ resize: 'vertical' }}
                  maxLength={500}
                />
                <div style={{ textAlign: 'right', color: 'var(--muted)', fontSize: 12, marginTop: 4 }}>
                  {commContent.length} / 500
                </div>
              </div>
              <div className="form-field" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <label className="ai-toggle">
                  <input type="checkbox" checked={useAi} onChange={(e) => setUseAi(e.target.checked)} />
                  <Sparkles size={12} /> 启用 AI 总结
                </label>
                <span style={{ fontSize: 12, color: 'var(--muted)' }}>
                  勾选后会把沟通记录输出给 AI 执行总结
                </span>
              </div>
            </div>
            <div className="modal-footer" style={{ justifyContent: 'flex-end' }}>
              <button className="btn btn-ghost btn-sm" onClick={() => setCommOpen(false)} disabled={aiBusy}>取消</button>
              <button className="btn btn-primary btn-sm" onClick={submitComm} disabled={aiBusy || !commContent.trim()}>
                {aiBusy ? 'AI 总结中…' : '添加'}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  )
}

import { useEffect, useState, useCallback } from 'react'
import { Plus, X, Check, MessageCircle } from 'lucide-react'
import Modal from '../../components/common/Modal'
import Button from '../../components/common/Button'
import { customersApi } from '../../api/client'
import type { ContactDetailDTO } from '../../types/channels'
import { toast } from '../../utils/toast'
import CustomerTagModal from './CustomerTagModal'

interface Props {
  contactId: string | null
  onClose: () => void
}

const AVATAR_COLORS = [
  '#ef4444', '#e8a649', '#4A90D9', '#7fb069', '#8b5cf6',
  '#ec4899', '#14b8a6', '#f59e0b', '#06b6d4', '#84cc16',
  '#3b82f6', '#6366f1', '#a855f7', '#22c55e', '#f97316',
]

function avatarColor(name: string): string {
  let hash = 0
  for (let i = 0; i < (name || '').length; i++) hash = name.charCodeAt(i) + ((hash << 5) - hash)
  return AVATAR_COLORS[Math.abs(hash) % AVATAR_COLORS.length]
}

function fillEmpty(v: string | undefined | null): string {
  return v || '--'
}

export default function CustomerDetailDrawer({ contactId, onClose }: Props) {
  const [data, setData] = useState<ContactDetailDTO | null>(null)
  const [loading, setLoading] = useState(false)
  const [commTab, setCommTab] = useState<'communications' | 'notes'>('communications')
  const [tagModalOpen, setTagModalOpen] = useState(false)
  const [customerTagIds, setCustomerTagIds] = useState<string[]>([])

  // 编辑备注
  const [editNoteOpen, setEditNoteOpen] = useState(false)
  const [noteText, setNoteText] = useState('')

  // 编辑基本信息
  const [editInfoOpen, setEditInfoOpen] = useState(false)
  const [infoPhone, setInfoPhone] = useState('')
  const [infoEmail, setInfoEmail] = useState('')
  const [infoCompany, setInfoCompany] = useState('')
  const [infoPosition, setInfoPosition] = useState('')
  const [infoRegion, setInfoRegion] = useState('')
  const [infoBirthday, setInfoBirthday] = useState('')

  // 添加沟通记录
  const [addCommOpen, setAddCommOpen] = useState(false)
  const [commContent, setCommContent] = useState('')

  // 添加自定义属性
  const [addAttrOpen, setAddAttrOpen] = useState(false)
  const [attrName, setAttrName] = useState('')
  const [attrValue, setAttrValue] = useState('')

  const loadDetail = useCallback(async () => {
    if (!contactId) return
    setLoading(true)
    try {
      const d = await customersApi.getDetail(contactId)
      setData(d)
      // Load tags (use profile.id, not contactId)
      try {
        const tags = await customersApi.getCustomerTags(d.profile?.id || '')
        setCustomerTagIds((tags as Array<{ id: string }>).map((t) => t.id))
      } catch { setCustomerTagIds([]) }
    } catch {
      setData(null)
      toast('加载客户详情失败')
    } finally {
      setLoading(false)
    }
  }, [contactId])

  useEffect(() => {
    if (contactId) loadDetail()
  }, [contactId, loadDetail])

  if (!contactId) return null

  const contact = data?.contact
  const profile = data?.profile
  const communications = data?.communications || []
  const attributes = data?.attributes || []

  const name = contact?.name || ''
  const account = contact?.remark || profile?.addChannel || ''
  const channel = contact?.channel || ''

  const saveNote = async () => {
    if (!contactId || !profile) return
    try {
      await customersApi.updateProfile(contactId, { remark: noteText })
      toast('备注已保存')
      setEditNoteOpen(false)
      loadDetail()
    } catch { toast('保存失败') }
  }

  const saveInfo = async () => {
    if (!contactId) return
    try {
      await customersApi.updateProfile(contactId, {
        phone: infoPhone,
        email: infoEmail,
        company: infoCompany,
        position: infoPosition,
        region: infoRegion,
        birthday: infoBirthday,
      })
      toast('基本信息已保存')
      setEditInfoOpen(false)
      loadDetail()
    } catch { toast('保存失败') }
  }

  const saveCommunication = async () => {
    if (!commContent.trim()) { toast('请填写沟通记录'); return }
    if (!contactId || !profile) return
    try {
      await customersApi.createCommunication(profile.id, { content: commContent.trim() })
      toast('沟通记录已添加')
      setAddCommOpen(false)
      setCommContent('')
      loadDetail()
    } catch { toast('添加失败') }
  }

  const saveAttribute = async () => {
    if (!attrName.trim() || !attrValue.trim()) { toast('请填写属性名称和属性值'); return }
    if (!contactId || !profile) return
    try {
      await customersApi.createAttribute(profile.id, { name: attrName.trim(), value: attrValue.trim() })
      toast('自定义属性已添加')
      setAddAttrOpen(false)
      setAttrName('')
      setAttrValue('')
      loadDetail()
    } catch { toast('添加失败') }
  }

  const handleSendMessage = () => {
    onClose()
    toast('已跳转至会话窗口（模拟）')
  }

  return (
    <>
      {/* Drawer overlay */}
      <div
        style={{
          position: 'fixed', inset: 0, zIndex: 1000, background: 'rgba(0,0,0,0.3)',
          display: 'flex', justifyContent: 'flex-end',
        }}
        onClick={onClose}
      >
        <div
          style={{
            width: 820, maxWidth: '100vw', height: '100%', background: '#fff',
            display: 'flex', flexDirection: 'column', boxShadow: '-4px 0 24px rgba(0,0,0,0.12)',
            animation: 'slideInRight 0.2s ease',
          }}
          onClick={(e) => e.stopPropagation()}
        >
          {/* Header */}
          <div style={{
            display: 'flex', alignItems: 'flex-start', gap: 12,
            padding: '16px 20px', borderBottom: '1px solid var(--border)',
          }}>
            <div style={{
              width: 44, height: 44, borderRadius: '50%', backgroundColor: avatarColor(name),
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              color: '#fff', fontSize: 18, fontWeight: 600, flexShrink: 0,
            }}>
              {name.slice(0, 1)}
            </div>
            <div style={{ minWidth: 0, flex: 1 }}>
              <div style={{ fontSize: 16, fontWeight: 700, color: 'var(--text-primary)' }}>{name}</div>
              <button
                className="customer-detail-add-tag"
                onClick={() => setTagModalOpen(true)}
              >
                <Plus size={12} /> 添加标签
              </button>
              <div style={{ fontSize: 12, color: 'var(--text-tertiary)', marginTop: 2 }}>
                {fillEmpty(account)} · {fillEmpty(channel)}
              </div>
            </div>
            <button
              onClick={onClose}
              style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-tertiary)', padding: 4 }}
            >
              <X size={20} />
            </button>
          </div>

          {/* Body */}
          <div style={{ flex: 1, overflow: 'hidden', display: 'flex' }}>
            {loading ? (
              <div style={{ padding: 40, textAlign: 'center', width: '100%', color: 'var(--text-tertiary)' }}>加载中...</div>
            ) : !data ? (
              <div style={{ padding: 40, textAlign: 'center', width: '100%', color: 'var(--text-tertiary)' }}>未找到客户数据</div>
            ) : (
              <div className="customer-detail-wrap">
                {/* Main */}
                <div className="customer-detail-main">
                  {/* Remark */}
                  <div className="contacts-detail-section" style={{ paddingBottom: 10 }}>
                    <div className="contacts-detail-row" style={{ justifyContent: 'space-between' }}>
                      <span className="contacts-detail-row-label">备注</span>
                      <span
                        className="contacts-detail-action"
                        style={{ color: 'var(--primary)', cursor: 'pointer', fontSize: 13 }}
                        onClick={() => {
                          setNoteText(profile?.remark || '')
                          setEditNoteOpen(true)
                        }}
                      >
                        编辑
                      </span>
                    </div>
                    <div className="contacts-detail-row" style={{ color: 'var(--text-secondary)' }}>
                      {fillEmpty(profile?.remark)}
                    </div>
                  </div>

                  {/* Basic Info */}
                  <div className="contacts-detail-section">
                    <div className="contacts-detail-row" style={{ justifyContent: 'space-between' }}>
                      <span className="contacts-detail-section-title" style={{ fontWeight: 600, fontSize: 14 }}>
                        基本信息
                      </span>
                      <span
                        className="contacts-detail-action"
                        style={{ color: 'var(--primary)', cursor: 'pointer', fontSize: 13 }}
                        onClick={() => {
                          setInfoPhone(profile?.phone || '')
                          setInfoEmail(profile?.email || '')
                          setInfoCompany(profile?.company || '')
                          setInfoPosition(profile?.position || '')
                          setInfoRegion(profile?.region || '')
                          setInfoBirthday(profile?.birthday || '')
                          setEditInfoOpen(true)
                        }}
                      >
                        编辑
                      </span>
                    </div>
                    <div className="contacts-detail-row"><span className="contacts-detail-row-label">电话</span><span className="contacts-detail-row-value">{fillEmpty(profile?.phone)}</span></div>
                    <div className="contacts-detail-row"><span className="contacts-detail-row-label">邮箱</span><span className="contacts-detail-row-value">{fillEmpty(profile?.email)}</span></div>
                    <div className="contacts-detail-row"><span className="contacts-detail-row-label">公司</span><span className="contacts-detail-row-value">{fillEmpty(profile?.company)}</span></div>
                    <div className="contacts-detail-row"><span className="contacts-detail-row-label">职位</span><span className="contacts-detail-row-value">{fillEmpty(profile?.position)}</span></div>
                    <div className="contacts-detail-row"><span className="contacts-detail-row-label">区域</span><span className="contacts-detail-row-value">{fillEmpty(profile?.region)}</span></div>
                    <div className="contacts-detail-row"><span className="contacts-detail-row-label">年龄</span><span className="contacts-detail-row-value">{profile?.age ?? '--'}</span></div>
                    <div className="contacts-detail-row"><span className="contacts-detail-row-label">出生日期</span><span className="contacts-detail-row-value">{fillEmpty(profile?.birthday)}</span></div>
                    <div className="contacts-detail-row"><span className="contacts-detail-row-label">添加时间</span><span className="contacts-detail-row-value">{fillEmpty(profile?.addTime)}</span></div>
                  </div>

                  {/* Communication Tabs */}
                  <div className="contacts-detail-section" style={{ borderBottom: 'none' }}>
                    <div className="customer-detail-tabs">
                      <button
                        className={`detail-tab${commTab === 'communications' ? ' active' : ''}`}
                        onClick={() => setCommTab('communications')}
                      >
                        沟通记录（{communications.length}）
                      </button>
                      <button
                        className={`detail-tab${commTab === 'notes' ? ' active' : ''}`}
                        onClick={() => setCommTab('notes')}
                      >
                        历史备注（0）
                      </button>
                    </div>
                    <Button
                      variant="primary"
                      size="sm"
                      style={{ margin: '8px 0', width: '100%' }}
                      icon={<Plus size={14} />}
                      onClick={() => setAddCommOpen(true)}
                    >
                      添加新的沟通记录
                    </Button>

                    {commTab === 'communications' && (
                      <div className="customer-comm-list">
                        {communications.length === 0 ? (
                          <div style={{ textAlign: 'center', padding: 24, color: 'var(--text-tertiary)', fontSize: 13 }}>
                            暂无沟通记录
                          </div>
                        ) : (
                          communications.map((c) => (
                            <div className="customer-comm-item" key={c.id}>
                              <div className="customer-comm-header">
                                <span className="customer-comm-date">{c.createdAt}</span>
                                {c.aiSummary && (
                                  <span className="customer-comm-ai">
                                    <Check size={11} /> AI总结
                                  </span>
                                )}
                              </div>
                              <div className="customer-comm-content">
                                {c.aiSummary ? (
                                  <>
                                    <p>{c.aiSummary}</p>
                                  </>
                                ) : (
                                  <p>{c.content}</p>
                                )}
                              </div>
                            </div>
                          ))
                        )}
                      </div>
                    )}

                    {commTab === 'notes' && (
                      <div style={{ textAlign: 'center', padding: 24, color: 'var(--text-tertiary)', fontSize: 13 }}>
                        暂无历史备注
                      </div>
                    )}
                  </div>
                </div>

                {/* Side */}
                <div className="customer-detail-side">
                  {/* Linked Channels */}
                  <div className="contacts-detail-section" style={{ borderBottom: 'none' }}>
                    <div className="contacts-detail-section-title" style={{ fontWeight: 600, marginBottom: 8 }}>
                      关联私域渠道
                    </div>
                    <div className="contacts-detail-row"><span className="contacts-detail-row-label">渠道类型</span><span className="contacts-detail-row-value">{fillEmpty(channel)}</span></div>
                    <div className="contacts-detail-row"><span className="contacts-detail-row-label">昵称</span><span className="contacts-detail-row-value">{fillEmpty(contact?.nickname)}</span></div>
                    <div className="contacts-detail-row"><span className="contacts-detail-row-label">个性签名</span><span className="contacts-detail-row-value">{fillEmpty(profile?.signature)}</span></div>
                    <div className="contacts-detail-row"><span className="contacts-detail-row-label">关联渠道账号</span><span className="contacts-detail-row-value">{fillEmpty(contact?.accountId)}</span></div>
                    <div className="contacts-detail-row"><span className="contacts-detail-row-label">渠道备注</span><span className="contacts-detail-row-value">{fillEmpty(contact?.remark)}</span></div>
                    <div className="contacts-detail-row"><span className="contacts-detail-row-label">关联会话</span></div>
                    <div className="contacts-detail-row" style={{ paddingLeft: 12 }}>
                      <span className="contacts-detail-row-label">单聊</span>
                      <span className="contacts-detail-row-value" style={{ color: 'var(--primary)', cursor: 'pointer' }} onClick={handleSendMessage}>
                        {name}
                      </span>
                    </div>
                  </div>

                  {/* Custom Attributes */}
                  <div className="contacts-detail-section" style={{ borderBottom: 'none' }}>
                    <div className="customer-detail-side-header" style={{ marginBottom: 8 }}>
                      <span className="contacts-detail-section-title" style={{ fontWeight: 600 }}>自定义属性</span>
                      <span
                        className="contacts-detail-action"
                        style={{ color: 'var(--primary)', cursor: 'pointer', fontSize: 13 }}
                        onClick={() => setAddAttrOpen(true)}
                      >
                        <Plus size={12} /> 新建
                      </span>
                    </div>
                    {attributes.length === 0 ? (
                      <div className="detail-empty" style={{ padding: '24px 0', textAlign: 'center', fontSize: 13, color: 'var(--text-tertiary)' }}>
                        <div>暂无自定义属性，点击右上角"新建"按钮添加</div>
                      </div>
                    ) : (
                      attributes.map((a) => (
                        <div className="contacts-detail-row" key={a.id}>
                          <span className="contacts-detail-row-label">{a.name}</span>
                          <span className="contacts-detail-row-value">{a.value}</span>
                        </div>
                      ))
                    )}
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Footer */}
          <div style={{
            display: 'flex', justifyContent: 'flex-end', gap: 10,
            padding: '12px 20px', borderTop: '1px solid var(--border)',
          }}>
            <Button variant="secondary" size="sm" onClick={onClose}>关闭</Button>
            <Button variant="primary" size="sm" icon={<MessageCircle size={14} />} onClick={handleSendMessage}>
              发消息
            </Button>
          </div>
        </div>
      </div>

      {/* Edit Note Modal */}
      <Modal
        open={editNoteOpen}
        title="修改备注"
        onClose={() => setEditNoteOpen(false)}
        footer={
          <>
            <Button variant="secondary" size="sm" onClick={() => setEditNoteOpen(false)}>取消</Button>
            <Button variant="primary" size="sm" onClick={saveNote}>确认</Button>
          </>
        }
      >
        <div className="form-group">
          <label className="form-label">备注</label>
          <textarea
            className="input"
            rows={4}
            placeholder="请填写备注"
            maxLength={1000}
            value={noteText}
            onChange={(e) => setNoteText(e.target.value)}
            style={{ width: '100%' }}
          />
          <div className="customer-char-count">{noteText.length}/1000</div>
        </div>
      </Modal>

      {/* Edit Basic Info Modal */}
      <Modal
        open={editInfoOpen}
        title="编辑基本信息"
        onClose={() => setEditInfoOpen(false)}
        width={520}
        footer={
          <>
            <Button variant="secondary" size="sm" onClick={() => setEditInfoOpen(false)}>取消</Button>
            <Button variant="primary" size="sm" onClick={saveInfo}>保存</Button>
          </>
        }
      >
        <div className="customer-edit-form">
          <div className="form-row">
            <div className="form-group" style={{ flex: 1 }}>
              <label className="form-label">电话</label>
              <input className="input" value={infoPhone} onChange={(e) => setInfoPhone(e.target.value)} style={{ width: '100%' }} />
            </div>
            <div className="form-group" style={{ flex: 1 }}>
              <label className="form-label">邮箱</label>
              <input className="input" value={infoEmail} onChange={(e) => setInfoEmail(e.target.value)} style={{ width: '100%' }} />
            </div>
          </div>
          <div className="form-group">
            <label className="form-label">公司</label>
            <input className="input" value={infoCompany} onChange={(e) => setInfoCompany(e.target.value)} style={{ width: '100%' }} />
          </div>
          <div className="form-row">
            <div className="form-group" style={{ flex: 1 }}>
              <label className="form-label">职位</label>
              <input className="input" value={infoPosition} onChange={(e) => setInfoPosition(e.target.value)} style={{ width: '100%' }} />
            </div>
            <div className="form-group" style={{ flex: 1 }}>
              <label className="form-label">出生日期</label>
              <input type="date" className="input" value={infoBirthday} onChange={(e) => setInfoBirthday(e.target.value)} style={{ width: '100%' }} />
            </div>
          </div>
          <div className="form-group">
            <label className="form-label">区域</label>
            <input className="input" value={infoRegion} onChange={(e) => setInfoRegion(e.target.value)} style={{ width: '100%' }} />
          </div>
        </div>
      </Modal>

      {/* Add Communication Modal */}
      <Modal
        open={addCommOpen}
        title="添加沟通记录"
        onClose={() => setAddCommOpen(false)}
        footer={
          <>
            <Button variant="secondary" size="sm" onClick={() => setAddCommOpen(false)}>取消</Button>
            <Button variant="primary" size="sm" onClick={saveCommunication}>添加</Button>
          </>
        }
      >
        <div className="form-group">
          <label className="form-label"><span className="required" style={{ color: 'red' }}>*</span> 沟通记录</label>
          <textarea
            className="input"
            rows={5}
            placeholder="请填写沟通记录"
            maxLength={500}
            value={commContent}
            onChange={(e) => setCommContent(e.target.value)}
            style={{ width: '100%' }}
          />
          <div className="customer-char-count">{commContent.length}/500</div>
        </div>
      </Modal>

      {/* Add Custom Attribute Modal */}
      <Modal
        open={addAttrOpen}
        title="新建自定义属性"
        onClose={() => setAddAttrOpen(false)}
        footer={
          <>
            <Button variant="secondary" size="sm" onClick={() => setAddAttrOpen(false)}>取消</Button>
            <Button variant="primary" size="sm" onClick={saveAttribute}>确定</Button>
          </>
        }
      >
        <div className="form-group">
          <label className="form-label"><span className="required" style={{ color: 'red' }}>*</span> 属性名称</label>
          <input className="input" placeholder="请输入属性名称" value={attrName} onChange={(e) => setAttrName(e.target.value)} style={{ width: '100%' }} />
        </div>
        <div className="form-group">
          <label className="form-label"><span className="required" style={{ color: 'red' }}>*</span> 属性值</label>
          <input className="input" placeholder="请输入属性值" value={attrValue} onChange={(e) => setAttrValue(e.target.value)} style={{ width: '100%' }} />
        </div>
      </Modal>

      {/* Tag Modal */}
      <CustomerTagModal
        open={tagModalOpen}
        customerId={data?.profile?.id || ''}
        initialTagIds={customerTagIds}
        onClose={() => setTagModalOpen(false)}
        onSaved={() => loadDetail()}
      />
    </>
  )
}

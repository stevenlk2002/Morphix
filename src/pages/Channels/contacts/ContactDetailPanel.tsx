/** 联系人详情（CON 右栏）：归属 / 基本信息 / 沟通记录 / 自定义属性 / 发消息。 */

import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { MessageSquare, Pencil, Check } from 'lucide-react'
import type { ContactDetailDTO, ContactLabelDTO, LabelDTO } from '../../../types/channels'
import { channelsApi } from '../../../api/client'
import { avatarColor, avatarChar } from '../shared/avatar'
import Modal from '../../../components/common/Modal'
import { toast, errText } from '../../../utils/toast'

interface ContactDetailPanelProps {
  detail: ContactDetailDTO | null
  accountName: string
  /** 关联渠道账号 id（用于发消息后端反查 user_id）。 */
  accountId?: string
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="contacts-detail-row">
      <span className="k">{label}</span>
      <span className="v">{value || '--'}</span>
    </div>
  )
}

export default function ContactDetailPanel({ detail, accountName, accountId }: ContactDetailPanelProps) {
  const navigate = useNavigate()
  // iPad 标签（已解析真实名称，来自 ipad_label_map，决策 #2/#9）
  const [ipadLabels, setIpadLabels] = useState<ContactLabelDTO[]>([])

  useEffect(() => {
    if (!detail?.contact || !accountId) {
      setIpadLabels([])
      return
    }
    channelsApi
      .getContactLabels(accountId, detail.contact.id)
      .then(setIpadLabels)
      .catch(() => setIpadLabels([]))
  }, [detail?.contact?.id, accountId])

  // 标签编辑（双写端点，决策 #9）
  const [editOpen, setEditOpen] = useState(false)
  const [allLabels, setAllLabels] = useState<LabelDTO[]>([])
  const [selected, setSelected] = useState<string[]>([])
  const [saving, setSaving] = useState(false)

  const openLabelEditor = () => {
    if (!accountId || !detail?.contact) return
    setSelected(ipadLabels.map((l) => l.labelId))
    setSaving(false)
    channelsApi
      .listLabels(accountId)
      .then(setAllLabels)
      .catch(() => setAllLabels([]))
    setEditOpen(true)
  }

  const toggleLabel = (id: string) =>
    setSelected((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]))

  const saveLabels = () => {
    if (!accountId || !detail?.contact) return
    setSaving(true)
    channelsApi
      .updateContactLabels(accountId, detail.contact!.id, selected)
      .then(() => channelsApi.getContactLabels(accountId, detail.contact!.id))
      .then(setIpadLabels)
      .catch((e) => toast(`保存失败：${errText(e)}`))
      .finally(() => {
        setSaving(false)
        setEditOpen(false)
      })
  }

  if (!detail) {
    return (
      <aside className="contacts-detail">
        <div className="placeholder" style={{ minHeight: 200 }}>
          <h3>选择联系人</h3>
          <p>从中间列表选择联系人查看详情</p>
        </div>
      </aside>
    )
  }

  const { contact, profile, communications, attributes } = detail
  const avatar = avatarColor(contact.id)

  return (
    <aside className="contacts-detail">
      <div className="contacts-detail-head">
        <div className="avatar-sm" style={{ background: avatar }}>
          {avatarChar(contact.name)}
        </div>
        <div>
          <div className="contacts-detail-name">{contact.name}</div>
          <div className="contacts-detail-sub">
            {contact.channel} · 归属于：{accountName || '—'}
          </div>
        </div>
      </div>

      <div className="contacts-detail-section-title">基础信息</div>
      <Row label="备注" value={contact.remark} />
      <Row label="描述" value={contact.description} />
      <Row label="添加时间" value={contact.addTime} />
      <Row label="来源" value={contact.source} />

      <div className="contacts-detail-actions">
        <button
          className="btn btn-primary btn-sm"
          onClick={() =>
            navigate(
              `/channels/sessions?accountId=${encodeURIComponent(
                accountId ?? ''
              )}&contactId=${encodeURIComponent(contact.id)}`
            )
          }
        >
          <MessageSquare size={14} /> 发消息
        </button>
      </div>

      {profile && (
        <>
          <div className="contacts-detail-section-title">客户档案</div>
          <Row label="电话" value={profile.phone} />
          <Row label="邮箱" value={profile.email} />
          <Row label="公司" value={profile.company} />
          <Row label="职位" value={profile.position} />
          <Row label="区域" value={profile.region} />
          <Row label="年龄" value={profile.age != null ? String(profile.age) : ''} />
          <Row label="出生日期" value={profile.birthday} />
          <Row label="添加渠道" value={profile.addChannel} />
          {/* iPad 协议外部联系人标签（真实标签名，来自 ipad_label_map，决策 #2/#9） */}
          <div className="contacts-detail-row contacts-detail-labels" style={{ borderBottom: '1px solid var(--line)' }}>
            <span className="k">
              iPad 标签
              <button type="button" className="contacts-detail-edit" onClick={openLabelEditor} title="编辑标签">
                <Pencil size={13} /> 编辑
              </button>
            </span>
            <span className="v" style={{ textAlign: 'right' }}>
              {ipadLabels.length > 0 ? (
                <span className="ipad-tags">
                  {ipadLabels.map((l) => (
                    <span className="ipad-tag" key={l.labelId}>
                      {l.labelName}
                    </span>
                  ))}
                </span>
              ) : (
                '—'
              )}
            </span>
          </div>
        </>
      )}

      {attributes.length > 0 && (
        <>
          <div className="contacts-detail-section-title">自定义属性</div>
          {attributes.map((a) => (
            <Row key={a.id} label={a.name} value={a.value} />
          ))}
        </>
      )}

      <div className="contacts-detail-section-title">沟通记录（{communications.length}）</div>
      {communications.length === 0 ? (
        <div className="detail-empty">
          <div style={{ fontSize: 32, opacity: 0.3 }}>📝</div>
          <div>暂无沟通记录</div>
        </div>
      ) : (
        communications.map((c) => (
          <div className="comm-item" key={c.id}>
            <div className="comm-meta">
              <span>{c.type}</span>
              <span>{c.createdAt}</span>
            </div>
            <div className="comm-content">{c.content}</div>
            {c.aiSummary && <div className="comm-summary">AI：{c.aiSummary}</div>}
          </div>
        ))
      )}

      {editOpen && (
        <Modal
          open={editOpen}
          title={`编辑标签 · ${contact.name}`}
          onClose={() => setEditOpen(false)}
          footer={
            <>
              <button type="button" className="btn btn-ghost btn-sm" onClick={() => setEditOpen(false)}>
                取消
              </button>
              <button type="button" className="btn btn-primary btn-sm" onClick={saveLabels} disabled={saving}>
                {saving ? '保存中…' : '保存'}
              </button>
            </>
          }
        >
          <div className="label-editor">
            {allLabels.length === 0 ? (
              <div className="detail-empty">暂无可用标签，请先在账号页「同步标签」</div>
            ) : (
              <div className="label-editor-chips">
                {allLabels.map((l) => {
                  const on = selected.includes(l.labelId)
                  return (
                    <button
                      key={l.labelId}
                      type="button"
                      className={`label-chip${on ? ' on' : ''}`}
                      onClick={() => toggleLabel(l.labelId)}
                    >
                      {on && <Check size={13} />}
                      {l.labelName}
                    </button>
                  )
                })}
              </div>
            )}
          </div>
        </Modal>
      )}
    </aside>
  )
}

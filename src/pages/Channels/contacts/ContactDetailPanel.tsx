/** 联系人详情（CON 右栏）：归属 / 基本信息 / 沟通记录 / 自定义属性。 */

import { MessageSquare } from 'lucide-react'
import type { ContactDetailDTO } from '../../../types/channels'
import { avatarColor, avatarChar } from '../shared/avatar'
import { toast } from '../../../utils/toast'

interface ContactDetailPanelProps {
  detail: ContactDetailDTO | null
  accountName: string
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="contacts-detail-row">
      <span className="k">{label}</span>
      <span className="v">{value || '--'}</span>
    </div>
  )
}

export default function ContactDetailPanel({ detail, accountName }: ContactDetailPanelProps) {
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
        <button className="btn btn-primary btn-sm" onClick={() => toast('发消息（P2 暂未开放）')}>
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
    </aside>
  )
}

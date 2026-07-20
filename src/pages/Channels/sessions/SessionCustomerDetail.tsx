/** 会话客户详情（SES 右二栏）：客户详情 / 渠道客户详情 双 Tab。 */

import { useState } from 'react'
import { Plus } from 'lucide-react'
import type { ContactDetailDTO, SessionDTO } from '../../../types/channels'
import { avatarColor, avatarChar } from '../shared/avatar'

interface SessionCustomerDetailProps {
  contact: ContactDetailDTO | null
  session: SessionDTO | null
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="detail-row">
      <span className="detail-row-label">{label}</span>
      <span className="detail-row-value">{value || '--'}</span>
    </div>
  )
}

export default function SessionCustomerDetail({ contact, session }: SessionCustomerDetailProps) {
  const [tab, setTab] = useState<'customer' | 'channel'>('customer')

  const name = contact?.contact.name ?? session?.name ?? '客户'
  const channel = contact?.contact.channel ?? session?.channel ?? ''
  const profile = contact?.profile
  const communications = contact?.communications ?? []
  const avatar = avatarColor(name)

  return (
    <aside className="session-detail">
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
          <div className="detail-avatar">
            <div className="avatar-sm" style={{ background: avatar }}>
              {avatarChar(name)}
            </div>
            <div className="detail-name">{name}</div>
            <div className="detail-channel">{channel}</div>
          </div>
          <div className="detail-section">
            <div className="detail-action">
              <Plus size={13} /> 添加标签
            </div>
            <Row label="备注" value={contact?.contact.remark ?? session?.sessionType ?? ''} />
          </div>
          <div className="detail-section">
            <div className="detail-section-title">基本信息</div>
            <Row label="电话" value={profile?.phone ?? ''} />
            <Row label="邮箱" value={profile?.email ?? ''} />
            <Row label="公司" value={profile?.company ?? ''} />
            <Row label="职位" value={profile?.position ?? ''} />
            <Row label="区域" value={profile?.region ?? ''} />
            <Row label="年龄" value={profile?.age != null ? String(profile.age) : ''} />
            <Row label="出生日期" value={profile?.birthday ?? ''} />
            <Row label="添加时间" value={contact?.contact.addTime ?? session?.addTime ?? ''} />
          </div>
          <div className="detail-section" style={{ borderBottom: 'none' }}>
            <div className="detail-section-title">沟通记录（{communications.length}）</div>
            <button className="btn btn-primary btn-sm" style={{ width: '100%' }}>
              <Plus size={13} /> 添加新沟通记录
            </button>
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
          </div>
        </div>
      ) : (
        <div className="detail-pane active">
          <div className="detail-avatar">
            <div className="avatar-sm" style={{ background: avatar }}>
              {avatarChar(name)}
            </div>
            <div className="detail-name">{name}</div>
            <div className="detail-channel">{channel}</div>
          </div>
          <div className="detail-section" style={{ borderBottom: 'none' }}>
            <Row label="描述" value={contact?.contact.description ?? ''} />
            <Row label="添加时间" value={contact?.contact.addTime ?? session?.addTime ?? ''} />
            <Row label="来源" value={contact?.contact.source ?? ''} />
          </div>
        </div>
      )}
    </aside>
  )
}

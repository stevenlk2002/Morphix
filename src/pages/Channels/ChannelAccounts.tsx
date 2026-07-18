import { useState } from 'react'
import { Plus, Settings, Link2, Unlink } from 'lucide-react'
import Button from '../../components/common/Button'
import '../../pages/prototype.css'

interface ChannelAccount {
  id: string
  name: string
  type: 'wecom' | 'wechat' | 'whatsapp' | 'unknown'
  status: 'online' | 'offline' | 'paused'
  onlineSessions: number
  addedAt: string
}

const TYPE_LABEL: Record<ChannelAccount['type'], string> = {
  wecom: '企业微信',
  wechat: '个人微信',
  whatsapp: 'WhatsApp',
  unknown: '未知',
}

const STATUS_META: Record<ChannelAccount['status'], { label: string; cls: string }> = {
  online: { label: '在线', cls: 'proto-badge-success' },
  offline: { label: '离线', cls: 'proto-badge-neutral' },
  paused: { label: '已暂停', cls: 'proto-badge-warning' },
}

const MOCK: ChannelAccount[] = [
  { id: 'ca-1', name: '微信客服-主号', type: 'wechat', status: 'online', onlineSessions: 86, addedAt: '2025-06-12' },
  { id: 'ca-2', name: '企业微信-销售部', type: 'wecom', status: 'online', onlineSessions: 54, addedAt: '2025-06-20' },
  { id: 'ca-3', name: 'WhatsApp-海外', type: 'whatsapp', status: 'paused', onlineSessions: 0, addedAt: '2025-07-01' },
  { id: 'ca-4', name: '个人微信-客服小号', type: 'wechat', status: 'offline', onlineSessions: 0, addedAt: '2025-07-05' },
]

export default function ChannelAccountsPage() {
  const [accounts] = useState<ChannelAccount[]>(MOCK)

  return (
    <div className="proto-page">
      <div className="page-header">
        <div>
          <h2 className="page-title">渠道账号托管</h2>
          <p className="page-subtitle">管理私域渠道账号的接入与托管状态</p>
        </div>
        <Button icon={<Plus size={16} />}>添加账号</Button>
      </div>

      <div className="proto-card">
        <table className="proto-table">
          <thead>
            <tr>
              <th>账号名称</th>
              <th>渠道类型</th>
              <th>状态</th>
              <th>在线会话</th>
              <th>接入时间</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            {accounts.map((a) => {
              const sm = STATUS_META[a.status]
              return (
                <tr key={a.id}>
                  <td>{a.name}</td>
                  <td>{TYPE_LABEL[a.type]}</td>
                  <td>
                    <span className={`proto-badge ${sm.cls}`}>{sm.label}</span>
                  </td>
                  <td>{a.onlineSessions}</td>
                  <td className="text-secondary">{a.addedAt}</td>
                  <td>
                    <div className="proto-actions">
                      <Button variant="ghost" size="sm" icon={<Settings size={14} />}>
                        设置
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        icon={a.status === 'offline' ? <Link2 size={14} /> : <Unlink size={14} />}
                      >
                        {a.status === 'offline' ? '托管' : '解绑'}
                      </Button>
                    </div>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}

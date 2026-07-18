import { useState } from 'react'
import { Search, UserPlus, Tag } from 'lucide-react'
import Button from '../../components/common/Button'
import '../../pages/prototype.css'

interface Customer {
  id: string
  name: string
  channel: string
  level: '普通' | '会员' | 'VIP'
  tags: string[]
  totalOrders: number
  lastContact: string
}

const LEVEL_META: Record<Customer['level'], string> = {
  普通: 'proto-badge-neutral',
  会员: 'proto-badge-info',
  VIP: 'proto-badge-warning',
}

const MOCK: Customer[] = [
  { id: 'u-1', name: '张敏', channel: '企业微信', level: 'VIP', tags: ['高价值', '复购'], totalOrders: 23, lastContact: '2025-07-18' },
  { id: 'u-2', name: '李雷', channel: '个人微信', level: '会员', tags: ['新客', '价格敏感'], totalOrders: 4, lastContact: '2025-07-17' },
  { id: 'u-3', name: '王芳', channel: 'WhatsApp', level: '会员', tags: ['海外'], totalOrders: 9, lastContact: '2025-07-16' },
  { id: 'u-4', name: '陈静', channel: '企业微信', level: '普通', tags: ['待跟进'], totalOrders: 1, lastContact: '2025-07-15' },
  { id: 'u-5', name: '刘洋', channel: '个人微信', level: '普通', tags: ['新客'], totalOrders: 0, lastContact: '2025-07-14' },
]

export default function CustomerListPage() {
  const [keyword, setKeyword] = useState('')
  const [list] = useState<Customer[]>(MOCK)

  const filtered = list.filter((c) =>
    [c.name, c.channel, c.level, ...c.tags].some((v) =>
      String(v || '').toLowerCase().includes(keyword.trim().toLowerCase())
    )
  )

  return (
    <div className="proto-page">
      <div className="page-header">
        <div>
          <h2 className="page-title">客户管理</h2>
          <p className="page-subtitle">统一视图管理私域客户、标签与价值分层</p>
        </div>
        <Button icon={<UserPlus size={16} />}>新建客户</Button>
      </div>

      <div className="proto-card">
        <div className="material-search" style={{ marginBottom: 16 }}>
          <Search size={16} className="search-icon" />
          <input
            type="text"
            placeholder="搜索客户 / 渠道 / 标签"
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
          />
        </div>
        <table className="proto-table">
          <thead>
            <tr>
              <th>客户</th>
              <th>渠道</th>
              <th>等级</th>
              <th>标签</th>
              <th>累计订单</th>
              <th>最近联系</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((c) => (
              <tr key={c.id}>
                <td>{c.name}</td>
                <td>{c.channel}</td>
                <td>
                  <span className={`proto-badge ${LEVEL_META[c.level]}`}>{c.level}</span>
                </td>
                <td>
                  {c.tags.map((t) => (
                    <span key={t} className="proto-pill">
                      <Tag size={10} /> {t}
                    </span>
                  ))}
                </td>
                <td>{c.totalOrders}</td>
                <td className="text-secondary">{c.lastContact}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

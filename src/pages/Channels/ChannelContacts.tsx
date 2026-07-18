import { useState } from 'react'
import { Search, UserPlus } from 'lucide-react'
import Button from '../../components/common/Button'
import '../../pages/prototype.css'

interface Contact {
  id: string
  name: string
  channel: string
  group?: string
  tags: string[]
  lastActive: string
}

const MOCK: Contact[] = [
  { id: 'c-1', name: '张敏', channel: '企业微信', group: 'VIP 客户群', tags: ['高价值', '复购'], lastActive: '2025-07-18 09:12' },
  { id: 'c-2', name: '李雷', channel: '个人微信', group: '新客群', tags: ['新客'], lastActive: '2025-07-17 21:40' },
  { id: 'c-3', name: '王芳', channel: 'WhatsApp', group: '海外群', tags: ['海外', '高价值'], lastActive: '2025-07-16 14:03' },
  { id: 'c-4', name: '陈静', channel: '企业微信', tags: ['待跟进'], lastActive: '2025-07-15 11:20' },
  { id: 'c-5', name: '刘洋', channel: '个人微信', group: '新客群', tags: ['新客', '价格敏感'], lastActive: '2025-07-14 18:55' },
]

export default function ChannelContactsPage() {
  const [keyword, setKeyword] = useState('')
  const [list] = useState<Contact[]>(MOCK)

  const filtered = list.filter((c) =>
    [c.name, c.channel, c.group, ...c.tags].some((v) =>
      String(v || '').toLowerCase().includes(keyword.trim().toLowerCase())
    )
  )

  return (
    <div className="proto-page">
      <div className="page-header">
        <div>
          <h2 className="page-title">渠道联系人</h2>
          <p className="page-subtitle">查看各渠道下的联系人及其分组与标签</p>
        </div>
        <Button icon={<UserPlus size={16} />}>导入联系人</Button>
      </div>

      <div className="proto-card">
        <div className="material-search" style={{ marginBottom: 16 }}>
          <Search size={16} className="search-icon" />
          <input
            type="text"
            placeholder="搜索联系人 / 分组 / 标签"
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
          />
        </div>
        <table className="proto-table">
          <thead>
            <tr>
              <th>联系人</th>
              <th>渠道</th>
              <th>分组</th>
              <th>标签</th>
              <th>最近活跃</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((c) => (
              <tr key={c.id}>
                <td>{c.name}</td>
                <td>{c.channel}</td>
                <td>{c.group || '—'}</td>
                <td>
                  {c.tags.map((t) => (
                    <span key={t} className="proto-pill">
                      {t}
                    </span>
                  ))}
                </td>
                <td className="text-secondary">{c.lastActive}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

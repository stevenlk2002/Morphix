/** 三栏布局左栏：账号列表（渠道下拉 + 搜索 + 状态 Tab + 账号项），SES/CON 复用。 */

import { useMemo, useState } from 'react'
import { Search, ChevronDown } from 'lucide-react'
import type { AccountDTO } from '../../../types/channels'

const CHANNEL_OPTIONS = [
  { value: 'all', label: '全部渠道' },
  { value: 'wecom', label: '企业微信' },
  { value: 'wechat', label: '微信' },
  { value: 'whatsapp', label: 'WhatsApp' },
  { value: 'business_whatsapp', label: '企业WhatsApp' },
]

const AVATAR_COLORS = ['#4A90D9', '#7fb069', '#e8a649', '#8b5cf6', '#14b8a6', '#ef4444']

function avatarColor(id: string): string {
  let h = 0
  for (let i = 0; i < id.length; i++) h = (h * 31 + id.charCodeAt(i)) >>> 0
  return AVATAR_COLORS[h % AVATAR_COLORS.length]
}

interface AccountListPanelProps {
  /** 账号列表。 */
  accounts: AccountDTO[]
  /** 当前选中账号 id。 */
  selectedAccountId: string | null
  /** 选中账号回调。 */
  onSelect: (accountId: string) => void
}

/**
 * 左栏账号列表。内部维护渠道/关键字/状态筛选，选中态受控于父级。
 */
export default function AccountListPanel({ accounts, selectedAccountId, onSelect }: AccountListPanelProps) {
  const [channel, setChannel] = useState('all')
  const [search, setSearch] = useState('')
  const [status, setStatus] = useState<'all' | 'online' | 'offline'>('all')
  const [channelOpen, setChannelOpen] = useState(false)

  const channelLabel = CHANNEL_OPTIONS.find((o) => o.value === channel)?.label ?? '全部渠道'

  const filtered = useMemo(() => {
    return accounts.filter((a) => {
      if (channel !== 'all' && a.channelType !== channel) return false
      if (status !== 'all' && a.status !== status) return false
      if (search && !a.name.toLowerCase().includes(search.toLowerCase())) return false
      return true
    })
  }, [accounts, channel, status, search])

  return (
    <aside className="session-accounts contacts-accounts">
      <div className="channel-select" onClick={(e) => e.stopPropagation()}>
        <div className="channel-select-trigger" onClick={() => setChannelOpen((v) => !v)}>
          {channelLabel}
          <ChevronDown size={14} />
        </div>
        {channelOpen && (
          <div className="channel-select-dropdown" onClick={(e) => e.stopPropagation()}>
            {CHANNEL_OPTIONS.map((o) => (
              <div
                key={o.value}
                className={`channel-select-option${o.value === channel ? ' active' : ''}`}
                data-value={o.value}
                onClick={() => {
                  setChannel(o.value)
                  setChannelOpen(false)
                }}
              >
                {o.label}
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="session-account-search">
        <input
          className="input"
          style={{ width: '100%' }}
          placeholder="托管账号名称"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <Search size={14} className="session-account-search-icon" />
      </div>

      <div className="account-status-tabs">
        {(['all', 'online', 'offline'] as const).map((s) => (
          <button
            key={s}
            className={`account-status-tab${status === s ? ' active' : ''}`}
            data-status={s}
            onClick={() => setStatus(s)}
          >
            {s === 'all' ? '全部' : s === 'online' ? '在线' : '离线'}
          </button>
        ))}
      </div>

      <div className="session-account-list">
        {filtered.map((a) => (
          <div
            key={a.id}
            className={`session-account${a.id === selectedAccountId ? ' active' : ''}`}
            data-status={a.status}
            data-tooltip={`${a.name} · ${a.channel} · ${a.status === 'online' ? '在线' : '离线'}`}
            onClick={() => onSelect(a.id)}
          >
            <div className="session-account-avatar" style={{ background: avatarColor(a.id) }}>
              {a.name.charAt(0)}
            </div>
            <div className="session-account-info">
              <div className="session-account-name">{a.name}</div>
              <div className="session-account-status">
                <span className={`dot ${a.status === 'online' ? 'online' : 'offline'}`} />
                <span>
                  [{a.status === 'online' ? (a.protocol ? `ipad在线` : '在线') : '离线'}]
                </span>
              </div>
            </div>
          </div>
        ))}
        {filtered.length === 0 && <div className="account-empty">无匹配账号</div>}
      </div>
    </aside>
  )
}

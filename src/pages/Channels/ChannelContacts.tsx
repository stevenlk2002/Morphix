/** 渠道联系人列表（CON）：三栏 — 账号 / 联系人列表 / 联系人详情。 */

import { useEffect, useMemo, useState } from 'react'
import { channelsApi } from '../../api/client'
import type {
  AccountDTO,
  ContactDTO,
  ContactDetailDTO,
} from '../../types/channels'
import AccountListPanel from './shared/AccountListPanel'
import ContactDetailPanel from './contacts/ContactDetailPanel'
import { avatarColor, avatarChar } from './shared/avatar'
import { toast, errText } from '../../utils/toast'
import '../../pages/prototype.css'
import './Channels.css'

type ContactType = 'customer' | 'internal' | 'customer-group' | 'internal-group'
type Status = 'all' | 'online' | 'offline'

export default function ChannelContactsPage() {
  const [accounts, setAccounts] = useState<AccountDTO[]>([])
  const [selectedAccountId, setSelectedAccountId] = useState<string | null>(null)

  const [contacts, setContacts] = useState<ContactDTO[]>([])
  const [selectedContactId, setSelectedContactId] = useState<string | null>(null)
  const [detail, setDetail] = useState<ContactDetailDTO | null>(null)

  const [type, setType] = useState<ContactType>('customer')
  const [status, setStatus] = useState<Status>('all')
  const [search, setSearch] = useState('')

  useEffect(() => {
    channelsApi
      .listAccounts()
      .then((a) => {
        setAccounts(a)
        const preferred = a.find((x) => x.id === 'acc-zhulu')?.id ?? a[0]?.id ?? null
        setSelectedAccountId(preferred)
      })
      .catch((e) => toast(`账号加载失败：${errText(e)}`))
  }, [])

  useEffect(() => {
    if (!selectedAccountId) return
    setSelectedContactId(null)
    setDetail(null)
    const params: Record<string, string> = { accountId: selectedAccountId, type }
    if (status !== 'all') params.status = status
    if (search) params.search = search
    channelsApi
      .listContacts(params)
      .then((list) => {
        setContacts(list)
        if (list[0]) setSelectedContactId(list[0].id)
      })
      .catch((e) => toast(`联系人加载失败：${errText(e)}`))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedAccountId, type, status, search])

  useEffect(() => {
    if (!selectedContactId) return
    channelsApi
      .getContactDetail(selectedContactId)
      .then(setDetail)
      .catch(() => setDetail(null))
  }, [selectedContactId])

  const accountName = useMemo(
    () => accounts.find((a) => a.id === selectedAccountId)?.name ?? '',
    [accounts, selectedAccountId]
  )

  return (
    <div className="contacts-mgmt">
      <AccountListPanel
        accounts={accounts}
        selectedAccountId={selectedAccountId}
        onSelect={setSelectedAccountId}
      />

      <section className="contacts-list">
        <div className="contacts-search-wrap">
          <span className="contacts-search-icon">🔍</span>
          <input
            className="input"
            placeholder="请输入联系人名称/备注"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <div className="contacts-type-tabs">
          {([
            { k: 'customer', l: '客户' },
            { k: 'internal', l: '内部成员' },
            { k: 'customer-group', l: '客户群聊' },
            { k: 'internal-group', l: '内部群聊' },
          ] as const).map((o) => (
            <button
              key={o.k}
              className={`contacts-type-tab${type === o.k ? ' active' : ''}`}
              onClick={() => setType(o.k)}
            >
              {o.l}
            </button>
          ))}
        </div>
        <div className="contacts-status-tabs">
          {([
            { k: 'all', l: '全部' },
            { k: 'online', l: '在线' },
            { k: 'offline', l: '离线' },
          ] as const).map((o) => (
            <button
              key={o.k}
              className={`contacts-status-tab${status === o.k ? ' active' : ''}`}
              onClick={() => setStatus(o.k)}
            >
              {o.l}
            </button>
          ))}
        </div>

        <div className="contacts-items">
          {contacts.map((c) => (
            <div
              key={c.id}
              className={`contacts-item${c.id === selectedContactId ? ' active' : ''}`}
              onClick={() => setSelectedContactId(c.id)}
            >
              <div className="contacts-item-avatar" style={{ background: avatarColor(c.id) }}>
                {avatarChar(c.name)}
              </div>
              <div className="contacts-item-body">
                <div className="contacts-item-top">
                  <span className="contacts-item-name">{c.name}</span>
                  <span className="contacts-item-channel">{c.channel}</span>
                </div>
                <div className="contacts-item-bottom">
                  <span className={`contacts-item-status ${c.status === 'online' ? 'online' : ''}`}>
                    <span className="dot" />
                    {c.status === 'online' ? '在线' : '离线'}
                  </span>
                  <span>归属于：{accountName || '—'}</span>
                </div>
              </div>
            </div>
          ))}
          {contacts.length === 0 && (
            <div className="placeholder" style={{ minHeight: 200 }}>
              <p>该分类下暂无联系人</p>
            </div>
          )}
        </div>
      </section>

      <ContactDetailPanel detail={detail} accountName={accountName} />
    </div>
  )
}

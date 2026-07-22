/** 渠道联系人列表（CON）：三栏 — 账号 / 联系人列表 / 联系人详情。
 *
 * 四 tab（客户 / 内部成员 / 客户群聊 / 内部群聊）均查真实数据：
 * - 客户 / 内部成员 → channel_contacts（listContacts）
 * - 客户群聊 → channel_groups（listGroups，groupType=customer_group，决策 #10）
 * - 内部群聊 → channel_groups（listGroups，groupType=internal_group，Issue #3 补调用）
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { RefreshCw, UserPlus, Tags } from 'lucide-react'
import { channelsApi } from '../../api/client'
import type {
  AccountDTO,
  ContactDTO,
  ContactDetailDTO,
  GroupDTO,
  SyncStatusDTO,
} from '../../types/channels'
import AccountListPanel from './shared/AccountListPanel'
import ContactDetailPanel from './contacts/ContactDetailPanel'
import GroupDetailDrawer from './contacts/GroupDetailDrawer'
import SearchAddContactModal from './contacts/SearchAddContactModal'
import { avatarColor, avatarChar } from './shared/avatar'
import { toast, errText } from '../../utils/toast'
import '../../pages/prototype.css'
import './Channels.css'

type ContactType = 'customer' | 'internal' | 'customer-group' | 'internal-group'
type Status = 'all' | 'online' | 'offline'

/** 列表项（联系人与群统一展示）。 */
type DisplayItem =
  | { kind: 'contact'; id: string; name: string; channel: string; status: string; contact: ContactDTO }
  | { kind: 'group'; id: string; name: string; channel: string; total: number; group: GroupDTO }

export default function ChannelContactsPage() {
  const [accounts, setAccounts] = useState<AccountDTO[]>([])
  const [selectedAccountId, setSelectedAccountId] = useState<string | null>(null)

  const [contacts, setContacts] = useState<ContactDTO[]>([])
  const [groups, setGroups] = useState<GroupDTO[]>([])
  const [selectedContactId, setSelectedContactId] = useState<string | null>(null)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [detail, setDetail] = useState<ContactDetailDTO | null>(null)

  const [type, setType] = useState<ContactType>('customer')
  const [status, setStatus] = useState<Status>('all')
  const [search, setSearch] = useState('')

  // iPad 协议同步状态（手动触发 + 轮询）
  const [syncStatus, setSyncStatus] = useState<SyncStatusDTO | null>(null)
  const [syncBusy, setSyncBusy] = useState(false)
  const syncTimer = useRef<number | null>(null)

  // 群成员抽屉（T04）
  const [groupDetailOpen, setGroupDetailOpen] = useState(false)
  const [groupRoomId, setGroupRoomId] = useState<string | null>(null)

  // 搜索添加外部联系人（P1-2）
  const [searchAddOpen, setSearchAddOpen] = useState(false)

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

  // 按当前筛选条件加载列表（联系人或群）。
  const loadList = useCallback(async () => {
    if (!selectedAccountId) return
    if (type === 'customer-group') {
      const list = await channelsApi.listGroups(selectedAccountId, 'customer_group')
      setGroups(list)
      setSelectedId(list[0]?.id ?? null)
      return
    }
    if (type === 'internal-group') {
      // 内部群聊：与「客户群聊」一致，调用后端群列表接口（groupType=internal_group）。
      const list = await channelsApi.listGroups(selectedAccountId, 'internal_group')
      setGroups(list)
      setContacts([])
      setSelectedId(list[0]?.id ?? null)
      return
    }
    const params: Record<string, string> = { accountId: selectedAccountId, type }
    if (status !== 'all') params.status = status
    if (search) params.search = search
    const list = await channelsApi.listContacts(params)
    setContacts(list)
    setSelectedId(list[0]?.id ?? null)
  }, [selectedAccountId, type, status, search])

  useEffect(() => {
    setSelectedContactId(null)
    setDetail(null)
    setGroupDetailOpen(false)
    setGroupRoomId(null)
    loadList().catch((e) => toast(`加载失败：${errText(e)}`))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loadList])

  // 账号切换 → 加载同步状态
  useEffect(() => {
    if (!selectedAccountId) return
    setSyncStatus(null)
    channelsApi
      .getSyncStatus(selectedAccountId)
      .then(setSyncStatus)
      .catch(() => setSyncStatus(null))
  }, [selectedAccountId])

  // 卸载时清理轮询定时器
  useEffect(() => {
    return () => {
      if (syncTimer.current) window.clearInterval(syncTimer.current)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

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

  const isGroupTab = type === 'customer-group' || type === 'internal-group'

  const displayItems = useMemo<DisplayItem[]>(() => {
    if (isGroupTab) {
      let gs = groups
      if (search) gs = gs.filter((g) => g.name.includes(search))
      return gs.map((g) => ({
        kind: 'group',
        id: g.id,
        name: g.name,
        channel: '群聊',
        total: g.total,
        group: g,
      }))
    }
    return contacts.map((c) => ({
      kind: 'contact',
      id: c.id,
      name: c.name,
      channel: c.channel,
      status: c.status,
      contact: c,
    }))
  }, [isGroupTab, groups, contacts, search])

  // ---- iPad 协议全量同步（手动触发 + 轮询） ----
  const syncRunning = syncBusy || !!syncStatus?.syncing

  const stopSyncPolling = () => {
    if (syncTimer.current) {
      window.clearInterval(syncTimer.current)
      syncTimer.current = null
    }
  }

  const startSyncPolling = (accountId: string) => {
    stopSyncPolling()
    syncTimer.current = window.setInterval(() => {
      channelsApi
        .getSyncStatus(accountId)
        .then((st) => {
          setSyncStatus(st)
          if (!st.syncing) {
            stopSyncPolling()
            loadList().catch(() => undefined)
          }
        })
        .catch(() => stopSyncPolling())
    }, 2000)
  }

  const handleSync = async () => {
    if (!selectedAccountId) return
    setSyncBusy(true)
    try {
      await channelsApi.syncAccount(selectedAccountId)
      toast('已触发后台同步，进度请稍候…')
      startSyncPolling(selectedAccountId)
    } catch (e) {
      toast(`同步触发失败：${errText(e)}`)
    } finally {
      setSyncBusy(false)
    }
  }

  // 同步 iPad 标签（企业 + 个人，决策 #8 / #9）
  const handleSyncLabels = async () => {
    if (!selectedAccountId) return
    try {
      const res = await channelsApi.syncLabels(selectedAccountId)
      if (res.skipped) toast('账号未托管 iPad，跳过标签同步')
      else toast(`标签同步完成：新增 ${res.synced} 个`)
    } catch (e) {
      toast(`标签同步失败：${errText(e)}`)
    }
  }

  // 同步状态颜色（绿=成功 / 蓝=同步中 / 黄=降级 / 红=失败 / 灰=未同步）
  const syncStatusColor = (s?: string) =>
    s === 'success'
      ? '#22c55e'
      : s === 'syncing'
      ? '#3b82f6'
      : s === 'degraded'
      ? '#eab308'
      : s === 'error'
      ? '#ef4444'
      : '#9ca3af'

  const handleItemClick = (it: DisplayItem) => {
    setSelectedId(it.id)
    if (it.kind === 'contact') {
      setSelectedContactId(it.contact.id)
    } else {
      setGroupRoomId(it.group.roomId)
      setGroupDetailOpen(true)
    }
  }

  const renderEmpty = () => {
    if (type === 'internal-group') {
      return <p>该账号下暂无内部群，请先点击「同步」</p>
    }
    if (type === 'customer-group') {
      return <p>该账号下暂无客户群，请先点击「同步」</p>
    }
    return <p>该分类下暂无联系人</p>
  }

  return (
    <div className="contacts-mgmt">
      <AccountListPanel
        accounts={accounts}
        selectedAccountId={selectedAccountId}
        onSelect={setSelectedAccountId}
      />

      <section className="contacts-list">
        <div className="contacts-list-header">
          <div className="contacts-search-wrap">
            <span className="contacts-search-icon">🔍</span>
            <input
              className="input"
              placeholder="请输入联系人名称/备注"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
          <div className="session-sync-wrap">
            <button
              className="btn btn-ghost btn-sm"
              onClick={() => setSearchAddOpen(true)}
              disabled={!selectedAccountId}
            >
              <UserPlus size={14} /> 添加联系人
            </button>
            <button
              className="btn btn-ghost btn-sm"
              onClick={handleSyncLabels}
              disabled={!selectedAccountId}
            >
              <Tags size={14} /> 同步标签
            </button>
            <button
              className="btn btn-ghost btn-sm"
              onClick={handleSync}
              disabled={!selectedAccountId || syncRunning}
            >
              <RefreshCw size={14} className={syncRunning ? 'spin' : ''} />
              {syncRunning ? '同步中…' : '同步'}
            </button>
            {syncStatus?.lastSyncAt && (
              <span
                className="session-sync-status"
                style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}
              >
                <span
                  style={{
                    width: 8,
                    height: 8,
                    borderRadius: '50%',
                    background: syncStatusColor(syncStatus.syncStatus),
                    display: 'inline-block',
                  }}
                />
                {syncStatus.syncStatus === 'degraded'
                  ? '上次降级'
                  : syncStatus.syncStatus === 'error'
                  ? '上次失败'
                  : '已同步'}
                · {syncStatus.lastSyncAt.slice(5, 16)}
              </span>
            )}
          </div>
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
        {!isGroupTab && (
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
        )}

        <div className="contacts-items">
          {displayItems.map((it) => (
            <div
              key={it.id}
              className={`contacts-item${it.id === selectedId ? ' active' : ''}`}
              onClick={() => handleItemClick(it)}
            >
              <div className="contacts-item-avatar" style={{ background: avatarColor(it.id) }}>
                {avatarChar(it.name)}
              </div>
              <div className="contacts-item-body">
                <div className="contacts-item-top">
                  <span className="contacts-item-name">{it.name}</span>
                  <span className="contacts-item-channel">{it.channel}</span>
                </div>
                <div className="contacts-item-bottom">
                  {it.kind === 'group' ? (
                    <span>群成员 {it.total} 人</span>
                  ) : (
                    <>
                      <span className={`contacts-item-status ${it.status === 'online' ? 'online' : ''}`}>
                        <span className="dot" />
                        {it.status === 'online' ? '在线' : '离线'}
                      </span>
                      <span>归属于：{accountName || '—'}</span>
                    </>
                  )}
                </div>
              </div>
            </div>
          ))}
          {displayItems.length === 0 && (
            <div className="placeholder" style={{ minHeight: 200 }}>
              {renderEmpty()}
            </div>
          )}
        </div>
      </section>

      <ContactDetailPanel
        detail={detail}
        accountName={accountName}
        accountId={selectedAccountId ?? ''}
      />

      {groupDetailOpen && (
        <GroupDetailDrawer
          accountId={selectedAccountId ?? ''}
          roomId={groupRoomId}
          onClose={() => setGroupDetailOpen(false)}
        />
      )}

      {searchAddOpen && (
        <SearchAddContactModal
          open={searchAddOpen}
          accountId={selectedAccountId ?? ''}
          onClose={() => setSearchAddOpen(false)}
          onAdded={() => loadList().catch(() => undefined)}
        />
      )}
    </div>
  )
}

/** 渠道会话管理（SES）：四栏工作区 — 账号 / 会话列表 / 聊天 / 客户详情。 */

import { useEffect, useMemo, useRef, useState } from 'react'
import { Globe, RefreshCw } from 'lucide-react'
import { channelsApi } from '../../api/client'
import type {
  AccountDTO,
  ContactDTO,
  ContactDetailDTO,
  GroupDTO,
  HostingBotDTO,
  MessageExtDTO,
  SessionDTO,
  SyncStatusDTO,
  TeamDTO,
} from '../../types/channels'
import TeamSelector from './shared/TeamSelector'
import AccountListPanel from './shared/AccountListPanel'
import SessionChatPanel from './sessions/SessionChatPanel'
import SessionCustomerDetail from './sessions/SessionCustomerDetail'
import { avatarColor, avatarChar } from './shared/avatar'
import { toast, errText } from '../../utils/toast'
import '../../pages/prototype.css'
import './Channels.css'
import { useSearchParams } from 'react-router-dom'

export default function ChannelSessionsPage() {
  const [teams, setTeams] = useState<TeamDTO[]>([])
  const [currentTeamId, setCurrentTeamId] = useState('')
  const [accounts, setAccounts] = useState<AccountDTO[]>([])
  const [selectedAccountId, setSelectedAccountId] = useState<string | null>(null)

  const [bots, setBots] = useState<HostingBotDTO[]>([])
  const [sessions, setSessions] = useState<SessionDTO[]>([])
  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(null)
  const [messages, setMessages] = useState<MessageExtDTO[]>([])
  const [contact, setContact] = useState<ContactDetailDTO | null>(null)
  const [detailOpen, setDetailOpen] = useState(true)

  // 中栏 Tab：会话 / 好友 / 群聊
  const [activeTab, setActiveTab] = useState<'sessions' | 'friends' | 'groups'>('sessions')
  const [friends, setFriends] = useState<ContactDTO[]>([])
  const [groups, setGroups] = useState<GroupDTO[]>([])

  // 列表筛选
  const [readFilter, setReadFilter] = useState<'all' | 'unread'>('all')
  const [hostedFilter, setHostedFilter] = useState<'all' | 'hosted' | 'unhosted'>('all')
  const [search, setSearch] = useState('')

  // 从联系人/群详情「发消息」跳转而来的 URL 参数
  const [searchParams] = useSearchParams()
  const navAccountId = searchParams.get('accountId')
  const navContactId = searchParams.get('contactId')
  const navRoomId = searchParams.get('roomId')

  // iPad 协议同步状态（手动触发 + 轮询）
  const [syncStatus, setSyncStatus] = useState<SyncStatusDTO | null>(null)
  const [syncBusy, setSyncBusy] = useState(false)
  const syncTimer = useRef<number | null>(null)
  // 消息 / 未读实时轮询定时器（P2-4 回调入站 + P2-2 未读实时清零）
  const pollTimer = useRef<number | null>(null)

  const stopPoll = () => {
    if (pollTimer.current) {
      window.clearInterval(pollTimer.current)
      pollTimer.current = null
    }
  }

  useEffect(() => {
    Promise.all([channelsApi.listTeams(), channelsApi.listAccounts(), channelsApi.listHostingBots()])
      .then(([t, a, b]) => {
        setTeams(t)
        setCurrentTeamId(t[0]?.id ?? 'team-initial')
        setAccounts(a)
        setBots(b)
        const preferred = a.find((x) => x.id === 'acc-zhulu')?.id ?? a[0]?.id ?? null
        setSelectedAccountId(preferred)
      })
      .catch((e) => toast(`加载失败：${errText(e)}`))
  }, [])

  // 账号切换 → 加载会话
  useEffect(() => {
    if (!selectedAccountId) return
    setSelectedSessionId(null)
    setMessages([])
    setContact(null)
    const params: Record<string, string> = { accountId: selectedAccountId }
    if (readFilter !== 'all') params.read = readFilter === 'unread' ? 'unread' : 'read'
    if (hostedFilter !== 'all') params.hosted = hostedFilter
    if (search) params.search = search
    channelsApi
      .listSessions(params)
      .then((list) => {
        setSessions(list)
        if (list[0]) setSelectedSessionId(list[0].id)
      })
      .catch((e) => toast(`会话加载失败：${errText(e)}`))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedAccountId, readFilter, hostedFilter, search])

  // 从联系人/群详情「发消息」跳转而来：定位账号
  useEffect(() => {
    if (navAccountId && navAccountId !== selectedAccountId) {
      setSelectedAccountId(navAccountId)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [navAccountId])

  // 账号就绪 + 会话加载完成后，自动选中目标会话
  useEffect(() => {
    if (!navAccountId || selectedAccountId !== navAccountId) return
    if (!navContactId && !navRoomId) return
    const match = sessions.find((s) =>
      navContactId ? s.contactId === navContactId : s.remoteSessionId === navRoomId
    )
    if (match && match.id !== selectedSessionId) {
      setSelectedSessionId(match.id)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessions, navContactId, navRoomId, selectedAccountId, navAccountId])

  // 好友 / 群聊 Tab：按账号加载列表
  useEffect(() => {
    if (!selectedAccountId) return
    if (activeTab === 'friends') {
      channelsApi
        .listContacts({ accountId: selectedAccountId })
        .then(setFriends)
        .catch(() => setFriends([]))
    } else if (activeTab === 'groups') {
      Promise.all([
        channelsApi.listGroups(selectedAccountId, 'customer_group'),
        channelsApi.listGroups(selectedAccountId, 'internal_group'),
      ])
        .then(([a, b]) => setGroups([...a, ...b]))
        .catch(() => setGroups([]))
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedAccountId, activeTab])

  // 账号切换 → 加载同步状态
  useEffect(() => {
    if (!selectedAccountId) return
    setSyncStatus(null)
    channelsApi
      .getSyncStatus(selectedAccountId)
      .then(setSyncStatus)
      .catch(() => setSyncStatus(null))
  }, [selectedAccountId])

  // 会话切换 → 加载消息 + 进入即清除未读 + 触发历史回填（P2-2 / P2-1）
  useEffect(() => {
    if (!selectedSessionId || !selectedAccountId) return
    channelsApi
      .getSessionMessages(selectedAccountId, selectedSessionId)
      .then(setMessages)
      .catch(() => setMessages([]))
    // 进入会话：清除 iPad 侧未读 + 回写本地（P2-2）
    channelsApi.markSessionRead(selectedAccountId, selectedSessionId).catch(() => undefined)
    // 触发历史回填（群 GetGroupMsgList / 1:1 SyncAllData→回调，P2-1）
    channelsApi.backfillSessionMessages(selectedAccountId, selectedSessionId).catch(() => undefined)
    // 已读/回填后刷新会话列表（清除消息列表未读徽标）
    channelsApi.listSessions({ accountId: selectedAccountId }).then(setSessions).catch(() => undefined)
  }, [selectedSessionId, selectedAccountId])

  // 卸载时清理轮询定时器
  useEffect(() => {
    return () => {
      if (syncTimer.current) window.clearInterval(syncTimer.current)
      if (pollTimer.current) window.clearInterval(pollTimer.current)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // 轮询：实时刷新消息（P2-4 回调入站）与会话未读徽标（P2-2 实时清零）
  useEffect(() => {
    if (!selectedSessionId || !selectedAccountId) return
    stopPoll()
    pollTimer.current = window.setInterval(() => {
      channelsApi.getSessionMessages(selectedAccountId, selectedSessionId).then(setMessages).catch(() => undefined)
      channelsApi.listSessions({ accountId: selectedAccountId }).then(setSessions).catch(() => undefined)
    }, 4000)
    return () => stopPoll()
  }, [selectedSessionId, selectedAccountId])

  const selectedSession = useMemo(
    () => sessions.find((s) => s.id === selectedSessionId) ?? null,
    [sessions, selectedSessionId]
  )

  const handleHostingChange = (next: SessionDTO) => {
    setSessions((prev) => prev.map((s) => (s.id === next.id ? next : s)))
  }

  const openByContact = (contactId: string) => {
    const session = sessions.find((s) => s.contactId === contactId)
    if (session) {
      setSelectedSessionId(session.id)
      setActiveTab('sessions')
    } else {
      toast('该好友暂无会话，请先同步或发消息')
    }
  }
  const openByRoom = (roomId: string) => {
    const session = sessions.find((s) => s.remoteSessionId === roomId)
    if (session) {
      setSelectedSessionId(session.id)
      setActiveTab('sessions')
    } else {
      toast('该群聊暂无会话，请先同步')
    }
  }

  const handleMessageSent = (msg: MessageExtDTO) => {
    setMessages((prev) => [...prev, msg])
  }

  // ---- iPad 协议全量同步（手动触发 + 轮询状态） ----
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
            // 同步完成，刷新会话列表
            channelsApi.listSessions({ accountId }).then(setSessions).catch(() => undefined)
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

  return (
    <div className="session-page-shell">
      <div className="session-page-topbar">
        <div className="session-page-topbar-left">
          <TeamSelector teams={teams} currentTeamId={currentTeamId} onSelect={setCurrentTeamId} />
        </div>
        <div className="session-mobile-entry" onClick={() => toast('移动端会话托管（P2 暂未开放）')}>
          <span className="session-mobile-entry-icon">
            <Globe size={14} />
          </span>
          <span>
            您也可以在移动端管理会话托管哦~<span className="session-mobile-entry-link">点击这里</span>
          </span>
        </div>
      </div>

      <div className="session-mgmt">
        <AccountListPanel
          accounts={accounts}
          selectedAccountId={selectedAccountId}
          onSelect={setSelectedAccountId}
        />

        {/* 中栏：会话列表 */}
        <section className="session-main">
          <div className="session-toolbar">
            <div className="session-toolbar-top">
              <div className="session-search">
                <span className="session-search-icon">🔍</span>
                <input
                  className="input"
                  placeholder="请输入会话名称"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                />
              </div>
              <div className="session-sync-wrap">
                <button
                  className="btn btn-ghost btn-sm"
                  onClick={handleSync}
                  disabled={!selectedAccountId || syncRunning}
                >
                  <RefreshCw size={14} className={syncRunning ? 'spin' : ''} />
                  {syncRunning ? '同步中…' : '同步'}
                </button>
                {syncStatus?.lastSyncAt && (
                  <span className="session-sync-status">
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
            <div className="session-filters-row">
              <div className="session-filter-select">
                <div
                  className="session-filter-select-trigger"
                  onClick={(e) => {
                    const dd = e.currentTarget.nextElementSibling as HTMLElement
                    dd.style.display = dd.style.display === 'block' ? 'none' : 'block'
                  }}
                >
                  阅读：{readFilter === 'all' ? '全部' : '未读'}
                </div>
                <div className="session-filter-select-dropdown" style={{ display: 'none' }}>
                  {(['all', 'unread'] as const).map((v) => (
                    <div
                      key={v}
                      className={`session-filter-select-option${readFilter === v ? ' active' : ''}`}
                      onClick={(e) => {
                        setReadFilter(v)
                        ;(e.currentTarget.parentElement as HTMLElement).style.display = 'none'
                        ;(e.currentTarget.parentElement?.previousElementSibling as HTMLElement).textContent =
                          `阅读：${v === 'all' ? '全部' : '未读'}`
                      }}
                    >
                      阅读：{v === 'all' ? '全部' : '未读'}
                    </div>
                  ))}
                </div>
              </div>
              <div className="session-filter-select">
                <div
                  className="session-filter-select-trigger"
                  onClick={(e) => {
                    const dd = e.currentTarget.nextElementSibling as HTMLElement
                    dd.style.display = dd.style.display === 'block' ? 'none' : 'block'
                  }}
                >
                  托管：{hostedFilter === 'all' ? '全部' : hostedFilter === 'hosted' ? '已托管' : '未托管'}
                </div>
                <div className="session-filter-select-dropdown" style={{ display: 'none' }}>
                  {([
                    { v: 'all', l: '全部' },
                    { v: 'hosted', l: '已托管' },
                    { v: 'unhosted', l: '未托管' },
                  ] as const).map((o) => (
                    <div
                      key={o.v}
                      className={`session-filter-select-option${hostedFilter === o.v ? ' active' : ''}`}
                      onClick={(e) => {
                        setHostedFilter(o.v)
                        ;(e.currentTarget.parentElement as HTMLElement).style.display = 'none'
                        ;(e.currentTarget.parentElement?.previousElementSibling as HTMLElement).textContent =
                          `托管：${o.l}`
                      }}
                    >
                      托管：{o.l}
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>

          <div className="detail-tabs">
            <button
              className={`detail-tab${activeTab === 'sessions' ? ' active' : ''}`}
              onClick={() => setActiveTab('sessions')}
            >
              会话
            </button>
            <button
              className={`detail-tab${activeTab === 'friends' ? ' active' : ''}`}
              onClick={() => setActiveTab('friends')}
            >
              好友
            </button>
            <button
              className={`detail-tab${activeTab === 'groups' ? ' active' : ''}`}
              onClick={() => setActiveTab('groups')}
            >
              群聊
            </button>
          </div>

          {activeTab === 'sessions' && (
            <div className="session-list">
              {sessions.map((s) => (
                <div
                  key={s.id}
                  className={`session-row${s.id === selectedSessionId ? ' active' : ''}`}
                  onClick={() => setSelectedSessionId(s.id)}
                >
                  {/* 以下为原 session-row 内容，保持不变 */}
                  <div className="session-row-avatar" style={{ background: avatarColor(s.id) }}>
                    {avatarChar(s.name)}
                  </div>
                  <div className="session-row-body">
                    <div className="session-row-top">
                      <div className="session-row-name-wrap">
                        <span className="session-row-name">{s.name}</span>
                        {s.externalTag && <span className="session-row-tag">{s.externalTag}</span>}
                      </div>
                      <span className="session-row-time">{s.lastTime}</span>
                    </div>
                    <div className="session-row-bottom">
                      <span className="session-row-msg">{s.lastMessage}</span>
                      <span className={`session-row-status ${s.onlineStatus === 'online' ? 'online' : ''}`}>
                        <span className="dot" />
                        {s.onlineStatus === 'online' ? '在线' : '离线'}
                      </span>
                    </div>
                  </div>
                  <div className="session-row-right">
                    {s.unreadCount > 0 && <span className="unread-badge">{s.unreadCount}</span>}
                    {s.owner && <span className="session-row-owner">{s.owner}</span>}
                  </div>
                </div>
              ))}
              {sessions.length === 0 && (
                <div className="placeholder" style={{ minHeight: 200 }}>
                  <p>该账号下暂无会话</p>
                </div>
              )}
            </div>
          )}

          {activeTab === 'friends' && (
            <div className="session-list">
              {friends.map((c) => (
                <div
                  key={c.id}
                  className="session-row"
                  onClick={() => openByContact(c.id)}
                >
                  <div className="session-row-avatar" style={{ background: avatarColor(c.id) }}>
                    {avatarChar(c.nickname || c.name)}
                  </div>
                  <div className="session-row-body">
                    <div className="session-row-top">
                      <span className="session-row-name">{c.nickname || c.name}</span>
                    </div>
                    <div className="session-row-bottom">
                      <span className="session-row-msg">
                        {c.type === 'internal' ? '内部成员' : '客户'}
                        {c.remark ? ` · ${c.remark}` : ''}
                      </span>
                    </div>
                  </div>
                </div>
              ))}
              {friends.length === 0 && (
                <div className="placeholder" style={{ minHeight: 200 }}>
                  <p>该账号下暂无好友</p>
                </div>
              )}
            </div>
          )}

          {activeTab === 'groups' && (
            <div className="session-list">
              {groups.map((g) => (
                <div
                  key={g.id}
                  className="session-row"
                  onClick={() => openByRoom(g.roomId)}
                >
                  <div className="session-row-avatar" style={{ background: avatarColor(g.id) }}>
                    {avatarChar(g.name)}
                  </div>
                  <div className="session-row-body">
                    <div className="session-row-top">
                      <span className="session-row-name">{g.name}</span>
                    </div>
                    <div className="session-row-bottom">
                      <span className="session-row-msg">群成员 {g.total}</span>
                    </div>
                  </div>
                </div>
              ))}
              {groups.length === 0 && (
                <div className="placeholder" style={{ minHeight: 200 }}>
                  <p>该账号下暂无群聊</p>
                </div>
              )}
            </div>
          )}
        </section>

        {/* 右一栏：聊天 */}
        <SessionChatPanel
          session={selectedSession}
          messages={messages}
          bots={bots}
          accountId={selectedAccountId ?? ''}
          onToggleDetail={() => setDetailOpen((v) => !v)}
          onHostingChange={handleHostingChange}
          onMessageSent={handleMessageSent}
        />

        {/* 右二栏：客户详情 */}
        {detailOpen && <SessionCustomerDetail contact={contact} session={selectedSession} />}
      </div>
    </div>
  )
}

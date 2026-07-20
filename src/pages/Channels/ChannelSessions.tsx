/** 渠道会话管理（SES）：四栏工作区 — 账号 / 会话列表 / 聊天 / 客户详情。 */

import { useEffect, useMemo, useState } from 'react'
import { Globe } from 'lucide-react'
import { channelsApi } from '../../api/client'
import type {
  AccountDTO,
  ContactDetailDTO,
  HostingBotDTO,
  MessageDTO,
  SessionDTO,
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

export default function ChannelSessionsPage() {
  const [teams, setTeams] = useState<TeamDTO[]>([])
  const [currentTeamId, setCurrentTeamId] = useState('')
  const [accounts, setAccounts] = useState<AccountDTO[]>([])
  const [selectedAccountId, setSelectedAccountId] = useState<string | null>(null)

  const [bots, setBots] = useState<HostingBotDTO[]>([])
  const [sessions, setSessions] = useState<SessionDTO[]>([])
  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(null)
  const [messages, setMessages] = useState<MessageDTO[]>([])
  const [contact, setContact] = useState<ContactDetailDTO | null>(null)
  const [detailOpen, setDetailOpen] = useState(true)

  // 列表筛选
  const [readFilter, setReadFilter] = useState<'all' | 'unread'>('all')
  const [hostedFilter, setHostedFilter] = useState<'all' | 'hosted' | 'unhosted'>('all')
  const [search, setSearch] = useState('')

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

  // 会话切换 → 加载消息
  useEffect(() => {
    if (!selectedSessionId) return
    channelsApi
      .listSessionMessages(selectedSessionId)
      .then(setMessages)
      .catch(() => setMessages([]))
  }, [selectedSessionId])

  const selectedSession = useMemo(
    () => sessions.find((s) => s.id === selectedSessionId) ?? null,
    [sessions, selectedSessionId]
  )

  const handleHostingChange = (next: SessionDTO) => {
    setSessions((prev) => prev.map((s) => (s.id === next.id ? next : s)))
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

          <div className="session-list">
            {sessions.map((s) => (
              <div
                key={s.id}
                className={`session-row${s.id === selectedSessionId ? ' active' : ''}`}
                onClick={() => setSelectedSessionId(s.id)}
              >
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
        </section>

        {/* 右一栏：聊天 */}
        <SessionChatPanel
          session={selectedSession}
          messages={messages}
          bots={bots}
          accountId={selectedAccountId ?? ''}
          onToggleDetail={() => setDetailOpen((v) => !v)}
          onHostingChange={handleHostingChange}
        />

        {/* 右二栏：客户详情 */}
        {detailOpen && <SessionCustomerDetail contact={contact} session={selectedSession} />}
      </div>
    </div>
  )
}

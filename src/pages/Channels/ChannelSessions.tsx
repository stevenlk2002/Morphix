/** 渠道会话管理（SES）：三栏工作区 — 账号 / 会话列表 / 聊天+客户详情合并区域。 */

import { useEffect, useMemo, useRef, useState } from 'react'
import {
  Globe,
  ArrowUpToLine,
  MessageCircleWarning,
  LocateFixed,
  UsersRound,
  CheckCheck,
} from 'lucide-react'
import { channelsApi, ApiClientError } from '../../api/client'
import type {
  AccountDTO,
  ContactDTO,
  ContactDetailDTO,
  GroupDTO,
  GroupMemberDTO,
  HostingBotDTO,
  MessageExtDTO,
  SessionDTO,
  SyncStatusDTO,
  TeamDTO,
} from '../../types/channels'
import TeamSelector from './shared/TeamSelector'
import AccountListPanel from './shared/AccountListPanel'
import RightPanelArea from './sessions/RightPanelArea'
import { avatarColor, avatarChar } from './shared/avatar'
import { toast, errText } from '../../utils/toast'
import { useResizablePanels } from './shared/useResizablePanels'
import Resizer from './shared/Resizer'
import { useSessionActions } from './shared/useSessionActions'
import CreateGroupModal from './shared/CreateGroupModal'
import '../../pages/prototype.css'
import './Channels.css'
import { useSearchParams } from 'react-router-dom'

const DEFAULT_DETAIL_WIDTH = 360

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

  // 合并区域右栏：客户详情宽度（拖拽）+ 折叠
  const [detailWidth, setDetailWidth] = useState<number>(DEFAULT_DETAIL_WIDTH)
  const [detailCollapsed, setDetailCollapsed] = useState<boolean>(() => {
    try {
      return localStorage.getItem('morphix.detailCollapsed') === '1'
    } catch {
      return false
    }
  })

  // 群聊：群信息 + 群成员
  const [currentGroup, setCurrentGroup] = useState<GroupDTO | null>(null)
  const [groupMembers, setGroupMembers] = useState<GroupMemberDTO[]>([])

  // 统一会话列表（单聊 + 群聊聚合在一起，不再分 Tab）
  const [friends, setFriends] = useState<ContactDTO[]>([])

  // 列表筛选
  const [readFilter, setReadFilter] = useState<'all' | 'unread'>('all')
  const [hostedFilter, setHostedFilter] = useState<'all' | 'hosted' | 'unhosted'>('all')
  const [search, setSearch] = useState('')

  // 建群弹窗开关
  const [createGroupOpen, setCreateGroupOpen] = useState(false)

  // 从联系人/群详情「发消息」跳转而来的 URL 参数
  const [searchParams] = useSearchParams()
  const navAccountId = searchParams.get('accountId')
  const navContactId = searchParams.get('contactId')
  const navRoomId = searchParams.get('roomId')

  // iPad 协议同步状态（手动触发 + 轮询）
  const [, setSyncStatus] = useState<SyncStatusDTO | null>(null)
  const syncTimer = useRef<number | null>(null)
  // 消息 / 未读实时轮询定时器（P2-4 回调入站 + P2-2 未读实时清零）
  const pollTimer = useRef<number | null>(null)

  // 左中栏可拖拽分隔（Q5）：宽度由 CSS 变量驱动 + localStorage 持久化
  const { startResize } = useResizablePanels()
  // 会话列表滚动容器（供 useSessionActions 定位 / 回到顶部）
  const listRef = useRef<HTMLDivElement | null>(null)
  // 进入页自动同步节流（Q7）：同账号 30s 内不重复触发
  const lastAutoSyncAt = useRef<Record<string, number>>({})

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

  // 账号切换 → 加载同步状态
  useEffect(() => {
    if (!selectedAccountId) return
    setSyncStatus(null)
    channelsApi
      .getSyncStatus(selectedAccountId)
      .then(setSyncStatus)
      .catch(() => setSyncStatus(null))
  }, [selectedAccountId])

  // 选中会话变化：群聊时拉取群信息 + 群成员
  useEffect(() => {
    const session = sessions.find((s) => s.id === selectedSessionId)
    if (!session || !selectedAccountId) {
      setCurrentGroup(null)
      setGroupMembers([])
      return
    }
    if (session.sessionType !== '群聊') {
      setCurrentGroup(null)
      setGroupMembers([])
      return
    }
    // 通过 roomId 查群
    const roomId = session.remoteSessionId ?? session.id.split(':').slice(1).join(':')
    if (!roomId) return
    channelsApi
      .listGroups(selectedAccountId)
      .then((list) => {
        const g = list.find((x) => x.roomId === roomId) ?? null
        setCurrentGroup(g)
      })
      .catch(() => setCurrentGroup(null))
    channelsApi
      .getGroupMembers(selectedAccountId, roomId)
      .then((detail) => setGroupMembers(detail.members ?? []))
      .catch(() => setGroupMembers([]))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedSessionId, selectedAccountId])

  const reloadGroupMembers = () => {
    if (!currentGroup || !selectedAccountId) return
    channelsApi
      .getGroupMembers(selectedAccountId, currentGroup.roomId)
      .then((detail) => setGroupMembers(detail.members ?? []))
      .catch(() => setGroupMembers([]))
  }

  // 进入页自动同步（Q2 + Q7）：进入页面或切换账号时触发全量同步，30s 内同账号不重复
  useEffect(() => {
    if (!selectedAccountId) return
    const now = Date.now()
    const last = lastAutoSyncAt.current[selectedAccountId] ?? 0
    if (last && now - last < 30000) return
    lastAutoSyncAt.current[selectedAccountId] = now
    channelsApi
      .syncAccount(selectedAccountId)
      .then(() => startSyncPolling(selectedAccountId))
      .catch((e) => {
        // 409 = 后端正在同步，视为「已跳过」仍启动轮询，不弹错误（决策 §6.2）
        if (e instanceof ApiClientError && e.code === 'HTTP_409') {
          startSyncPolling(selectedAccountId)
        } else {
          toast(`同步触发失败：${errText(e)}`)
        }
      })
    // eslint-disable-next-line react-hooks/exhaustive-deps
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

  // 右栏详情抽屉折叠状态持久化（刷新后记住用户偏好）
  const handleDetailCollapsedChange = (next: boolean) => {
    setDetailCollapsed(next)
    try {
      localStorage.setItem('morphix.detailCollapsed', next ? '1' : '0')
    } catch {
      /* 隐私模式等无 localStorage 时静默忽略 */
    }
  }

  const handleHostingChange = (next: SessionDTO) => {
    setSessions((prev) => prev.map((s) => (s.id === next.id ? next : s)))
  }

  const handleMessageSent = (msg: MessageExtDTO) => {
    setMessages((prev) => [...prev, msg])
  }

  // ---- iPad 协议同步轮询（手动触发也复用） ----
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

  // ---- 中栏会话列表滚动定位 / 一键已读（R5-P0） ----
  const reloadSessions = () => {
    if (!selectedAccountId) return
    const params: Record<string, string> = { accountId: selectedAccountId }
    if (readFilter !== 'all') params.read = readFilter === 'unread' ? 'unread' : 'read'
    if (hostedFilter !== 'all') params.hosted = hostedFilter
    if (search) params.search = search
    channelsApi.listSessions(params).then(setSessions).catch(() => undefined)
  }

  const sessionActions = useSessionActions(sessions, selectedSessionId, listRef, {
    accountId: selectedAccountId ?? '',
    reloadSessions,
    setSelectedSessionId: (id: string) => setSelectedSessionId(id),
  })

  // 会话列表始终挂载（已无 Tab 切换），直接执行滚动类动作
  const ensureSessionsTabThen = (fn: () => void) => {
    fn()
  }

  // ---- 建群（T04） ----
  const openCreateGroup = () => {
    if (!selectedAccountId) {
      toast('请先选择账号')
      return
    }
    // 确保好友列表已加载（建群数据源，复用 listContacts，决策 §6.8）
    if (friends.length === 0) {
      channelsApi
        .listContacts({ accountId: selectedAccountId })
        .then(setFriends)
        .catch(() => setFriends([]))
    }
    setCreateGroupOpen(true)
  }

  const handleGroupCreated = (group: GroupDTO) => {
    setCreateGroupOpen(false)
    // 新群聊已落库并生成会话，重载会话列表即可在统一列表中看到
    channelsApi
      .listSessions({ accountId: selectedAccountId ?? '' })
      .then((list) => {
        setSessions(list)
        const created = list.find((s) => s.remoteSessionId === group.roomId)
        if (created) setSelectedSessionId(created.id)
      })
      .catch(() => undefined)
    toast(`已创建群聊：${group.name}`)
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

        {/* 左中栏可拖拽分隔条（grid 第 2 track，Q5） */}
        <Resizer onResizeStart={startResize} />

        {/* 中栏 + 右栏 合并容器（grid 第 3 track，内部 flex） */}
        <div className="session-mgmt-content">
          {/* 中栏：会话列表 */}
          <section className="session-main">
          {/* 搜索框独占一行（R4-P0） */}
          <div className="session-search-top">
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

          {/* 功能按钮行（R5-P0：5 个图标按钮，hover 显示提示） */}
          <div className="session-action-bar">
            <button
              className="session-action-btn"
              data-tip="回到顶部"
              onClick={() => ensureSessionsTabThen(sessionActions.scrollToTop)}
            >
              <ArrowUpToLine size={16} />
            </button>
            <button
              className="session-action-btn"
              data-tip="定位有未读消息的聊天"
              onClick={() => ensureSessionsTabThen(sessionActions.scrollToFirstUnread)}
            >
              <MessageCircleWarning size={16} />
            </button>
            <button
              className="session-action-btn"
              data-tip="定位当前选中的聊天"
              onClick={() => ensureSessionsTabThen(sessionActions.scrollToSelected)}
            >
              <LocateFixed size={16} />
            </button>
            <button
              className="session-action-btn"
              data-tip="创建群聊"
              onClick={openCreateGroup}
            >
              <UsersRound size={16} />
            </button>
            <button
              className="session-action-btn"
              data-tip="一键已读，一键清除本地的未读状态（不包含原渠道的状态）"
              onClick={sessionActions.markAllReadLocal}
            >
              <CheckCheck size={16} />
            </button>
          </div>

          <div className="session-toolbar">
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

          {/* 统一会话列表：单聊 + 群聊聚合在一列，不再分 Tab */}
          <div className="session-list" ref={listRef}>
            {sessions.map((s) => (
              <div
                key={s.id}
                data-session-id={s.id}
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
                      {s.sessionType === '群聊' && <span className="session-row-type">群</span>}
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

        {/* 合并区域：聊天 + 客户详情/群管理 */}
        <RightPanelArea
          session={selectedSession}
          messages={messages}
          bots={bots}
          account={accounts.find((a) => a.id === selectedAccountId) ?? null}
          contact={contact}
          group={currentGroup}
          detailWidth={detailWidth}
          onDetailWidthChange={setDetailWidth}
          onHostingChange={handleHostingChange}
          onMessageSent={handleMessageSent}
          onClearContext={() => setMessages([])}
          onGroupChanged={(g) => setCurrentGroup(g)}
          groupMembers={groupMembers}
          reloadGroupMembers={reloadGroupMembers}
          onContactUpdated={(c) => setContact(c)}
          onCommunicationAdded={() => { /* 通信记录变更触发器，可用于重载 */ }}
          detailCollapsed={detailCollapsed}
          onDetailCollapsedChange={handleDetailCollapsedChange}
        />
        </div>
      </div>

      {/* 创建群聊弹窗（T04，mock-first 建群，失败仍落库） */}
      {createGroupOpen && selectedAccountId && (
        <CreateGroupModal
          accountId={selectedAccountId}
          friends={friends}
          onClose={() => setCreateGroupOpen(false)}
          onCreate={handleGroupCreated}
        />
      )}
    </div>
  )
}

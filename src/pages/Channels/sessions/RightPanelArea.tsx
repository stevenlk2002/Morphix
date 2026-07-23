/** 合并区域容器：头部 + 聊天 + 详情（可拖拽分隔 + 客户详情可折叠）。 */

import { useRef } from 'react'
import type { MouseEvent as ReactMouseEvent } from 'react'
import { ChevronRight, ChevronLeft } from 'lucide-react'
import type {
  AccountDTO,
  ContactDetailDTO,
  GroupDTO,
  HostingBotDTO,
  MessageExtDTO,
  SessionDTO,
} from '../../../types/channels'
import RightPanelHeader from './RightPanelHeader'
import SessionChatPanel from './SessionChatPanel'
import GroupManagementPanel from './GroupManagementPanel'
import SessionDetailPanel from './SessionDetailPanel'

interface RightPanelAreaProps {
  session: SessionDTO | null
  messages: MessageExtDTO[]
  bots: HostingBotDTO[]
  account: AccountDTO | null
  contact: ContactDetailDTO | null
  group: GroupDTO | null
  /** 详情面板的容器宽度（用于内部分栏，0 = 折叠）。 */
  detailWidth: number
  onDetailWidthChange: (w: number) => void
  /** 托管状态变更。 */
  onHostingChange: (next: SessionDTO) => void
  /** 消息发送（乐观追加）。 */
  onMessageSent?: (msg: MessageExtDTO) => void
  /** 清空上下文。 */
  onClearContext?: () => void
  /** 群操作回传（解散/转让/公告）。 */
  onGroupChanged?: (g: GroupDTO | null) => void
  /** 群成员列表变化（用于面板展示）。 */
  groupMembers: import('../../../types/channels').GroupMemberDTO[]
  reloadGroupMembers: () => void
  /** 单聊详情相关回传。 */
  onContactUpdated?: (contact: ContactDetailDTO) => void
  onCommunicationAdded?: () => void
  /** 折叠状态变化。 */
  detailCollapsed: boolean
  onDetailCollapsedChange: (v: boolean) => void
}

const MIN_DETAIL_WIDTH = 280
const MAX_DETAIL_WIDTH = 520
const DEFAULT_DETAIL_WIDTH = 360

export default function RightPanelArea({
  session,
  messages,
  bots,
  account,
  contact,
  group,
  detailWidth,
  onDetailWidthChange,
  onHostingChange,
  onMessageSent,
  onClearContext,
  onGroupChanged,
  groupMembers,
  reloadGroupMembers,
  onContactUpdated,
  onCommunicationAdded,
  detailCollapsed,
  onDetailCollapsedChange,
}: RightPanelAreaProps) {
  const isGroup = session?.sessionType === '群聊'
  const detailPanelRef = useRef<HTMLDivElement | null>(null)

  // 拖拽调整 detail 宽度
  const startResize = (e: ReactMouseEvent) => {
    e.preventDefault()
    const startX = e.clientX
    const startW = detailWidth || DEFAULT_DETAIL_WIDTH
    let latest = startW
    const onMove = (ev: globalThis.MouseEvent) => {
      // 注意：detail 在右边，鼠标左移 = 宽度增加
      latest = Math.min(
        MAX_DETAIL_WIDTH,
        Math.max(MIN_DETAIL_WIDTH, startW - (ev.clientX - startX))
      )
      onDetailWidthChange(latest)
    }
    const onUp = () => {
      window.removeEventListener('mousemove', onMove)
      window.removeEventListener('mouseup', onUp)
    }
    window.addEventListener('mousemove', onMove)
    window.addEventListener('mouseup', onUp)
  }

  return (
    <section className="right-panel-area">
      <RightPanelHeader
        session={session}
        bots={bots}
        account={account}
        onHostingChange={onHostingChange}
        onClearContext={onClearContext}
      />

      <div className="right-panel-body">
        {/* 聊天 */}
        <div className="right-panel-chat">
          <SessionChatPanel
            session={session}
            messages={messages}
            bots={bots}
            accountId={account?.id ?? ''}
            hideHeader
            onToggleDetail={() => { /* 区域级管理折叠 */ }}
            onHostingChange={onHostingChange}
            onMessageSent={onMessageSent}
          />
        </div>

        {/* 分隔条 */}
        {!detailCollapsed && session && (
          <div className="right-panel-resizer" onMouseDown={startResize} role="separator" />
        )}

        {/* 客户详情/群管理 —— 右侧抽屉，可收缩到最右缘 */}
        {session && (
          <div
            className={`right-panel-detail${detailCollapsed ? ' collapsed' : ''}`}
            ref={detailPanelRef}
            style={{ width: detailWidth || DEFAULT_DETAIL_WIDTH }}
          >
            <button
              className="detail-drawer-handle"
              onClick={() => onDetailCollapsedChange(!detailCollapsed)}
              title={isGroup ? '群管理' : '客户详情'}
              aria-label={detailCollapsed ? '展开详情' : '收起详情'}
            >
              <span className="detail-drawer-label">{isGroup ? '群管理' : '客户详情'}</span>
              {detailCollapsed ? <ChevronLeft size={14} /> : <ChevronRight size={14} />}
            </button>
            <div className="right-panel-detail-inner">
              {isGroup ? (
                <GroupManagementPanel
                  accountId={account?.id ?? ''}
                  group={group}
                  members={groupMembers}
                  onReloadMembers={reloadGroupMembers}
                  onGroupChanged={onGroupChanged}
                />
              ) : (
                <SessionDetailPanel
                  accountId={account?.id ?? ''}
                  contact={contact}
                  onContactUpdated={onContactUpdated}
                  onCommunicationAdded={onCommunicationAdded}
                />
              )}
            </div>
          </div>
        )}
      </div>
    </section>
  )
}

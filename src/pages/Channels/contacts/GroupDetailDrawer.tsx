/** 群成员抽屉（T04）：展示群信息 + 成员列表，支持群发消息。
 *
 * 成员数据由后端 GetRoomUserList 实时拉取并落库（group_members 端点降级已落库成员）。
 */

import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Users, X, MessageSquare } from 'lucide-react'
import Button from '../../../components/common/Button'
import { avatarChar } from '../shared/avatar'
import { channelsApi } from '../../../api/client'
import type { GroupDetailDTO, GroupDTO, GroupMemberDTO } from '../../../types/channels'
import { toast, errText } from '../../../utils/toast'

interface Props {
  accountId: string
  roomId: string | null
  onClose: () => void
}

const AVATAR_COLORS = [
  '#ef4444', '#e8a649', '#4A90D9', '#7fb069', '#8b5cf6',
  '#ec4899', '#14b8a6', '#f59e0b', '#06b6d4', '#84cc16',
  '#3b82f6', '#6366f1', '#a855f7', '#22c55e', '#f97316',
]

function avatarColor(name: string): string {
  let hash = 0
  for (let i = 0; i < (name || '').length; i++) hash = name.charCodeAt(i) + ((hash << 5) - hash)
  return AVATAR_COLORS[Math.abs(hash) % AVATAR_COLORS.length]
}

function sexLabel(sex: number): string {
  if (sex === 1) return '男'
  if (sex === 2) return '女'
  return '未知'
}

export default function GroupDetailDrawer({ accountId, roomId, onClose }: Props) {
  const navigate = useNavigate()
  const [data, setData] = useState<GroupDetailDTO | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!roomId) return
    setLoading(true)
    channelsApi
      .getGroupMembers(accountId, roomId)
      .then(setData)
      .catch((e) => {
        setData(null)
        toast(`加载群成员失败：${errText(e)}`)
      })
      .finally(() => setLoading(false))
  }, [accountId, roomId])

  if (!roomId) return null

  const group: GroupDTO | undefined = data?.group
  const members: GroupMemberDTO[] = data?.members ?? []
  const notice: string = data?.noticeContent || group?.noticeContent || ''
  const total: number = data?.total ?? group?.total ?? 0
  const name: string = group?.name || ''

  return (
    <>
      <div
        style={{
          position: 'fixed', inset: 0, zIndex: 1000, background: 'rgba(0,0,0,0.3)',
          display: 'flex', justifyContent: 'flex-end',
        }}
        onClick={onClose}
      >
        <div
          style={{
            width: 760, maxWidth: '100vw', height: '100%', background: '#fff',
            display: 'flex', flexDirection: 'column', boxShadow: '-4px 0 24px rgba(0,0,0,0.12)',
            animation: 'slideInRight 0.2s ease',
          }}
          onClick={(e) => e.stopPropagation()}
        >
          {/* Header */}
          <div style={{
            display: 'flex', alignItems: 'flex-start', gap: 12,
            padding: '16px 20px', borderBottom: '1px solid var(--border)',
          }}>
            <div style={{
              width: 44, height: 44, borderRadius: '50%', backgroundColor: avatarColor(name),
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              color: '#fff', fontSize: 18, fontWeight: 600, flexShrink: 0,
            }}>
              <Users size={22} />
            </div>
            <div style={{ minWidth: 0, flex: 1 }}>
              <div style={{ fontSize: 16, fontWeight: 700, color: 'var(--text-primary)' }}>{name || '群聊'}</div>
              <div className="group-detail-header-meta">
                {group?.roomId ? `群ID：${group.roomId}` : ''}
              </div>
            </div>
            <button
              onClick={onClose}
              style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-tertiary)', padding: 4 }}
            >
              <X size={20} />
            </button>
          </div>

          {/* Body */}
          <div style={{ flex: 1, overflow: 'hidden', display: 'flex' }}>
            {loading ? (
              <div style={{ padding: 40, textAlign: 'center', width: '100%', color: 'var(--text-tertiary)' }}>加载中...</div>
            ) : !data ? (
              <div style={{ padding: 40, textAlign: 'center', width: '100%', color: 'var(--text-tertiary)' }}>未找到群数据，请先同步</div>
            ) : (
              <div className="customer-detail-wrap" style={{ width: '100%' }}>
                <div className="customer-detail-main">
                  <div className="group-detail-stats">
                    <div className="group-detail-stat"><b>{total}</b>群成员</div>
                    <div className="group-detail-stat"><b>{members.length}</b>已加载</div>
                  </div>

                  {notice && (
                    <>
                      <div className="group-detail-section-title">群公告</div>
                      <div className="group-detail-notice">{notice}</div>
                    </>
                  )}

                  <div className="group-detail-section-title">成员列表（{members.length}）</div>
                  <div className="group-member-list">
                    {members.map((m) => {
                      const displayName = m.roomNickname || m.nickname || m.realname || '成员'
                      return (
                        <div className="group-member-item" key={m.id}>
                          <div className="group-member-avatar" style={{ background: avatarColor(m.id) }}>
                            {avatarChar(displayName)}
                          </div>
                          <div className="group-member-body">
                            <div className="group-member-name">{displayName}</div>
                            <div className="group-member-sub">
                              {m.realname ? `姓名：${m.realname}` : m.nickname ? `昵称：${m.nickname}` : '—'}
                              {m.mobile ? ` · ${m.mobile}` : ''}
                            </div>
                          </div>
                          <div className="group-member-meta">
                            <div>性别：{sexLabel(m.sex)}</div>
                            {m.joinTime ? <div>入群：{m.joinTime.slice(0, 10)}</div> : null}
                          </div>
                        </div>
                      )
                    })}
                    {members.length === 0 && (
                      <div className="detail-empty">
                        <div style={{ fontSize: 32, opacity: 0.3 }}>👥</div>
                        <div>暂无成员数据</div>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Footer */}
          <div style={{
            display: 'flex', justifyContent: 'flex-end', gap: 10,
            padding: '12px 20px', borderTop: '1px solid var(--border)',
          }}>
            <Button variant="secondary" size="sm" onClick={onClose}>关闭</Button>
            <Button
              variant="primary"
              size="sm"
              icon={<MessageSquare size={14} />}
              onClick={() =>
                navigate(
                  `/channels/sessions?accountId=${encodeURIComponent(
                    accountId
                  )}&roomId=${encodeURIComponent(roomId ?? '')}`
                )
              }
            >
              发消息
            </Button>
          </div>
        </div>
      </div>

    </>
  )
}

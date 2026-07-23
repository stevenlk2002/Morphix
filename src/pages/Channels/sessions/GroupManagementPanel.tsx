/** 群管理面板（区域右栏，群聊场景）：群信息/标签/成员/公告/转让/解散。 */

import { useState } from 'react'
import { Search, QrCode, Plus, ChevronRight, Trash2 } from 'lucide-react'
import type { GroupDTO, GroupMemberDTO } from '../../../types/channels'
import { channelsApi } from '../../../api/client'
import { avatarColor, avatarChar } from '../shared/avatar'
import { toast, errText } from '../../../utils/toast'

interface GroupManagementPanelProps {
  accountId: string
  group: GroupDTO | null
  members: GroupMemberDTO[]
  onReloadMembers: () => void
  onGroupChanged?: (g: GroupDTO | null) => void
}

export default function GroupManagementPanel({
  accountId,
  group,
  members,
  onReloadMembers,
  onGroupChanged,
}: GroupManagementPanelProps) {
  const [memberKw, setMemberKw] = useState('')
  const [busy, setBusy] = useState(false)
  const [addPickerOpen, setAddPickerOpen] = useState(false)
  const [contacts, setContacts] = useState<{ id: string; nickname: string; name: string }[]>([])
  const [picked, setPicked] = useState<Set<string>>(new Set())
  const [pickerKw, setPickerKw] = useState('')
  const [noticeOpen, setNoticeOpen] = useState(false)
  const [noticeText, setNoticeText] = useState(group?.noticeContent ?? '')

  if (!group) {
    return (
      <aside className="session-detail group-panel">
        <div className="detail-empty">
          <div style={{ fontSize: 32, opacity: 0.3 }}>💬</div>
          <div>该群未在本系统落库</div>
        </div>
      </aside>
    )
  }

  const filteredMembers = members.filter((m) =>
    (m.nickname || m.realname || '').toLowerCase().includes(memberKw.toLowerCase())
  )

  const openAddPicker = async () => {
    if (!accountId) {
      toast('请先选择账号')
      return
    }
    setAddPickerOpen(true)
    try {
      const list = await channelsApi.listContacts({ accountId })
      setContacts(list as any)
    } catch (e) {
      toast(`加载好友失败：${errText(e)}`)
    }
  }

  const confirmAdd = async () => {
    if (picked.size === 0) {
      toast('请至少选择一位好友')
      return
    }
    setBusy(true)
    try {
      await channelsApi.addGroupMembers(accountId, group.roomId, Array.from(picked))
      toast('已添加群成员')
      setAddPickerOpen(false)
      setPicked(new Set())
      onReloadMembers()
      onGroupChanged?.({ ...group, total: group.total + picked.size })
    } catch (e) {
      toast(`添加失败：${errText(e)}`)
    } finally {
      setBusy(false)
    }
  }

  const removeMember = async (member: GroupMemberDTO) => {
    if (!confirm(`确定移除「${member.nickname || member.realname}」？`)) return
    setBusy(true)
    try {
      await channelsApi.removeGroupMember(accountId, group.roomId, member.userId)
      toast('已移除')
      onReloadMembers()
      onGroupChanged?.({ ...group, total: Math.max(0, group.total - 1) })
    } catch (e) {
      toast(`移除失败：${errText(e)}`)
    } finally {
      setBusy(false)
    }
  }

  const saveNotice = async () => {
    setBusy(true)
    try {
      await channelsApi.setGroupNotice(accountId, group.roomId, noticeText)
      toast('群公告已更新')
      onGroupChanged?.({ ...group, noticeContent: noticeText })
      setNoticeOpen(false)
    } catch (e) {
      toast(`更新失败：${errText(e)}`)
    } finally {
      setBusy(false)
    }
  }

  const transferOwner = async () => {
    const newOwner = prompt('输入新群主的 user_id / 昵称')
    if (!newOwner) return
    try {
      await channelsApi.transferGroupOwner(accountId, group.roomId, newOwner)
      toast('已转让群主')
    } catch (e) {
      toast(`转让失败：${errText(e)}`)
    }
  }

  const dismissGroup = async () => {
    if (!confirm(`确定解散群「${group.name}」？此操作不可撤销！`)) return
    setBusy(true)
    try {
      await channelsApi.dismissGroup(accountId, group.roomId)
      toast('群已解散')
      onGroupChanged?.(null)
    } catch (e) {
      toast(`解散失败：${errText(e)}`)
    } finally {
      setBusy(false)
    }
  }

  const ownerName = members[0]?.nickname || members[0]?.realname || group.name.split(/[、,，\s]/)[0]

  return (
    <aside className="session-detail group-panel">
      <div className="group-panel-header">
        <div
          className="group-panel-avatar"
          style={{ background: avatarColor(group.id) }}
        >
          {avatarChar(group.name)}
        </div>
        <div className="group-panel-name-wrap">
          <div className="group-panel-name">{group.name}</div>
          <div className="group-panel-meta">
            <span className="group-panel-tag">{group.groupType === 'internal_group' ? '内部群' : '外部群'}</span>
            <QrCode size={14} className="group-panel-qr" />
          </div>
        </div>
      </div>
      <div className="group-panel-line">归属账号：{accountId}</div>
      <div className="group-panel-tags">
        <button className="group-tag-add">
          <Plus size={12} /> 添加标签
        </button>
      </div>
      <div className="group-panel-search">
        <Search size={14} className="group-panel-search-icon" />
        <input
          className="input"
          placeholder="搜索群成员"
          value={memberKw}
          onChange={(e) => setMemberKw(e.target.value)}
        />
      </div>

      <div className="group-panel-members">
        {filteredMembers.slice(0, 3).map((m) => (
          <div className="group-member" key={m.id}>
            <div
              className="group-member-avatar"
              style={{ background: avatarColor(m.id) }}
            >
              {avatarChar(m.nickname || m.realname || m.userId)}
            </div>
            <div className="group-member-name">{m.nickname || m.realname || m.userId}</div>
          </div>
        ))}
        <button className="group-member-action" onClick={openAddPicker} disabled={busy}>
          <div className="group-member-action-icon">
            <Plus size={18} />
          </div>
          <div>添加</div>
        </button>
        <button className="group-member-action" disabled={busy || members.length === 0}
          onClick={() => filteredMembers[0] && removeMember(filteredMembers[0])}>
          <div className="group-member-action-icon danger">
            <Trash2 size={16} />
          </div>
          <div>移出</div>
        </button>
      </div>

      <div className="group-panel-owner">
        <div>群主：{ownerName}</div>
      </div>

      <div className="group-panel-row" onClick={transferOwner}>
        <span>转让群主</span>
        <ChevronRight size={14} />
      </div>
      <div className="group-panel-row" onClick={() => { setNoticeText(group.noticeContent || ''); setNoticeOpen(true) }}>
        <span>群公告</span>
        <ChevronRight size={14} />
      </div>

      <div className="group-panel-dismiss">
        <button onClick={dismissGroup} disabled={busy}>解散群聊</button>
      </div>

      {/* 添加成员弹窗 */}
      {addPickerOpen && (
        <div className="modal-overlay" onMouseDown={() => setAddPickerOpen(false)}>
          <div className="modal-panel" onMouseDown={(e) => e.stopPropagation()}
            style={{ width: 'min(420px, calc(100vw - 32px))' }}>
            <div className="modal-header">
              <h3>添加群成员</h3>
              <button className="modal-close" onClick={() => setAddPickerOpen(false)}>✕</button>
            </div>
            <div className="modal-body">
              <div className="contacts-search-wrap" style={{ padding: 0, borderBottom: 'none', marginBottom: 10 }}>
                <span className="contacts-search-icon">🔍</span>
                <input
                  className="input"
                  placeholder="搜索好友"
                  value={pickerKw}
                  onChange={(e) => setPickerKw(e.target.value)}
                />
              </div>
              <div className="session-list" style={{ padding: 0, maxHeight: 320 }}>
                {contacts
                  .filter((c) => (c.nickname || c.name || '').toLowerCase().includes(pickerKw.toLowerCase()))
                  .map((c) => (
                    <label key={c.id} className="session-row" style={{ cursor: 'pointer', gap: 10 }}>
                      <input
                        type="checkbox"
                        checked={picked.has(c.id)}
                        onChange={() => {
                          setPicked((prev) => {
                            const n = new Set(prev)
                            if (n.has(c.id)) n.delete(c.id); else n.add(c.id)
                            return n
                          })
                        }}
                      />
                      <div className="session-row-avatar" style={{ background: avatarColor(c.id) }}>
                        {avatarChar(c.nickname || c.name)}
                      </div>
                      <div className="session-row-name">{c.nickname || c.name}</div>
                    </label>
                  ))}
              </div>
            </div>
            <div className="modal-footer" style={{ justifyContent: 'flex-end' }}>
              <button className="btn btn-ghost btn-sm" onClick={() => setAddPickerOpen(false)} disabled={busy}>取消</button>
              <button className="btn btn-primary btn-sm" onClick={confirmAdd} disabled={busy || picked.size === 0}>
                {busy ? '添加中…' : `确认（${picked.size}）`}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 群公告弹窗 */}
      {noticeOpen && (
        <div className="modal-overlay" onMouseDown={() => setNoticeOpen(false)}>
          <div className="modal-panel" onMouseDown={(e) => e.stopPropagation()}
            style={{ width: 'min(440px, calc(100vw - 32px))' }}>
            <div className="modal-header">
              <h3>群公告</h3>
              <button className="modal-close" onClick={() => setNoticeOpen(false)}>✕</button>
            </div>
            <div className="modal-body">
              <textarea
                className="input"
                rows={6}
                placeholder="编辑群公告"
                value={noticeText}
                onChange={(e) => setNoticeText(e.target.value)}
                style={{ resize: 'vertical' }}
              />
            </div>
            <div className="modal-footer" style={{ justifyContent: 'flex-end' }}>
              <button className="btn btn-ghost btn-sm" onClick={() => setNoticeOpen(false)} disabled={busy}>取消</button>
              <button className="btn btn-primary btn-sm" onClick={saveNotice} disabled={busy}>保存</button>
            </div>
          </div>
        </div>
      )}
    </aside>
  )
}

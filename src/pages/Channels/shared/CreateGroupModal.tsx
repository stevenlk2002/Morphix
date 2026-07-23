import { useMemo, useState } from 'react'
import { channelsApi } from '../../../api/client'
import { toast, errText } from '../../../utils/toast'
import { avatarColor, avatarChar } from './avatar'
import type { ContactDTO, GroupDTO } from '../../../types/channels'

interface CreateGroupModalProps {
  accountId: string
  /** 建群好友数据源（复用 listContacts）。 */
  friends: ContactDTO[]
  onClose: () => void
  /** 建群成功回调（已落库 GroupDTO）。 */
  onCreate: (group: GroupDTO) => void
}

/** 创建群聊弹窗：好友多选 + 关键字过滤 + 可选群名（T04）。 */
export default function CreateGroupModal({
  accountId,
  friends,
  onClose,
  onCreate,
}: CreateGroupModalProps) {
  const [keyword, setKeyword] = useState('')
  const [roomName, setRoomName] = useState('')
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [submitting, setSubmitting] = useState(false)

  const filtered = useMemo(() => {
    const kw = keyword.trim().toLowerCase()
    if (!kw) return friends
    return friends.filter((c) => {
      const name = (c.nickname || c.name || '').toLowerCase()
      const remark = (c.remark || '').toLowerCase()
      return name.includes(kw) || remark.includes(kw)
    })
  }, [friends, keyword])

  const toggle = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const handleConfirm = async () => {
    if (selected.size === 0) {
      toast('请至少选择一位好友')
      return
    }
    setSubmitting(true)
    try {
      const group = await channelsApi.createGroup(accountId, {
        memberIds: Array.from(selected),
        roomName: roomName.trim() || undefined,
      })
      toast('群聊创建成功')
      onCreate(group)
    } catch (e) {
      toast(`创建群聊失败：${errText(e)}`)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="modal-overlay" onMouseDown={onClose}>
      <div
        className="modal-panel"
        onMouseDown={(e) => e.stopPropagation()}
        style={{ width: 'min(440px, calc(100vw - 32px))' }}
      >
        <div className="modal-header">
          <h3>创建群聊</h3>
          <button className="modal-close" onClick={onClose} aria-label="关闭">
            ✕
          </button>
        </div>

        <div className="modal-body">
          <div
            className="contacts-search-wrap"
            style={{ padding: 0, borderBottom: 'none', marginBottom: 10 }}
          >
            <span className="contacts-search-icon">🔍</span>
            <input
              className="input"
              placeholder="搜索好友昵称 / 备注"
              value={keyword}
              onChange={(e) => setKeyword(e.target.value)}
            />
          </div>

          <input
            className="input"
            style={{ marginBottom: 10 }}
            placeholder="群名称（可选）"
            value={roomName}
            onChange={(e) => setRoomName(e.target.value)}
          />

          <div className="session-list" style={{ padding: 0, maxHeight: 320 }}>
            {filtered.map((c) => (
              <label
                key={c.id}
                className="session-row"
                style={{ cursor: 'pointer', gap: 10 }}
              >
                <input
                  type="checkbox"
                  checked={selected.has(c.id)}
                  onChange={() => toggle(c.id)}
                  style={{ flexShrink: 0 }}
                />
                <div
                  className="session-row-avatar"
                  style={{ background: avatarColor(c.id) }}
                >
                  {avatarChar(c.nickname || c.name)}
                </div>
                <div className="session-row-body">
                  <div className="session-row-name">
                    {c.nickname || c.name}
                  </div>
                  <div className="session-row-bottom">
                    <span className="session-row-msg">
                      {c.type === 'internal' ? '内部成员' : '客户'}
                      {c.remark ? ` · ${c.remark}` : ''}
                    </span>
                  </div>
                </div>
              </label>
            ))}
            {filtered.length === 0 && (
              <div className="placeholder" style={{ minHeight: 160 }}>
                <p>没有匹配的好友</p>
              </div>
            )}
          </div>
        </div>

        <div
          className="modal-footer"
          style={{ justifyContent: 'space-between', alignItems: 'center' }}
        >
          <span style={{ fontSize: 13, color: 'var(--muted)' }}>
            已选 {selected.size} 位好友
          </span>
          <div style={{ display: 'inline-flex', gap: 8 }}>
            <button
              className="btn btn-ghost btn-sm"
              onClick={onClose}
              disabled={submitting}
            >
              取消
            </button>
            <button
              className="btn btn-primary btn-sm"
              onClick={handleConfirm}
              disabled={submitting || selected.size === 0}
            >
              {submitting ? '创建中…' : '确认创建'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

/** 团队添加成员弹层：搜索授权用户并多选。 */

import { useEffect, useState } from 'react'
import Modal from '../../../components/common/Modal'
import Button from '../../../components/common/Button'
import { orgApi } from '../../../api/client'
import type { AuthUserDTO } from '../../../api/client'
import { toast, errText } from '../../../utils/toast'

interface AddMemberModalProps {
  open: boolean
  /** 已存在的成员 userId 集合（用于去重提示）。 */
  existingUserIds: string[]
  onClose: () => void
  /** 返回选中的 userId 列表。 */
  onConfirm: (userIds: string[]) => void
}

export default function AddMemberModal({
  open,
  existingUserIds,
  onClose,
  onConfirm,
}: AddMemberModalProps) {
  const [account, setAccount] = useState('')
  const [nickname, setNickname] = useState('')
  const [users, setUsers] = useState<AuthUserDTO[]>([])
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!open) {
      setAccount('')
      setNickname('')
      setUsers([])
      setSelected(new Set())
      return
    }
    handleSearch()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open])

  const handleSearch = async () => {
    setLoading(true)
    try {
      const res = await orgApi.listAuthUsers({ account, nickname })
      setUsers(res)
    } catch (e) {
      toast(`搜索失败：${errText(e)}`)
    } finally {
      setLoading(false)
    }
  }

  const handleReset = () => {
    setAccount('')
    setNickname('')
    setUsers([])
    setSelected(new Set())
  }

  const toggleSelect = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const handleConfirm = () => {
    if (selected.size === 0) {
      toast('请至少选择一位成员')
      return
    }
    onConfirm(Array.from(selected))
  }

  return (
    <Modal
      open={open}
      title="添加成员"
      onClose={onClose}
      width={720}
      footer={
        <div className="team-modal-footer">
          <Button variant="outline" onClick={onClose}>
            取消
          </Button>
          <Button onClick={handleConfirm}>确定选择</Button>
        </div>
      }
    >
      <div className="add-member-modal">
        <div className="add-member-search">
          <div className="add-member-field">
            <label>登录账号</label>
            <input
              className="input"
              placeholder="请输入"
              value={account}
              onChange={(e) => setAccount(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
            />
          </div>
          <div className="add-member-field">
            <label>用户名</label>
            <input
              className="input"
              placeholder="请输入"
              value={nickname}
              onChange={(e) => setNickname(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
            />
          </div>
          <div className="add-member-actions">
            <Button variant="outline" onClick={handleReset}>
              重置
            </Button>
            <Button onClick={handleSearch}>查询</Button>
          </div>
        </div>

        <div className="add-member-table-wrap">
          <table className="add-member-table">
            <thead>
              <tr>
                <th style={{ width: 48 }}>
                  <input
                    type="checkbox"
                    checked={users.length > 0 && users.every((u) => selected.has(u.id))}
                    onChange={(e) => {
                      if (e.target.checked) {
                        setSelected(new Set(users.map((u) => u.id)))
                      } else {
                        setSelected(new Set())
                      }
                    }}
                  />
                </th>
                <th>登录账号</th>
                <th>用户名</th>
                <th>所属角色</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={4} className="add-member-empty">
                    加载中…
                  </td>
                </tr>
              ) : users.length === 0 ? (
                <tr>
                  <td colSpan={4} className="add-member-empty">
                    <div className="add-member-empty-icon">📭</div>
                    <div>暂无数据</div>
                  </td>
                </tr>
              ) : (
                users.map((u) => {
                  const disabled = existingUserIds.includes(u.id)
                  const checked = selected.has(u.id) || disabled
                  return (
                    <tr key={u.id} className={disabled ? 'disabled' : ''}>
                      <td>
                        <input
                          type="checkbox"
                          checked={checked}
                          disabled={disabled}
                          onChange={() => toggleSelect(u.id)}
                        />
                      </td>
                      <td>{u.account}</td>
                      <td>{u.nickname}</td>
                      <td>{u.role}</td>
                    </tr>
                  )
                })
              )}
            </tbody>
          </table>
        </div>
      </div>
    </Modal>
  )
}

import { useEffect, useState } from 'react'
import Modal from '../../components/common/Modal'
import Button from '../../components/common/Button'
import { customerGroupsApi } from '../../api/client'
import { toast } from '../../utils/toast'

interface SelectedCustomer {
  id: string
  name: string
}

interface Props {
  open: boolean
  selectedCustomers: SelectedCustomer[]
  onClose: () => void
  onSaved: () => void
}

/**
 * 创建客户分组弹窗（从客户列表批量选择后创建）。
 * - 输入分组名称
 * - 展示已选客户列表（可移除）
 * - 类型默认 custom
 */
export default function CustomerGroupCreateModal({
  open,
  selectedCustomers,
  onClose,
  onSaved,
}: Props) {
  const [name, setName] = useState('')
  const [members, setMembers] = useState<SelectedCustomer[]>([])
  const [saving, setSaving] = useState(false)

  // 当弹窗打开时同步选中客户
  useEffect(() => {
    if (open) {
      setName('')
      setMembers([...selectedCustomers])
    }
  }, [open, selectedCustomers])

  const removeMember = (id: string) => {
    setMembers((prev) => prev.filter((m) => m.id !== id))
  }

  const handleSave = async () => {
    const trimmed = name.trim()
    if (!trimmed) {
      toast('请输入分组名称')
      return
    }
    setSaving(true)
    try {
      await customerGroupsApi.createWithMembers({
        name: trimmed,
        type: 'custom',
        memberIds: members.map((m) => m.id),
      })
      toast('分组创建成功')
      onSaved()
      onClose()
    } catch {
      toast('创建分组失败')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal
      open={open}
      title="创建新群总分组"
      onClose={onClose}
      width={480}
      footer={
        <>
          <Button variant="secondary" size="sm" onClick={onClose}>
            取消
          </Button>
          <Button
            variant="primary"
            size="sm"
            onClick={handleSave}
            disabled={saving || !name.trim() || members.length === 0}
          >
            确定
          </Button>
        </>
      }
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
        {/* 分组名称 */}
        <div className="form-group">
          <label className="form-label">分组名称</label>
          <input
            className="input"
            type="text"
            placeholder="请输入分组名称"
            value={name}
            onChange={(e) => setName(e.target.value)}
            style={{ width: '100%' }}
            autoFocus
          />
        </div>

        {/* 已选客户列表 */}
        <div className="form-group">
          <label className="form-label">
            已选客户（{members.length}）
          </label>
          {members.length === 0 ? (
            <p className="text-secondary" style={{ fontSize: 13 }}>
              请从客户列表中选择客户
            </p>
          ) : (
            <div
              className="group-create-member-list"
              style={{
                maxHeight: 200,
                overflowY: 'auto',
                border: '1px solid var(--border)',
                borderRadius: 4,
                padding: '4px 0',
              }}
            >
              {members.map((m) => (
                <div
                  key={m.id}
                  className="group-create-member-row"
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: '6px 12px',
                    fontSize: 13,
                  }}
                >
                  <span>{m.name}</span>
                  <button
                    className="btn-ghost"
                    style={{
                      border: 'none',
                      background: 'none',
                      color: 'var(--text-tertiary)',
                      cursor: 'pointer',
                      fontSize: 13,
                      padding: '2px 6px',
                    }}
                    onClick={() => removeMember(m.id)}
                    title="移除"
                  >
                    ✕
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </Modal>
  )
}

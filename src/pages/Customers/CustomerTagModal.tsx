import { useEffect, useState, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import Modal from '../../components/common/Modal'
import Button from '../../components/common/Button'
import { tagGroupsApi } from '../../api/client'
import type { TagGroupDTO, TagDTO } from '../../types/customers'

interface Props {
  open: boolean
  customerId: string
  initialTagIds: string[]
  onClose: () => void
  onSaved: () => void
  /** 批量模式：为多个客户打标签 */
  batchMode?: boolean
  batchCustomerIds?: string[]
}

/**
 * 打标签弹窗（原型 5628-5649）。
 * - 搜索框 + [标签管理]跳转
 * - 标签组列表（热标签徽标）
 * - 勾选 toggle → 确定保存
 */
export default function CustomerTagModal({ open, customerId, initialTagIds, onClose, onSaved, batchMode, batchCustomerIds }: Props) {
  const navigate = useNavigate()
  const [groups, setGroups] = useState<TagGroupDTO[]>([])
  const [search, setSearch] = useState('')
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set(initialTagIds))

  useEffect(() => {
    if (open) {
      tagGroupsApi.list().then(setGroups).catch(() => setGroups([]))
      setSelectedIds(new Set(initialTagIds))
    }
  }, [open, initialTagIds])

  const filtered = useMemo(() => {
    if (!search.trim()) return groups
    const kw = search.trim().toLowerCase()
    return groups
      .map((g) => ({
        ...g,
        tags: g.tags.filter((t) => t.name.toLowerCase().includes(kw)),
      }))
      .filter((g) => g.tags.length > 0)
  }, [groups, search])

  const toggleTag = (tag: TagDTO) => {
    setSelectedIds((prev) => {
      const next = new Set(prev)
      if (next.has(tag.id)) next.delete(tag.id)
      else next.add(tag.id)
      return next
    })
  }

  const clearAll = () => setSelectedIds(new Set())

  const handleSave = async () => {
    const { customersApi } = await import('../../api/client')
    if (batchMode && batchCustomerIds && batchCustomerIds.length > 0) {
      // Batch mode: use batchUpdateTags
      await customersApi.batchUpdateTags({
        contactIds: batchCustomerIds,
        tagIds: Array.from(selectedIds),
        mode: 'add',
      })
    } else {
      await customersApi.setCustomerTags(customerId, Array.from(selectedIds))
    }
    onSaved()
    onClose()
  }

  return (
    <Modal
      open={open}
      title="客户标签"
      onClose={onClose}
      width={520}
      footer={
        <>
          <Button variant="secondary" size="sm" onClick={onClose}>
            取消
          </Button>
          <Button variant="primary" size="sm" onClick={handleSave}>
            确定
          </Button>
        </>
      }
    >
      <div className="customer-tag-modal">
        <div className="customer-tag-search-row">
          <input
            type="text"
            className="input"
            placeholder="搜索"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            style={{ flex: 1 }}
          />
          <Button
            variant="ghost"
            size="sm"
            onClick={() => {
              onClose()
              navigate('/customers/tags')
            }}
          >
            标签管理
          </Button>
        </div>
        <div className="customer-tag-total">
          全部标签组（{filtered.length}）
        </div>
        {filtered.map((g) => (
          <div className="customer-tag-group" key={g.id}>
            <div className="customer-tag-group-title">
              {g.name}
              {g.isHot && (
                <span
                  className="proto-badge proto-badge-warning"
                  style={{ fontSize: 11 }}
                >
                  热标签
                </span>
              )}
            </div>
            <div className="customer-tag-options">
              {g.tags.map((t) => (
                <span
                  key={t.id}
                  className={`customer-tag-option${selectedIds.has(t.id) ? ' selected' : ''}`}
                  onClick={() => toggleTag(t)}
                >
                  {t.name}
                </span>
              ))}
            </div>
          </div>
        ))}
        <div className="customer-tag-clear">
          <label
            className="checkbox-label"
            style={{ cursor: 'pointer' }}
            onClick={clearAll}
          >
            清除已选择标签
          </label>
        </div>
      </div>
    </Modal>
  )
}

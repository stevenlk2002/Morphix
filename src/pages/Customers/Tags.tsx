import { useCallback, useEffect, useState } from 'react'
import { Plus, Pencil, Trash2 } from 'lucide-react'
import Button from '../../components/common/Button'
import Modal from '../../components/common/Modal'
import { tagGroupsApi } from '../../api/client'
import type { TagGroupDTO, TagDTO } from '../../types/customers'
import '../../pages/prototype.css'
import './Tags.css'

/**
 * 标签管理页（/customers/tags）。
 * 从后端 /api/customer-tag-groups 获取数据，支持标签组的增删改。
 */
export default function TagsPage() {
  const [groups, setGroups] = useState<TagGroupDTO[]>([])
  const [loading, setLoading] = useState(true)

  const fetchGroups = useCallback(() => {
    tagGroupsApi
      .list()
      .then((data) => setGroups(data))
      .catch(() => setGroups([]))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    fetchGroups()
  }, [fetchGroups])

  // 创建标签组弹窗
  const [createOpen, setCreateOpen] = useState(false)
  const [groupName, setGroupName] = useState('')
  const [draftTags, setDraftTags] = useState<{ id: string; name: string }[]>([])

  // 编辑标签组弹窗
  const [editGroup, setEditGroup] = useState<TagGroupDTO | null>(null)
  const [editGroupName, setEditGroupName] = useState('')
  const [editDraftTags, setEditDraftTags] = useState<TagDTO[]>([])

  // ---- 创建标签组 ----
  const openCreate = () => {
    setGroupName('')
    setDraftTags([{ id: `draft_${Date.now()}`, name: '' }])
    setCreateOpen(true)
  }

  const addDraftTag = () => {
    setDraftTags((prev) => [...prev, { id: `draft_${Date.now()}_${prev.length}`, name: '' }])
  }

  const updateDraftTagName = (index: number, name: string) => {
    setDraftTags((prev) => prev.map((t, i) => (i === index ? { ...t, name } : t)))
  }

  const removeDraftTag = (index: number) => {
    setDraftTags((prev) => prev.filter((_, i) => i !== index))
  }

  const saveGroup = async () => {
    const name = groupName.trim()
    if (!name) return
    const validTags = draftTags.map((t) => t.name.trim()).filter(Boolean)
    if (validTags.length === 0) return
    await tagGroupsApi.create({
      name,
      isHot: true,
      tags: validTags.map((t) => ({ name: t, color: 'blue' })),
    })
    setCreateOpen(false)
    fetchGroups()
  }

  // ---- 编辑标签组 ----
  const openEditGroup = (g: TagGroupDTO) => {
    setEditGroup(g)
    setEditGroupName(g.name)
    setEditDraftTags([...g.tags])
  }

  const saveEditGroup = async () => {
    if (!editGroup) return
    const name = editGroupName.trim()
    if (!name) return
    await tagGroupsApi.update(editGroup.id, {
      name,
      tags: editDraftTags.map((t) => ({ name: t.name, color: t.color || 'blue' })),
    })
    setEditGroup(null)
    fetchGroups()
  }

  const deleteGroup = async (g: TagGroupDTO) => {
    if (!window.confirm(`确定删除标签组「${g.name}」？该组下所有标签将一并删除。`)) return
    await tagGroupsApi.delete(g.id)
    fetchGroups()
  }

  // 编辑标签组内标签操作
  const addEditTag = () => {
    setEditDraftTags((prev) => [
      ...prev,
      { id: `draft_${Date.now()}`, name: '', color: 'blue' },
    ])
  }

  const updateEditTagName = (index: number, name: string) => {
    setEditDraftTags((prev) => prev.map((t, i) => (i === index ? { ...t, name } : t)))
  }

  const removeEditTag = (index: number) => {
    setEditDraftTags((prev) => prev.filter((_, i) => i !== index))
  }

  if (loading) {
    return (
      <div className="proto-page">
        <div className="proto-card tag-empty-state">
          <p className="text-secondary">加载中...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="proto-page">
      <div className="page-header" style={{ borderBottom: 'none', padding: 0, marginBottom: 16, justifyContent: 'flex-end' }}>
        <Button variant="primary" size="sm" icon={<Plus size={16} />} onClick={openCreate}>
          添加标签组
        </Button>
      </div>

      {groups.length === 0 ? (
        <div className="proto-card tag-empty-state">
          <p className="text-secondary">暂无标签组，点击右上角「添加标签组」开始创建。</p>
        </div>
      ) : (
        groups.map((g) => (
          <div className="proto-card tag-group-card" key={g.id}>
            <div className="tag-group-header">
              <span className="tag-dot" style={{ backgroundColor: '#3b82f6' }} />
              <span className="tag-group-name">{g.name}</span>
              {g.isHot && <span className="proto-badge proto-badge-warning" style={{ fontSize: 11 }}>热标</span>}
              <span className="proto-badge proto-badge-neutral tag-count">{g.tags.length} 个标签</span>
              <div className="tag-group-actions">
                <Button variant="ghost" size="sm" icon={<Pencil size={14} />} onClick={() => openEditGroup(g)}>
                  编辑
                </Button>
                <Button variant="ghost" size="sm" icon={<Trash2 size={14} />} onClick={() => deleteGroup(g)} aria-label="删除组">
                  删除
                </Button>
              </div>
            </div>

            <div className="tag-chips">
              {g.tags.length === 0 ? (
                <span className="text-secondary tag-empty">暂无标签</span>
              ) : (
                g.tags.map((t) => (
                  <span key={t.id} className="tag-chip">
                    {t.name}
                  </span>
                ))
              )}
            </div>
          </div>
        ))
      )}

      {/* 创建标签组 */}
      <Modal
        open={createOpen}
        title="新建标签组"
        onClose={() => setCreateOpen(false)}
        footer={
          <>
            <Button variant="ghost" size="sm" onClick={() => setCreateOpen(false)}>
              取消
            </Button>
            <Button
              variant="primary"
              size="sm"
              icon={<Plus size={14} />}
              onClick={saveGroup}
              disabled={!groupName.trim() || !draftTags.some((t) => t.name.trim())}
            >
              确认
            </Button>
          </>
        }
      >
        <div className="form-group">
          <label className="form-label">
            标签组名称 <span className="required">*</span>
          </label>
          <input
            className="input"
            value={groupName}
            placeholder="请输入标签组名称"
            onChange={(e) => setGroupName(e.target.value)}
          />
        </div>
        <div className="form-group">
          <label className="form-label">
            标签 <span className="required">*</span>
          </label>
          {draftTags.map((t, i) => (
            <div key={t.id} className="tag-input-row" style={{ display: 'flex', gap: 8, marginBottom: 8 }}>
              <input
                className="input"
                value={t.name}
                placeholder="请输入标签"
                onChange={(e) => updateDraftTagName(i, e.target.value)}
              />
              <button
                className="btn-icon tag-input-remove"
                type="button"
                onClick={() => removeDraftTag(i)}
                style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#ef4444' }}
                aria-label={`移除标签 ${i + 1}`}
              >
                <Trash2 size={16} />
              </button>
            </div>
          ))}
          <Button variant="ghost" size="sm" icon={<Plus size={14} />} onClick={addDraftTag}>
            添加标签
          </Button>
        </div>
      </Modal>

      {/* 编辑标签组 */}
      <Modal
        open={editGroup !== null}
        title="编辑标签组"
        onClose={() => setEditGroup(null)}
        footer={
          <>
            <Button variant="ghost" size="sm" onClick={() => setEditGroup(null)}>
              取消
            </Button>
            <Button
              variant="primary"
              size="sm"
              onClick={saveEditGroup}
              disabled={!editGroupName.trim()}
            >
              确认
            </Button>
          </>
        }
      >
        <div className="form-group">
          <label className="form-label">
            标签组名称 <span className="required">*</span>
          </label>
          <input
            className="input"
            value={editGroupName}
            onChange={(e) => setEditGroupName(e.target.value)}
          />
        </div>
        <div className="form-group">
          <label className="form-label">标签</label>
          {editDraftTags.map((t, i) => (
            <div key={t.id || i} className="tag-input-row" style={{ display: 'flex', gap: 8, marginBottom: 8 }}>
              <input
                className="input"
                value={t.name}
                placeholder="请输入标签"
                onChange={(e) => updateEditTagName(i, e.target.value)}
              />
              <button
                className="btn-icon tag-input-remove"
                type="button"
                onClick={() => removeEditTag(i)}
                style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#ef4444' }}
              >
                <Trash2 size={16} />
              </button>
            </div>
          ))}
          <Button variant="ghost" size="sm" icon={<Plus size={14} />} onClick={addEditTag}>
            添加标签
          </Button>
        </div>
      </Modal>
    </div>
  )
}

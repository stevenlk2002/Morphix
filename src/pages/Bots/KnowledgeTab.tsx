import { useState, useEffect, useRef } from 'react'
import { Plus, Search, Edit2, Trash2, MoreHorizontal, FileText } from 'lucide-react'
import Button from '../../components/common/Button'
import { toast } from '../../utils/toast'
import { knowledgeApi, KnowledgeItemDTO } from '../../api/client'
import './KnowledgeTab.css'

interface BotRef {
  id: string
  name?: string
}

/** 知识条目（前端结构，与 KnowledgeItemDTO 对齐）。 */
interface KnowledgeItem {
  id: string
  question: string
  answer: string
  tags: string[]
  source: string
  kind: string
  creator: string
  createdAt: string
  updatedAt: string
}

/** 侧栏知识库分类（common=常见问题 / correction=纠偏知识）。 */
type KnowledgeKind = 'common' | 'correction'

/** 弹窗状态。 */
type ModalState = null | { mode: 'create' } | { mode: 'edit'; item: KnowledgeItem }

/** 后端 DTO → 前端结构。 */
function toItem(dto: KnowledgeItemDTO): KnowledgeItem {
  return {
    id: dto.id,
    question: dto.question,
    answer: dto.answer,
    tags: dto.tags ?? [],
    source: dto.source ?? '',
    kind: dto.kind,
    creator: dto.creator ?? 'system',
    createdAt: dto.createdAt,
    updatedAt: dto.updatedAt,
  }
}

/**
 * 知识内容 Tab（对齐 prototype robot-train 的 knowledge-pane）。
 * 左侧知识库侧栏（常见问题 / 纠偏知识 + 新建），右侧工具栏 + 表格。
 * 「删除知识库」= 真实删除整库（按 bot_id + kind）；编辑知识库保持占位提示。
 * 数据全部来自真实后端（knowledgeApi）。
 */
export default function KnowledgeTab({ bot }: { bot: BotRef }) {
  const [kind, setKind] = useState<KnowledgeKind>('common')
  const [items, setItems] = useState<KnowledgeItem[]>([])
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(false)
  const [selectedIds, setSelectedIds] = useState<string[]>([])
  const [modal, setModal] = useState<ModalState>(null)
  const [openMenu, setOpenMenu] = useState<KnowledgeKind | null>(null)
  const menuRef = useRef<HTMLDivElement>(null)

  /** 加载知识条目（按 kind + 关键词）。 */
  const loadItems = async (nextKind?: KnowledgeKind, nextSearch?: string) => {
    const useKind = nextKind ?? kind
    const useSearch = nextSearch ?? search
    try {
      setLoading(true)
      const dtos = await knowledgeApi.listByBot(bot.id, {
        kind: useKind,
        search: useSearch || undefined,
      })
      setItems((dtos as KnowledgeItemDTO[]).map(toItem))
      setSelectedIds([])
    } catch (e) {
      toast(`加载知识失败：${(e as Error).message}`)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadItems()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [bot.id])

  /** 切换分类（常见问题 / 纠偏知识）。 */
  const switchKind = (next: KnowledgeKind) => {
    setKind(next)
    setOpenMenu(null)
    loadItems(next, search)
  }

  /** 搜索（输入即查，防抖由 onChange 直接触发即可，数据量小）。 */
  const onSearch = (value: string) => {
    setSearch(value)
    loadItems(kind, value)
  }

  /** 点击侧栏「更多」切换下拉。 */
  const toggleMenu = (k: KnowledgeKind) => {
    setOpenMenu((prev) => (prev === k ? null : k))
  }

  /** 编辑知识库（占位提示）。 */
  const editKnowledgeBase = (k: KnowledgeKind) => {
    setOpenMenu(null)
    toast(`编辑${k === 'common' ? '常见问题' : '纠偏知识'}（演示环境暂未开放）`)
  }

  /** 删除知识库（真实硬删整库）。 */
  const deleteKnowledgeBase = (k: KnowledgeKind) => {
    setOpenMenu(null)
    const label = k === 'common' ? '常见问题' : '纠偏知识'
    if (!window.confirm(`确定删除「${label}」整个知识库吗？该操作不可恢复。`)) return
    knowledgeApi
      .deleteByKind(bot.id, k)
      .then((res) => {
        toast(`已删除「${label}」共 ${res.deleted} 条`)
        loadItems(kind, search)
      })
      .catch((e) => toast(`删除失败：${(e as Error).message}`))
  }

  /** 单个删除。 */
  const handleDelete = (item: KnowledgeItem) => {
    if (!window.confirm('确定删除这条知识吗？')) return
    knowledgeApi
      .delete(item.id)
      .then(() => {
        toast('已删除知识')
        loadItems(kind, search)
      })
      .catch((e) => toast(`删除失败：${(e as Error).message}`))
  }

  /** 批量删除（选中项）。 */
  const handleBatchDelete = () => {
    if (selectedIds.length === 0) return
    if (!window.confirm(`确定删除选中的 ${selectedIds.length} 条知识吗？`)) return
    knowledgeApi
      .batchDelete(bot.id, selectedIds)
      .then((res) => {
        toast(`已批量删除 ${res.deleted} 条知识`)
        loadItems(kind, search)
      })
      .catch((e) => toast(`批量删除失败：${(e as Error).message}`))
  }

  /** 保存（新增 / 编辑 共用）。 */
  const handleSave = (payload: {
    question: string
    answer: string
    tags: string[]
    source: string | null
    kind: KnowledgeKind
  }) => {
    if (modal?.mode === 'edit') {
      const id = modal.item.id
      knowledgeApi
        .update(id, {
          question: payload.question,
          answer: payload.answer,
          tags: payload.tags,
          source: payload.source ?? '',
          kind: payload.kind,
        })
        .then(() => {
          toast('已更新知识')
          setModal(null)
          loadItems(kind, search)
        })
        .catch((e) => toast(`更新失败：${(e as Error).message}`))
    } else {
      knowledgeApi
        .create(bot.id, {
          question: payload.question,
          answer: payload.answer,
          tags: payload.tags,
          source: payload.source ?? '',
          kind: payload.kind,
          creator: bot.name ?? 'system',
        })
        .then(() => {
          toast('已添加知识')
          setModal(null)
          loadItems(kind, search)
        })
        .catch((e) => toast(`添加失败：${(e as Error).message}`))
    }
  }

  const allChecked = items.length > 0 && selectedIds.length === items.length
  const toggleSelectAll = () => {
    setSelectedIds(allChecked ? [] : items.map((i) => i.id))
  }
  const toggleSelect = (id: string) => {
    setSelectedIds((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]))
  }

  // 点击空白处关闭侧栏下拉
  useEffect(() => {
    if (!openMenu) return
    const onDoc = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setOpenMenu(null)
      }
    }
    document.addEventListener('mousedown', onDoc)
    return () => document.removeEventListener('mousedown', onDoc)
  }, [openMenu])

  return (
    <div className="knowledge-pane">
      {/* 左侧知识库侧栏 */}
      <aside className="knowledge-sidebar">
        <div className="knowledge-menu" ref={menuRef}>
          {(
            [
              { key: 'common', label: '常见问题', icon: <FileText size={16} /> },
              { key: 'correction', label: '纠偏知识', icon: <Edit2 size={16} /> },
            ] as { key: KnowledgeKind; label: string; icon: React.ReactNode }[]
          ).map((m) => (
            <div
              key={m.key}
              className={`knowledge-menu-item ${kind === m.key ? 'active' : ''}`}
              onClick={() => switchKind(m.key)}
            >
              <span className="menu-label">
                {m.icon} {m.label}
              </span>
              <div className="knowledge-menu-more-wrap">
                <button
                  className="menu-more"
                  title="更多"
                  onClick={(e) => {
                    e.stopPropagation()
                    toggleMenu(m.key)
                  }}
                >
                  <MoreHorizontal size={16} />
                </button>
                {openMenu === m.key && (
                  <div className="knowledge-menu-dropdown">
                    <div
                      className="knowledge-menu-option"
                      onClick={(e) => {
                        e.stopPropagation()
                        editKnowledgeBase(m.key)
                      }}
                    >
                      <Edit2 size={14} /> 编辑
                    </div>
                    <div
                      className="knowledge-menu-option"
                      onClick={(e) => {
                        e.stopPropagation()
                        deleteKnowledgeBase(m.key)
                      }}
                    >
                      <Trash2 size={14} /> 删除
                    </div>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
        <div className="knowledge-new-base">
          <button onClick={() => toast('新建知识库（演示环境暂未开放）')}>
            <Plus size={16} /> 新建知识库
          </button>
        </div>
      </aside>

      {/* 右侧主区 */}
      <main className="knowledge-main">
        <div className="knowledge-toolbar">
          <div className="knowledge-toolbar-left">
            <label className="knowledge-select-all">
              <input
                type="checkbox"
                checked={allChecked}
                onChange={toggleSelectAll}
                disabled={items.length === 0}
              />
              <span>跨页全选</span>
            </label>
            {selectedIds.length > 0 && (
              <Button
                variant="danger"
                size="sm"
                icon={<Trash2 size={14} />}
                onClick={handleBatchDelete}
              >
                批量删除 ({selectedIds.length})
              </Button>
            )}
            <button
              className="btn-knowledge-add"
              onClick={() => setModal({ mode: 'create' })}
            >
              <Plus size={14} /> {kind === 'common' ? '增加常见问题' : '增加纠偏知识'}
            </button>
            <button className="btn-knowledge-source" onClick={() => toast('来源记录（演示环境暂未开放）')}>
              来源记录
            </button>
          </div>
          <div className="knowledge-search">
            <Search size={16} />
            <input
              type="text"
              placeholder="搜索..."
              value={search}
              onChange={(e) => onSearch(e.target.value)}
            />
          </div>
        </div>

        <div className="knowledge-table">
          <table>
            <thead>
              <tr>
                <th style={{ width: 40 }}>
                  <input
                    type="checkbox"
                    checked={allChecked}
                    onChange={toggleSelectAll}
                    disabled={items.length === 0}
                  />
                </th>
                <th>问题</th>
                <th>回答</th>
                <th>来源</th>
                <th>创建者</th>
                <th>创建时间</th>
                <th>修改时间</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={7}>
                    <div className="knowledge-loading">加载中…</div>
                  </td>
                </tr>
              ) : items.length === 0 ? (
                <tr>
                  <td colSpan={7}>
                    <div className="knowledge-empty">
                      <svg viewBox="0 0 120 120" fill="none" stroke="currentColor" strokeWidth={1.5}>
                        <rect x="20" y="15" width="60" height="75" rx="4" fill="currentColor" fillOpacity="0.06" />
                        <path d="M20 25h60M20 40h45M20 55h45M20 70h30" />
                        <circle cx="90" cy="85" r="18" fill="currentColor" fillOpacity="0.08" />
                        <path d="M90 73v12l-8 8M82 93l8-8 8 8" />
                      </svg>
                      <div className="knowledge-empty-text">暂无内容</div>
                    </div>
                  </td>
                </tr>
              ) : (
                items.map((item) => (
                  <tr key={item.id}>
                    <td>
                      <input
                        type="checkbox"
                        checked={selectedIds.includes(item.id)}
                        onChange={() => toggleSelect(item.id)}
                      />
                    </td>
                    <td className="cell-question">{item.question}</td>
                    <td className="cell-answer">{item.answer}</td>
                    <td>{item.source || '—'}</td>
                    <td>{item.creator || '—'}</td>
                    <td className="cell-time">{item.createdAt}</td>
                    <td className="cell-time">{item.updatedAt}</td>
                    <td className="cell-actions">
                      <button
                        type="button"
                        className="action-btn"
                        title="编辑"
                        onClick={() => setModal({ mode: 'edit', item })}
                      >
                        <Edit2 size={14} />
                      </button>
                      <button
                        type="button"
                        className="action-btn action-btn-danger"
                        title="删除"
                        onClick={() => handleDelete(item)}
                      >
                        <Trash2 size={14} />
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </main>

      {modal && (
        <KnowledgeModal
          kind={kind}
          initial={modal.mode === 'edit' ? modal.item : null}
          onClose={() => setModal(null)}
          onSave={handleSave}
        />
      )}
    </div>
  )
}

interface KnowledgeForm {
  question: string
  answer: string
  tags: string
  source: string
}

function KnowledgeModal({
  kind,
  initial,
  onClose,
  onSave,
}: {
  kind: KnowledgeKind
  initial: KnowledgeItem | null
  onClose: () => void
  onSave: (payload: {
    question: string
    answer: string
    tags: string[]
    source: string | null
    kind: KnowledgeKind
  }) => void
}) {
  const [form, setForm] = useState<KnowledgeForm>({
    question: initial?.question || '',
    answer: initial?.answer || '',
    tags: (initial?.tags ?? []).join(', '),
    source: initial?.source || '',
  })

  const handleChange = (field: keyof KnowledgeForm) => (
    e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>
  ) => {
    setForm({ ...form, [field]: e.target.value })
  }

  const handleSubmit = () => {
    if (!form.question.trim()) {
      toast('请填写问题')
      return
    }
    if (!form.answer.trim()) {
      toast('请填写答案')
      return
    }
    onSave({
      question: form.question.trim(),
      answer: form.answer.trim(),
      tags: form.tags
        .split(',')
        .map((t) => t.trim())
        .filter(Boolean),
      source: form.source.trim() || null,
      kind,
    })
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <h3 className="modal-title">{initial ? '编辑知识' : '添加知识'}</h3>
        <div className="modal-field">
          <label>问题 *</label>
          <input
            type="text"
            value={form.question}
            onChange={handleChange('question')}
            placeholder="用户可能问的问题"
          />
        </div>
        <div className="modal-field">
          <label>答案 *</label>
          <textarea
            rows={4}
            value={form.answer}
            onChange={handleChange('answer')}
            placeholder="对应的回答内容"
          />
        </div>
        <div className="modal-field">
          <label>标签（逗号分隔）</label>
          <input
            type="text"
            value={form.tags}
            onChange={handleChange('tags')}
            placeholder="例如：价格, 优惠, 售后"
          />
        </div>
        <div className="modal-field">
          <label>来源（可选）</label>
          <input
            type="text"
            value={form.source}
            onChange={handleChange('source')}
            placeholder="例如：官网FAQ"
          />
        </div>
        <div className="modal-actions">
          <Button variant="ghost" size="sm" onClick={onClose}>
            取消
          </Button>
          <Button variant="primary" size="sm" onClick={handleSubmit}>
            保存
          </Button>
        </div>
      </div>
    </div>
  )
}

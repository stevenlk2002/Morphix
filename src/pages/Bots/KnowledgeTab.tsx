import { useState, useEffect } from 'react'
import { Plus, Search, Edit2, Trash2, Tag } from 'lucide-react'
import Button from '../../components/common/Button'
import { knowledgeApi } from '../../api/client'
import './KnowledgeTab.css'

interface BotRef {
  id: string
}

interface KnowledgeItem {
  id: string
  question: string
  answer: string
  tags?: string[] | null
  source?: string | null
  updatedAt?: string
}

type ModalState = null | 'create' | { id: string; question: string; answer: string; tags: string; source: string }

export default function KnowledgeTab({ bot }: { bot: BotRef }) {
  const [knowledge, setKnowledge] = useState<KnowledgeItem[]>([])
  const [searchTerm, setSearchTerm] = useState('')
  const [loading, setLoading] = useState(true)
  const [modal, setModal] = useState<ModalState>(null)

  useEffect(() => {
    loadKnowledge()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [bot.id])

  const loadKnowledge = async () => {
    try {
      const data = await knowledgeApi.listByBot(bot.id)
      setKnowledge(data as KnowledgeItem[])
    } catch (error) {
      console.error('加载知识库失败:', error)
    } finally {
      setLoading(false)
    }
  }

  const filteredKnowledge = knowledge.filter(
    (item) =>
      item.question.includes(searchTerm) ||
      item.answer.includes(searchTerm) ||
      (item.tags || []).some((tag) => tag.includes(searchTerm))
  )

  const handleDelete = async (id: string) => {
    if (!confirm('确定删除这条知识吗？')) return
    try {
      await knowledgeApi.delete(id)
      setKnowledge(knowledge.filter((item) => item.id !== id))
    } catch (error) {
      console.error('删除失败:', error)
      alert('删除失败，请重试')
    }
  }

  const handleSave = async (payload: { question: string; answer: string; tags: string[]; source: string | null }, editingId?: string) => {
    try {
      if (editingId) {
        const updated = await knowledgeApi.update(editingId, payload)
        setKnowledge(
          knowledge.map((item) => (item.id === editingId ? (updated as KnowledgeItem) : item))
        )
      } else {
        const created = await knowledgeApi.create(bot.id, payload)
        setKnowledge([created as KnowledgeItem, ...knowledge])
      }
      setModal(null)
    } catch (error) {
      console.error('保存失败:', error)
      alert('保存失败，请重试')
    }
  }

  if (loading) {
    return <div className="knowledge-loading">加载中...</div>
  }

  return (
    <div className="knowledge-tab">
      <div className="knowledge-header">
        <div className="knowledge-search">
          <Search size={16} className="search-icon" />
          <input
            type="text"
            placeholder="搜索知识库..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
        </div>
        <Button
          variant="primary"
          size="sm"
          icon={<Plus size={16} />}
          onClick={() => setModal('create')}
        >
          添加知识
        </Button>
      </div>

      <div className="knowledge-stats">
        <div className="stat-badge">
          <span className="stat-badge-label">总条目</span>
          <span className="stat-badge-value">{knowledge.length}</span>
        </div>
        <div className="stat-badge">
          <span className="stat-badge-label">今日新增</span>
          <span className="stat-badge-value">—</span>
        </div>
        <div className="stat-badge">
          <span className="stat-badge-label">待审核</span>
          <span className="stat-badge-value">0</span>
        </div>
      </div>

      <div className="knowledge-list">
        {filteredKnowledge.map((item) => (
          <div key={item.id} className="knowledge-card">
            <div className="knowledge-card-header">
              <h4 className="knowledge-question">{item.question}</h4>
              <div className="knowledge-actions">
                <button
                  type="button"
                  className="action-btn"
                  title="编辑"
                  onClick={() =>
                    setModal({
                      id: item.id,
                      question: item.question,
                      answer: item.answer,
                      tags: (item.tags || []).join(', '),
                      source: item.source || '',
                    })
                  }
                >
                  <Edit2 size={14} />
                </button>
                <button
                  type="button"
                  className="action-btn action-btn-danger"
                  title="删除"
                  onClick={() => handleDelete(item.id)}
                >
                  <Trash2 size={14} />
                </button>
              </div>
            </div>

            <p className="knowledge-answer">{item.answer}</p>

            <div className="knowledge-footer">
              <div className="knowledge-tags">
                {(item.tags || []).map((tag) => (
                  <span key={tag} className="knowledge-tag">
                    <Tag size={12} />
                    {tag}
                  </span>
                ))}
              </div>
              <div className="knowledge-meta">
                {item.source && (
                  <>
                    <span className="knowledge-source">{item.source}</span>
                    <span className="knowledge-dot">·</span>
                  </>
                )}
                <span className="knowledge-date">{item.updatedAt}</span>
              </div>
            </div>
          </div>
        ))}
      </div>

      {filteredKnowledge.length === 0 && (
        <div className="knowledge-empty">
          <p>未找到匹配的知识条目</p>
        </div>
      )}

      {modal && (
        <KnowledgeModal
          initial={modal === 'create' ? null : modal}
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
  initial,
  onClose,
  onSave,
}: {
  initial: { id: string; question: string; answer: string; tags: string; source: string } | null
  onClose: () => void
  onSave: (
    payload: { question: string; answer: string; tags: string[]; source: string | null },
    editingId?: string
  ) => void
}) {
  const [form, setForm] = useState<KnowledgeForm>({
    question: initial?.question || '',
    answer: initial?.answer || '',
    tags: initial?.tags || '',
    source: initial?.source || '',
  })
  const [submitting, setSubmitting] = useState(false)

  const handleChange = (field: keyof KnowledgeForm) => (
    e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>
  ) => {
    setForm({ ...form, [field]: e.target.value })
  }

  const handleSubmit = async () => {
    if (!form.question.trim()) {
      alert('请填写问题')
      return
    }
    if (!form.answer.trim()) {
      alert('请填写答案')
      return
    }
    const payload = {
      question: form.question.trim(),
      answer: form.answer.trim(),
      tags: form.tags
        .split(',')
        .map((t) => t.trim())
        .filter(Boolean),
      source: form.source.trim() || null,
    }
    setSubmitting(true)
    try {
      await onSave(payload, initial?.id)
    } catch (error) {
      console.error('保存失败:', error)
      alert('保存失败，请重试')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <h3 className="modal-title">{initial?.id ? '编辑知识' : '添加知识'}</h3>
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
          <Button
            variant="primary"
            size="sm"
            onClick={handleSubmit}
            disabled={submitting}
          >
            {submitting ? '保存中...' : '保存'}
          </Button>
        </div>
      </div>
    </div>
  )
}

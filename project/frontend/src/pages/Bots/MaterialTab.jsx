import { useState, useEffect } from 'react'
import { Upload, Search, Trash2, Download, Eye } from 'lucide-react'
import Button from '../../components/common/Button'
import { materialsApi } from '../../utils/api'
import './MaterialTab.css'

function formatSize(bytes) {
  if (typeof bytes !== 'number' || bytes <= 0) return '—'
  const units = ['B', 'KB', 'MB', 'GB']
  let value = bytes
  let unitIndex = 0
  while (value >= 1024 && unitIndex < units.length - 1) {
    value /= 1024
    unitIndex += 1
  }
  return `${value.toFixed(value >= 10 || unitIndex === 0 ? 0 : 1)} ${units[unitIndex]}`
}

function getTypeName(type) {
  if (type === 'image') return '图片'
  if (type === 'video') return '视频'
  if (type === 'document') return '文档'
  return '其他'
}

function getTypeIcon(type) {
  switch (type) {
    case 'image':
      return '🖼️'
    case 'video':
      return '🎥'
    case 'document':
      return '📄'
    default:
      return '📎'
  }
}

const MATERIAL_TYPES = [
  { value: 'image', label: '图片' },
  { value: 'video', label: '视频' },
  { value: 'document', label: '文档' },
]

export default function MaterialTab({ bot }) {
  const [materials, setMaterials] = useState([])
  const [searchTerm, setSearchTerm] = useState('')
  const [selectedIds, setSelectedIds] = useState([])
  const [loading, setLoading] = useState(true)
  const [showUpload, setShowUpload] = useState(false)

  useEffect(() => {
    loadMaterials()
  }, [bot.id])

  const loadMaterials = async () => {
    try {
      const data = await materialsApi.listByBot(bot.id)
      setMaterials(data)
    } catch (error) {
      console.error('加载素材库失败:', error)
    } finally {
      setLoading(false)
    }
  }

  const filteredMaterials = materials.filter(
    (item) =>
      item.name.includes(searchTerm) || item.category.includes(searchTerm)
  )

  const handleSelectAll = (checked) => {
    setSelectedIds(checked ? filteredMaterials.map((m) => m.id) : [])
  }

  const handleSelect = (id, checked) => {
    setSelectedIds(
      checked ? [...selectedIds, id] : selectedIds.filter((sid) => sid !== id)
    )
  }

  const handleDelete = async (id) => {
    if (!confirm('确定删除这个素材吗？')) return
    try {
      await materialsApi.delete(id)
      setMaterials(materials.filter((m) => m.id !== id))
      setSelectedIds(selectedIds.filter((sid) => sid !== id))
    } catch (error) {
      console.error('删除失败:', error)
      alert('删除失败，请重试')
    }
  }

  const handleDeleteSelected = async () => {
    if (
      selectedIds.length === 0 ||
      !confirm(`确定删除选中的 ${selectedIds.length} 个素材吗？`)
    ) {
      return
    }
    try {
      await Promise.all(selectedIds.map((id) => materialsApi.delete(id)))
      setMaterials(materials.filter((m) => !selectedIds.includes(m.id)))
      setSelectedIds([])
    } catch (error) {
      console.error('批量删除失败:', error)
      alert('部分素材删除失败，请重试')
    }
  }

  if (loading) {
    return <div className="material-loading">加载中...</div>
  }

  return (
    <div className="material-tab">
      <div className="material-header">
        <div className="material-search">
          <Search size={16} className="search-icon" />
          <input
            type="text"
            placeholder="搜索素材..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
        </div>
        <div className="material-actions">
          {selectedIds.length > 0 && (
            <Button
              variant="danger"
              size="sm"
              icon={<Trash2 size={16} />}
              onClick={handleDeleteSelected}
            >
              删除 ({selectedIds.length})
            </Button>
          )}
          <Button
            variant="primary"
            size="sm"
            icon={<Upload size={16} />}
            onClick={() => setShowUpload(true)}
          >
            上传素材
          </Button>
        </div>
      </div>

      <div className="material-stats">
        <div className="stat-badge">
          <span className="stat-badge-label">总素材</span>
          <span className="stat-badge-value">{materials.length}</span>
        </div>
        <div className="stat-badge">
          <span className="stat-badge-label">总大小</span>
          <span className="stat-badge-value">
            {formatSize(materials.reduce((sum, m) => sum + (m.size || 0), 0))}
          </span>
        </div>
        <div className="stat-badge">
          <span className="stat-badge-label">总引用</span>
          <span className="stat-badge-value">—</span>
        </div>
      </div>

      <div className="material-table-wrapper">
        <table className="material-table">
          <thead>
            <tr>
              <th style={{ width: '40px' }}>
                <input
                  type="checkbox"
                  checked={
                    selectedIds.length === filteredMaterials.length &&
                    filteredMaterials.length > 0
                  }
                  onChange={(e) => handleSelectAll(e.target.checked)}
                />
              </th>
              <th>素材</th>
              <th>类型</th>
              <th>分类</th>
              <th>大小</th>
              <th>引用次数</th>
              <th>上传时间</th>
              <th style={{ width: '120px' }}>操作</th>
            </tr>
          </thead>
          <tbody>
            {filteredMaterials.map((item) => (
              <tr key={item.id}>
                <td>
                  <input
                    type="checkbox"
                    checked={selectedIds.includes(item.id)}
                    onChange={(e) => handleSelect(item.id, e.target.checked)}
                  />
                </td>
                <td>
                  <div className="material-name-cell">
                    <span className="material-type-icon">
                      {getTypeIcon(item.type)}
                    </span>
                    {item.url && (
                      <img
                        src={item.url}
                        alt={item.name}
                        className="material-thumb"
                      />
                    )}
                    <span className="material-name">{item.name}</span>
                  </div>
                </td>
                <td>
                  <span className="material-type-badge">
                    {getTypeName(item.type)}
                  </span>
                </td>
                <td>{item.category || '未分类'}</td>
                <td className="text-muted">{formatSize(item.size)}</td>
                <td className="text-muted">—</td>
                <td className="text-muted">—</td>
                <td>
                  <div className="table-actions">
                    <button className="table-action-btn" title="预览">
                      <Eye size={14} />
                    </button>
                    <button className="table-action-btn" title="下载">
                      <Download size={14} />
                    </button>
                    <button
                      className="table-action-btn table-action-btn-danger"
                      title="删除"
                      onClick={() => handleDelete(item.id)}
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {filteredMaterials.length === 0 && (
        <div className="material-empty">
          <p>未找到匹配的素材</p>
        </div>
      )}

      {showUpload && (
        <UploadModal
          botId={bot.id}
          onClose={() => setShowUpload(false)}
          onCreated={(created) => {
            setMaterials([created, ...materials])
            setShowUpload(false)
          }}
        />
      )}
    </div>
  )
}

function UploadModal({ botId, onClose, onCreated }) {
  const [form, setForm] = useState({
    name: '',
    type: 'image',
    size: '',
    category: '未分类',
    url: '',
  })
  const [submitting, setSubmitting] = useState(false)

  const handleChange = (field) => (e) => {
    setForm({ ...form, [field]: e.target.value })
  }

  const handleSubmit = async () => {
    if (!form.name.trim()) {
      alert('请填写素材名称')
      return
    }
    const sizeNum = Number(form.size)
    if (!Number.isFinite(sizeNum) || sizeNum < 0) {
      alert('请填写有效的文件大小（字节数）')
      return
    }
    setSubmitting(true)
    try {
      const payload = {
        name: form.name.trim(),
        type: form.type,
        size: sizeNum,
        category: form.category.trim() || '未分类',
        url: form.url.trim() || null,
      }
      const created = await materialsApi.create(botId, payload)
      onCreated(created)
    } catch (error) {
      console.error('上传素材失败:', error)
      alert('上传失败，请重试')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <h3 className="modal-title">上传素材</h3>
        <div className="modal-field">
          <label>素材名称 *</label>
          <input
            type="text"
            value={form.name}
            onChange={handleChange('name')}
            placeholder="例如：产品宣传图.png"
          />
        </div>
        <div className="modal-field">
          <label>类型</label>
          <select value={form.type} onChange={handleChange('type')}>
            {MATERIAL_TYPES.map((t) => (
              <option key={t.value} value={t.value}>
                {t.label}
              </option>
            ))}
          </select>
        </div>
        <div className="modal-field">
          <label>文件大小（字节）*</label>
          <input
            type="number"
            min="0"
            value={form.size}
            onChange={handleChange('size')}
            placeholder="例如：2400000 表示约 2.3 MB"
          />
        </div>
        <div className="modal-field">
          <label>分类</label>
          <input
            type="text"
            value={form.category}
            onChange={handleChange('category')}
            placeholder="例如：产品图片"
          />
        </div>
        <div className="modal-field">
          <label>URL（可选）</label>
          <input
            type="text"
            value={form.url}
            onChange={handleChange('url')}
            placeholder="素材访问地址，可留空"
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
            {submitting ? '上传中...' : '确认上传'}
          </Button>
        </div>
      </div>
    </div>
  )
}

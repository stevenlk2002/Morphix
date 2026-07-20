import { useState, useEffect } from 'react'
import { Upload, Trash2, Download, Eye, ChevronDown } from 'lucide-react'
import { toast } from '../../utils/toast'
import { materialsApi, MaterialItemDTO, Paged } from '../../api/client'
import './MaterialTab.css'

interface BotRef {
  id: string
  name?: string
}

interface MaterialItem {
  id: string
  name: string
  type: string
  size: number
  category: string
  url: string | null
  source: string
  usageCount: number
  uploadedAt: string
  updatedAt: string
}

/** 来源筛选选项（与种子 source 对齐）。 */
const SOURCE_OPTIONS = ['请选择', '知识中心', '上传']

const PAGE_SIZES = [10, 20, 50, 100]

/** 将字节数格式化为可读大小。 */
function formatSize(bytes: number): string {
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

function getTypeName(type: string): string {
  if (type === 'image') return '图片'
  if (type === 'video') return '视频'
  if (type === 'document') return '文档'
  if (type === 'audio') return '音频'
  return '其他'
}

function getTypeIcon(type: string): string {
  switch (type) {
    case 'image':
      return '🖼️'
    case 'video':
      return '🎥'
    case 'document':
      return '📄'
    case 'audio':
      return '🎵'
    default:
      return '📎'
  }
}

/** 后端 DTO → 前端结构。 */
function toItem(dto: MaterialItemDTO): MaterialItem {
  return {
    id: dto.id,
    name: dto.name,
    type: dto.type,
    size: dto.size,
    category: dto.category ?? '未分类',
    url: dto.url ?? null,
    source: dto.source ?? '上传',
    usageCount: dto.usageCount ?? 0,
    uploadedAt: dto.uploadedAt,
    updatedAt: dto.updatedAt,
  }
}

/**
 * 素材内容 Tab（对齐 prototype robot-train 的 material-pane）。
 * 顶部筛选（文件名 / 上传时间 / 来源）+ 操作（上传 / 批量删除）+ 列表 + 分页。
 * 列表走后端分页接口（materialsApi.listByBot → {items, total, page, pageSize, hasMore}）。
 */
export default function MaterialTab({ bot }: { bot: BotRef }) {
  const [items, setItems] = useState<MaterialItem[]>([])
  const [loading, setLoading] = useState(false)
  const [selectedIds, setSelectedIds] = useState<string[]>([])

  const [fileName, setFileName] = useState('')
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')
  const [source, setSource] = useState('请选择')
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)

  const [sourceOpen, setSourceOpen] = useState(false)
  const [pageSizeOpen, setPageSizeOpen] = useState(false)

  const [total, setTotal] = useState(0)

  /** 拉取素材（分页 + 筛选）。nextPageSize 用于切换每页条数时避免闭包取到旧值。 */
  const loadMaterials = async (nextPage?: number, nextPageSize?: number) => {
    const usePage = nextPage ?? page
    const useSize = nextPageSize ?? pageSize
    try {
      setLoading(true)
      const res = (await materialsApi.listByBot(bot.id, {
        name: fileName || undefined,
        startDate: startDate || undefined,
        endDate: endDate || undefined,
        source: source !== '请选择' ? source : undefined,
        page: usePage,
        pageSize: useSize,
      })) as Paged<MaterialItemDTO>
      setItems(res.items.map(toItem))
      setTotal(res.total)
      setSelectedIds([])
    } catch (e) {
      toast(`加载素材失败：${(e as Error).message}`)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadMaterials(1)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [bot.id])

  /** 查询（筛选）。 */
  const handleQuery = () => {
    setPage(1)
    loadMaterials(1)
  }

  /** 重置筛选。 */
  const handleReset = () => {
    setFileName('')
    setStartDate('')
    setEndDate('')
    setSource('请选择')
    setPage(1)
    loadMaterials(1)
  }

  const totalPages = Math.max(1, Math.ceil(total / pageSize))
  const rangeStart = total === 0 ? 0 : (page - 1) * pageSize + 1
  const rangeEnd = Math.min(page * pageSize, total)

  const goPrev = () => {
    if (page > 1) {
      const p = page - 1
      setPage(p)
      loadMaterials(p)
    }
  }
  const goNext = () => {
    if (page < totalPages) {
      const p = page + 1
      setPage(p)
      loadMaterials(p)
    }
  }

  const changePageSize = (size: number) => {
    setPageSizeOpen(false)
    setPageSize(size)
    setPage(1)
    loadMaterials(1, size)
  }

  const allChecked = items.length > 0 && selectedIds.length === items.length
  const toggleSelectAll = () => {
    setSelectedIds(allChecked ? [] : items.map((i) => i.id))
  }
  const toggleSelect = (id: string) => {
    setSelectedIds((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]))
  }

  const handleDelete = (item: MaterialItem) => {
    if (!window.confirm(`确定删除素材「${item.name}」吗？`)) return
    materialsApi
      .delete(item.id)
      .then(() => {
        toast('已删除素材')
        loadMaterials(page)
      })
      .catch((e) => toast(`删除失败：${(e as Error).message}`))
  }

  const handleBatchDelete = () => {
    if (selectedIds.length === 0) return
    if (!window.confirm(`确定删除选中的 ${selectedIds.length} 个素材吗？`)) return
    materialsApi
      .batchDelete(bot.id, selectedIds)
      .then((res) => {
        toast(`已批量删除 ${res.deleted} 个素材`)
        loadMaterials(page)
      })
      .catch((e) => toast(`批量删除失败：${(e as Error).message}`))
  }

  return (
    <div className="material-pane">
      {/* 筛选区 */}
      <div className="material-filter">
        <div className="material-filter-item">
          <label>文件名称：</label>
          <input
            type="text"
            placeholder="请输入"
            value={fileName}
            style={{ width: 180 }}
            onChange={(e) => setFileName(e.target.value)}
          />
        </div>
        <div className="material-filter-item">
          <label>上传时间：</label>
          <div className="date-range">
            <input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} />
            <span>至</span>
            <input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} />
          </div>
        </div>
        <div className="material-filter-item">
          <label>来源：</label>
          <div className={`material-select ${sourceOpen ? 'open' : ''}`}>
            <div
              className="material-select-trigger"
              onClick={() => setSourceOpen((v) => !v)}
            >
              {source}
              <ChevronDown size={14} />
            </div>
            <div className="material-select-dropdown">
              {SOURCE_OPTIONS.map((opt) => (
                <div
                  key={opt}
                  className={`material-select-option ${source === opt ? 'active' : ''}`}
                  onClick={() => {
                    setSource(opt)
                    setSourceOpen(false)
                  }}
                >
                  {opt}
                </div>
              ))}
            </div>
          </div>
        </div>
        <div className="material-filter-actions">
          <button className="btn-material-reset" onClick={handleReset}>
            重置
          </button>
          <button className="btn-material-query" onClick={handleQuery}>
            查询
          </button>
        </div>
      </div>

      {/* 操作区 */}
      <div className="material-actions">
        <button
          className="btn-material-upload"
          onClick={() => toast('上传素材（演示环境暂未开放）')}
        >
          <Upload size={14} /> 上传
        </button>
        {selectedIds.length > 0 && (
          <button className="btn-material-batch-delete" onClick={handleBatchDelete}>
            <Trash2 size={14} /> 批量删除 ({selectedIds.length})
          </button>
        )}
      </div>

      {/* 列表 */}
      <div className="material-list">
        {loading ? (
          <div className="material-loading">加载中…</div>
        ) : items.length === 0 ? (
          <div className="material-empty">
            <svg viewBox="0 0 120 120" fill="none" stroke="currentColor" strokeWidth={1.5}>
              <rect x="25" y="18" width="46" height="56" rx="4" fill="currentColor" fillOpacity="0.06" transform="rotate(8 48 46)" />
              <rect x="42" y="36" width="46" height="56" rx="4" fill="currentColor" fillOpacity="0.08" transform="rotate(-6 65 64)" />
              <path d="M35 38 L45 48 L55 34 L69 52 L81 40" strokeLinecap="round" strokeLinejoin="round" transform="rotate(8 48 46)" />
              <circle cx="62" cy="34" r="4" transform="rotate(8 48 46)" />
              <path d="M55 70 L75 90" strokeLinecap="round" />
              <path d="M75 70 L55 90" strokeLinecap="round" />
            </svg>
            <div className="material-empty-text">暂无素材</div>
          </div>
        ) : (
          <table className="material-list-table">
            <thead>
              <tr>
                <th style={{ width: 40 }}>
                  <input
                    type="checkbox"
                    checked={allChecked}
                    onChange={toggleSelectAll}
                  />
                </th>
                <th>素材名称</th>
                <th>类型</th>
                <th>来源</th>
                <th>大小</th>
                <th>引用次数</th>
                <th>上传时间</th>
                <th style={{ width: 120 }}>操作</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr key={item.id}>
                  <td>
                    <input
                      type="checkbox"
                      checked={selectedIds.includes(item.id)}
                      onChange={() => toggleSelect(item.id)}
                    />
                  </td>
                  <td>
                    <div className="material-name-cell">
                      <span className="material-type-icon">{getTypeIcon(item.type)}</span>
                      {item.url && <img src={item.url} alt={item.name} className="material-thumb" />}
                      <span className="material-name">{item.name}</span>
                    </div>
                  </td>
                  <td>
                    <span className="material-type-badge">{getTypeName(item.type)}</span>
                  </td>
                  <td>{item.source}</td>
                  <td className="text-muted">{formatSize(item.size)}</td>
                  <td className="text-muted">{item.usageCount}</td>
                  <td className="text-muted">{item.uploadedAt}</td>
                  <td>
                    <div className="table-actions">
                      <button
                        type="button"
                        className="table-action-btn"
                        title="预览"
                        onClick={() => toast('演示环境：预览未接入')}
                      >
                        <Eye size={14} />
                      </button>
                      <button
                        type="button"
                        className="table-action-btn"
                        title="下载"
                        onClick={() => toast('演示环境：下载未接入')}
                      >
                        <Download size={14} />
                      </button>
                      <button
                        type="button"
                        className="table-action-btn table-action-btn-danger"
                        title="删除"
                        onClick={() => handleDelete(item)}
                      >
                        <Trash2 size={14} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* 分页 */}
      <div className="material-pagination">
        <div className="material-pagination-info">
          第 {rangeStart}-{rangeEnd} 条/总共 {total} 条
        </div>
        <div className="material-pagination-pages">
          <button disabled={page <= 1} onClick={goPrev}>
            &lt;
          </button>
          <button className="active">{page}</button>
          <button disabled={page >= totalPages} onClick={goNext}>
            &gt;
          </button>
        </div>
        <div className={`material-page-size ${pageSizeOpen ? 'open' : ''}`}>
          <div
            className="material-page-size-trigger"
            onClick={() => setPageSizeOpen((v) => !v)}
          >
            {pageSize}条/页
            <ChevronDown size={14} />
          </div>
          <div className="material-page-size-dropdown">
            {PAGE_SIZES.map((size) => (
              <div
                key={size}
                className={`material-page-size-option ${pageSize === size ? 'active' : ''}`}
                onClick={() => changePageSize(size)}
              >
                {size}条/页
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}

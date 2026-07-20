import { useState, useEffect, useCallback, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { Plus, Search, MoreHorizontal } from 'lucide-react'
import Button from '../../components/common/Button'
import type { OperationTask } from '../../types/operations'
import { TASK_TYPE_OPTIONS } from '../../types/operations'
import { operationsTasksApi } from '../../api/operations'
import './OperationTasks.css'

/** 任务卡片组件（内联，避免额外文件）。 */
function TaskCard({
  task,
  onToggle,
  onEdit,
  onRecords,
  onDelete,
}: {
  task: OperationTask
  onToggle: (id: string) => void
  onEdit: (task: OperationTask) => void
  onRecords: () => void
  onDelete: (id: string) => void
}) {
  const [menuOpen, setMenuOpen] = useState(false)
  const menuRef = useRef<HTMLDivElement>(null)

  // 点击外部关闭菜单
  useEffect(() => {
    if (!menuOpen) return
    const handler = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [menuOpen])

  const typeBadgeClass =
    task.task_type === '群发任务'
      ? 'proto-badge proto-badge-info'
      : task.task_type === '朋友圈任务'
        ? 'proto-badge proto-badge-success'
        : 'proto-badge proto-badge-warning'

  return (
    <div className="task-card">
      <div className="task-card-top">
        <span className={typeBadgeClass}>{task.task_type}</span>
        <label className="switch">
          <input
            type="checkbox"
            checked={task.enabled}
            onChange={() => onToggle(task.id)}
            aria-label={`${task.name} 启用开关`}
          />
          <span className="slider" />
        </label>
      </div>
      <div className="task-bot-name">{task.name}</div>
      <div className="task-meta">
        渠道类型：{task.channel_type || '企业微信'} · 运行频率：{task.run_frequency || '一次'}
      </div>
      <div className="task-meta" style={{ marginTop: 4 }}>
        下次运行时间：{task.next_run_time || '—'}
      </div>
      <div className="task-card-footer">
        <Button variant="ghost" size="sm" onClick={() => onEdit(task)}>
          编辑
        </Button>
        <Button variant="ghost" size="sm" onClick={onRecords}>
          运营记录
        </Button>
        <div className="task-card-more-wrapper" ref={menuRef}>
          <button
            className="task-card-more-btn"
            onClick={(e) => {
              e.stopPropagation()
              setMenuOpen((v) => !v)
            }}
            aria-label="更多操作"
          >
            <MoreHorizontal size={16} />
          </button>
          {menuOpen && (
            <div className="task-card-menu">
              <button
                className="task-card-menu-item task-card-menu-item-danger"
                onClick={() => {
                  setMenuOpen(false)
                  onDelete(task.id)
                }}
              >
                删除
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

/** 生成 toast 提示。 */
let toastTimer: ReturnType<typeof setTimeout> | null = null

function showToast(message: string) {
  const el = document.getElementById('ops-toast')
  if (el) {
    el.textContent = message
    el.classList.add('ops-toast-show')
    if (toastTimer) clearTimeout(toastTimer)
    toastTimer = setTimeout(() => {
      el.classList.remove('ops-toast-show')
    }, 2500)
  }
}

export default function OperationTasksPage() {
  const navigate = useNavigate()

  // 数据
  const [tasks, setTasks] = useState<OperationTask[]>([])
  const [loading, setLoading] = useState(true)

  // 筛选
  const [search, setSearch] = useState('')
  const [typeFilter, setTypeFilter] = useState('全部')
  const [enabledFilter, setEnabledFilter] = useState('全部')
  const [runFilter, setRunFilter] = useState('全部')
  const [sortBy, setSortBy] = useState('created_at_desc')

  /** 加载任务列表。 */
  const loadTasks = useCallback(async () => {
    setLoading(true)
    try {
      const params: Record<string, string> = {}
      if (search.trim()) params.search = search.trim()
      if (typeFilter !== '全部') params.type = typeFilter
      if (enabledFilter === '已启用') params.enabled = 'enabled'
      else if (enabledFilter === '已停用') params.enabled = 'disabled'
      if (runFilter !== '全部') params.run_status = runFilter
      // 排序
      if (sortBy === 'created_at_desc') {
        params.sortBy = 'created_at'
        params.sortOrder = 'DESC'
      } else if (sortBy === 'created_at_asc') {
        params.sortBy = 'created_at'
        params.sortOrder = 'ASC'
      } else if (sortBy === 'name_asc') {
        params.sortBy = 'name'
        params.sortOrder = 'ASC'
      } else if (sortBy === 'name_desc') {
        params.sortBy = 'name'
        params.sortOrder = 'DESC'
      } else if (sortBy === 'next_run_asc') {
        params.sortBy = 'next_run_time'
        params.sortOrder = 'ASC'
      } else if (sortBy === 'next_run_desc') {
        params.sortBy = 'next_run_time'
        params.sortOrder = 'DESC'
      }

      const data = await operationsTasksApi.list(params)
      setTasks(Array.isArray(data) ? data : [])
    } catch (err) {
      console.error('加载运营任务失败:', err)
      setTasks([])
    } finally {
      setLoading(false)
    }
  }, [search, typeFilter, enabledFilter, runFilter, sortBy])

  useEffect(() => {
    loadTasks()
  }, [loadTasks])

  /** Switch 切换启用状态。 */
  const handleToggle = async (id: string) => {
    // 乐观更新
    setTasks((prev) =>
      prev.map((t) => (t.id === id ? { ...t, enabled: !t.enabled } : t))
    )
    try {
      const updated = await operationsTasksApi.toggleEnabled(id)
      // 使用服务端返回的数据回填
      setTasks((prev) => prev.map((t) => (t.id === id ? updated : t)))
    } catch (err) {
      console.error('切换启用失败:', err)
      showToast('切换失败，请重试')
      // 回退
      setTasks((prev) =>
        prev.map((t) => (t.id === id ? { ...t, enabled: !t.enabled } : t))
      )
    }
  }

  /** 编辑 -> 跳转编辑页。 */
  const handleEdit = (task: OperationTask) => {
    navigate(`/operations/tasks/${task.id}/edit`)
  }

  /** 运营记录 toast 占位。 */
  const handleRecords = () => {
    showToast('查看运营记录')
  }

  /** 删除任务。 */
  const handleDelete = async (id: string) => {
    if (!window.confirm('确认删除该运营任务？此操作不可撤销。')) return
    try {
      await operationsTasksApi.delete(id)
      showToast('任务已删除')
      loadTasks()
    } catch (err) {
      console.error('删除任务失败:', err)
      showToast('删除失败，请重试')
    }
  }

  return (
    <div className="proto-page">
      {/* Banner */}
      <div className="banner">
        <div>
          <div className="banner-title">运营任务</div>
          <div className="banner-desc">
            群发任务 · 机器人定时任务 · 特定节点定时任务
            <br />
            特定节点机器人定时任务
          </div>
        </div>
        <svg width="200" height="120" viewBox="0 0 200 120" aria-hidden="true">
          <rect x="120" y="20" width="60" height="80" rx="6" fill="#fff" opacity="0.5" />
          <rect x="100" y="40" width="50" height="60" rx="6" fill="#fff" opacity="0.4" />
          <circle cx="50" cy="60" r="25" fill="#3b82f6" opacity="0.3" />
          <path d="M35 60l10 10 20-20" stroke="#fff" strokeWidth="3" fill="none" strokeLinecap="round" />
        </svg>
      </div>

      {/* 筛选栏 */}
      <div className="filter-bar">
        <div className="task-search">
          <Search size={16} />
          <input
            className="input"
            placeholder="搜索任务"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && loadTasks()}
          />
        </div>
        <select
          className="select"
          value={typeFilter}
          onChange={(e) => setTypeFilter(e.target.value)}
        >
          <option value="全部">全部类型</option>
          {TASK_TYPE_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
        <select
          className="select"
          value={enabledFilter}
          onChange={(e) => setEnabledFilter(e.target.value)}
        >
          <option value="全部">启用状态</option>
          <option value="已启用">已启用</option>
          <option value="已停用">已停用</option>
        </select>
        <select
          className="select"
          value={runFilter}
          onChange={(e) => setRunFilter(e.target.value)}
        >
          <option value="全部">运行状态</option>
          <option value="未运行">未运行</option>
          <option value="运行中">运行中</option>
          <option value="已完成">已完成</option>
          <option value="失败">异常结束</option>
          <option value="已暂停">人工停止</option>
        </select>
        <select
          className="select"
          value={sortBy}
          onChange={(e) => setSortBy(e.target.value)}
        >
          <option value="created_at_desc">创建时间 ↓</option>
          <option value="created_at_asc">创建时间 ↑</option>
          <option value="name_asc">任务名称 A-Z</option>
          <option value="name_desc">任务名称 Z-A</option>
          <option value="next_run_asc">下次运行 ↑</option>
          <option value="next_run_desc">下次运行 ↓</option>
        </select>
      </div>

      {/* 卡片网格 */}
      <div className="task-grid">
        {/* 创建入口（虚线卡片） */}
        <div
          className="task-card task-card-dashed"
          onClick={() => navigate('/operations/tasks/create')}
          role="button"
          tabIndex={0}
        >
          <span className="task-dashed-icon">
            <Plus size={22} />
          </span>
          <span>创建运营任务</span>
        </div>

        {/* 加载态 */}
        {loading && (
          <div className="task-empty">
            <div className="ops-loading-spinner" />
            <span>加载中...</span>
          </div>
        )}

        {/* 任务卡片 */}
        {!loading &&
          tasks.map((task) => (
            <TaskCard
              key={task.id}
              task={task}
              onToggle={handleToggle}
              onEdit={handleEdit}
              onRecords={handleRecords}
              onDelete={handleDelete}
            />
          ))}

        {/* 空态 */}
        {!loading && tasks.length === 0 && (
          <div className="task-empty">没有符合条件的运营任务</div>
        )}
      </div>

      {/* Toast */}
      <div id="ops-toast" className="ops-toast" />
    </div>
  )
}

import { useEffect, useRef, useState } from 'react'
import { NavLink, useLocation } from 'react-router-dom'
import { Bell, ChevronDown, ChevronLeft, ChevronRight } from 'lucide-react'
import { navItems, flattenNavItems, type NavItem } from '../utils/routes'
import { useUser, type AppUser } from '../context/UserContext'
import './Sidebar.css'

interface SidebarProps {
  collapsed: boolean
  onToggle: () => void
}

interface NotifyItem {
  title: string
  desc: string
}

/** 消息通知（与 prototype/index.html 保持一致）。 */
const NOTIFICATIONS: NotifyItem[] = [
  { title: '机器人训练完成', desc: '野风秋大健康机器人已完成训练' },
  { title: '新的客户消息', desc: '通天草-林瞰 发来一条消息' },
]

export default function Sidebar({ collapsed, onToggle }: SidebarProps) {
  const location = useLocation()
  const { currentUser, users, switchUser } = useUser()

  const [userOpen, setUserOpen] = useState(false)
  const [notifyOpen, setNotifyOpen] = useState(false)
  const [toastMsg, setToastMsg] = useState<string | null>(null)
  const [unread, setUnread] = useState(2)

  const brandRef = useRef<HTMLDivElement>(null)
  const toastTimer = useRef<number | null>(null)

  // 计算需要精确匹配（end）的路径：是其它导航路径的前缀时，避免父子同时高亮。
  // 例如 /bots 是 /bots/logs 的前缀，故 /bots 在子路由下不应高亮。
  const flatPaths = flattenNavItems().map((item) => item.path)
  const exactOnlyPaths = new Set(
    flatPaths.filter(
      (p) => p === '/' || flatPaths.some((q) => q !== p && q.startsWith(p + '/'))
    )
  )

  // 默认展开包含当前路由的父级分组，保证进入子页面时父菜单处于展开态。
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(() => {
    const initial = new Set<string>()
    for (const item of navItems) {
      if (
        item.children &&
        item.children.some((child) => location.pathname.startsWith(child.path))
      ) {
        initial.add(item.id)
      }
    }
    return initial
  })

  const toggleGroup = (id: string) => {
    setExpandedGroups((prev) => {
      const next = new Set(prev)
      if (next.has(id)) {
        next.delete(id)
      } else {
        next.add(id)
      }
      return next
    })
  }

  // 点击外部关闭所有下拉
  useEffect(() => {
    const onDocClick = (e: MouseEvent) => {
      if (brandRef.current && !brandRef.current.contains(e.target as Node)) {
        setUserOpen(false)
        setNotifyOpen(false)
      }
    }
    document.addEventListener('mousedown', onDocClick)
    return () => document.removeEventListener('mousedown', onDocClick)
  }, [])

  // 卸载时清理 toast 计时器
  useEffect(() => {
    return () => {
      if (toastTimer.current) window.clearTimeout(toastTimer.current)
    }
  }, [])

  const showToast = (msg: string) => {
    setToastMsg(msg)
    if (toastTimer.current) window.clearTimeout(toastTimer.current)
    toastTimer.current = window.setTimeout(() => setToastMsg(null), 1800)
  }

  const handleSelectUser = (u: AppUser) => {
    switchUser(u)
    showToast('已切换至：' + u.name)
    setUserOpen(false)
    setNotifyOpen(false)
  }

  const closeDropdowns = () => {
    setUserOpen(false)
    setNotifyOpen(false)
  }

  return (
    <>
      <aside className={`sidebar ${collapsed ? 'collapsed' : ''}`}>
        <button
          className="sidebar-toggle"
          type="button"
          onClick={onToggle}
          aria-label={collapsed ? '展开侧边栏' : '收起侧边栏'}
        >
          {collapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
        </button>

        <div className="brand" ref={brandRef}>
          <div
            className="brand-user"
            onClick={(e) => {
              e.stopPropagation()
              setUserOpen((o) => !o)
              setNotifyOpen(false)
            }}
          >
            <div className="brand-avatar">{currentUser.avatar}</div>
            {!collapsed && (
              <div className="brand-info">
                <div className="brand-name">{currentUser.name}</div>
                <span className="brand-tag">{currentUser.tag}</span>
              </div>
            )}
            {!collapsed && <ChevronDown size={14} className="brand-chevron" />}
          </div>

          <button
            className="btn-icon"
            type="button"
            onClick={(e) => {
              e.stopPropagation()
              setNotifyOpen((o) => {
                const next = !o
                if (next) setUnread(0)
                return next
              })
              setUserOpen(false)
            }}
            title="消息通知"
            aria-label="消息通知"
          >
            <Bell size={18} />
            {unread > 0 && <span className="notify-dot" />}
          </button>

          <div
            className={`user-dropdown ${userOpen ? 'open' : ''}`}
            onClick={(e) => e.stopPropagation()}
          >
            {users.map((u) => (
              <div
                key={u.name}
                className={`user-option ${
                  u.name === currentUser.name ? 'active' : ''
                }`}
                onClick={() => handleSelectUser(u)}
              >
                <div className="brand-avatar">{u.avatar}</div>
                <div className="brand-info">
                  <div className="brand-name">{u.name}</div>
                  <span className="brand-tag">{u.tag}</span>
                </div>
              </div>
            ))}
          </div>

          <div
            className={`notify-dropdown ${notifyOpen ? 'open' : ''}`}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="notify-header">消息通知</div>
            {NOTIFICATIONS.map((n) => (
              <div
                key={n.title}
                className="notify-item"
                onClick={closeDropdowns}
              >
                <div className="notify-title">{n.title}</div>
                <div className="notify-desc">{n.desc}</div>
              </div>
            ))}
            <div
              className="notify-item"
              onClick={() => {
                showToast('查看全部通知')
                closeDropdowns()
              }}
            >
              查看全部
            </div>
          </div>
        </div>

        <nav className="nav">
          {navItems.map((item) => {
            if (item.children && item.children.length > 0) {
              const Icon = item.icon
              const isExpanded = expandedGroups.has(item.id)
              return (
                <div className="nav-group" key={item.id}>
                  <div
                    className={`nav-item ${isExpanded ? 'expanded' : ''}`}
                    onClick={() => toggleGroup(item.id)}
                    title={collapsed ? item.label : ''}
                  >
                    {Icon && <Icon size={18} className="nav-icon" />}
                    {!collapsed && <span className="nav-label">{item.label}</span>}
                    {!collapsed && <ChevronDown size={16} className="chevron" />}
                  </div>
                  <div className={`nav-sub ${isExpanded ? 'open' : ''}`}>
                    {item.children.map((child: NavItem) => (
                      <NavLink
                        key={child.id}
                        to={child.path}
                        end={exactOnlyPaths.has(child.path)}
                        className={({ isActive }) =>
                          `nav-item ${isActive ? 'active' : ''}`
                        }
                        title={collapsed ? child.label : ''}
                      >
                        {!collapsed && (
                          <span className="nav-label">{child.label}</span>
                        )}
                      </NavLink>
                    ))}
                  </div>
                </div>
              )
            }

            const Icon = item.icon
            return (
              <NavLink
                key={item.id}
                to={item.path}
                end={exactOnlyPaths.has(item.path)}
                className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
                title={collapsed ? item.label : ''}
              >
                {Icon && <Icon size={18} className="nav-icon" />}
                {!collapsed && <span className="nav-label">{item.label}</span>}
              </NavLink>
            )
          })}
        </nav>
      </aside>

      {toastMsg && <div className="sidebar-toast">{toastMsg}</div>}
    </>
  )
}

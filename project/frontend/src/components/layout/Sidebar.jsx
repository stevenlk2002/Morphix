import { NavLink } from 'react-router-dom'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import { navItems } from '../../utils/routes'
import './Sidebar.css'

export default function Sidebar({ collapsed, onToggle }) {
  return (
    <aside className={`sidebar ${collapsed ? 'collapsed' : ''}`}>
      <button className="sidebar-toggle" onClick={onToggle}>
        {collapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
      </button>

      <div className="brand">
        <div className="brand-user">
          <div className="brand-avatar">M</div>
          {!collapsed && (
            <div style={{ flex: 1 }}>
              <div className="brand-name">Morphix</div>
              <div className="brand-tag">AI 运营协同</div>
            </div>
          )}
        </div>
      </div>

      <nav className="nav">
        {navItems.map((item) => {
          const Icon = item.icon
          return (
            <NavLink
              key={item.id}
              to={item.path}
              className={({ isActive }) =>
                `nav-item ${isActive ? 'active' : ''}`
              }
              title={collapsed ? item.label : ''}
            >
              <Icon size={18} className="nav-icon" />
              {!collapsed && <span className="nav-label">{item.label}</span>}
            </NavLink>
          )
        })}
      </nav>
    </aside>
  )
}

import { useState } from 'react'
import { BrowserRouter, useLocation } from 'react-router-dom'
import Sidebar from './layout/Sidebar'
import Header from './layout/Header'
import AppRoutes from './router'
import { navItems } from './utils/routes'
import './App.css'

function AppLayout() {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)
  const location = useLocation()

  const currentNav = navItems.find((item) =>
    item.path === '/' ? location.pathname === '/' : location.pathname.startsWith(item.path)
  )
  const pageTitle = currentNav?.label || 'Morphix 控制台'

  return (
    <div className="app-layout">
      <Sidebar
        collapsed={sidebarCollapsed}
        onToggle={() => setSidebarCollapsed(!sidebarCollapsed)}
      />
      <div className="app-main">
        <Header title={pageTitle} />
        <div className="app-content">
          <AppRoutes />
        </div>
      </div>
    </div>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <AppLayout />
    </BrowserRouter>
  )
}

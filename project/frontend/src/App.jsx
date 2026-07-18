import { useState } from 'react'
import { BrowserRouter, Routes, Route, useLocation } from 'react-router-dom'
import Sidebar from './components/layout/Sidebar'
import Header from './components/layout/Header'
import HomePage from './pages/Home/Home'
import BotsPage from './pages/Bots/Bots'
import BotDetailPage from './pages/Bots/BotDetail'
import SessionsPage from './pages/Sessions/Sessions'
import SessionDetailPage from './pages/Sessions/SessionDetail'
import PlaceholderPage from './pages/Placeholder'
import { navItems } from './utils/routes'
import { MessageCircle, Users, Workflow, Database, BarChart3 } from 'lucide-react'
import './design-tokens.css'
import './App.css'

function AppLayout() {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)
  const location = useLocation()

  const currentNav = navItems.find((item) => item.path === location.pathname)
  const pageTitle = currentNav?.label || '首页'

  return (
    <div className="app-layout">
      <Sidebar collapsed={sidebarCollapsed} onToggle={() => setSidebarCollapsed(!sidebarCollapsed)} />
      <div className="app-main">
        <Header title={pageTitle} />
        <div className="app-content">
          <Routes>
            <Route path="/" element={<HomePage />} />
            <Route path="/bots" element={<BotsPage />} />
            <Route path="/bots/:botId" element={<BotDetailPage />} />
            <Route path="/sessions" element={<SessionsPage />} />
            <Route path="/sessions/:sessionId" element={<SessionDetailPage />} />
            <Route path="/customers" element={<PlaceholderPage title="客户管理" icon={Users} />} />
            <Route path="/sop" element={<PlaceholderPage title="运营管理" icon={Workflow} />} />
            <Route path="/resources" element={<PlaceholderPage title="资源管理" icon={Database} />} />
            <Route path="/data" element={<PlaceholderPage title="数据面板" icon={BarChart3} />} />
          </Routes>
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

import { useState } from 'react'
import { BrowserRouter } from 'react-router-dom'
import Sidebar from './layout/Sidebar'
import AppRoutes from './router'
import { UserProvider } from './context/UserContext'
import './App.css'

function AppLayout() {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)

  return (
    <div className="app-layout">
      <Sidebar
        collapsed={sidebarCollapsed}
        onToggle={() => setSidebarCollapsed(!sidebarCollapsed)}
      />
      <div className="app-main">
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
      <UserProvider>
        <AppLayout />
      </UserProvider>
    </BrowserRouter>
  )
}

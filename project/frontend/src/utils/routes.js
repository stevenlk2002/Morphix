import { Home, Bot, MessageCircle, Users, Workflow, Database, BarChart3 } from 'lucide-react'

export const navItems = [
  { id: 'home', label: '首页', icon: Home, path: '/' },
  { id: 'bots', label: 'AI机器人', icon: Bot, path: '/bots' },
  { id: 'sessions', label: '渠道会话', icon: MessageCircle, path: '/sessions' },
  { id: 'customers', label: '客户管理', icon: Users, path: '/customers' },
  { id: 'sop', label: '运营管理', icon: Workflow, path: '/sop' },
  { id: 'resources', label: '资源管理', icon: Database, path: '/resources' },
  { id: 'data', label: '数据面板', icon: BarChart3, path: '/data' },
]

import {
  Home,
  Bot,
  MessageCircle,
  Users,
  Radio,
  BarChart3,
  type LucideIcon,
} from 'lucide-react'

export interface NavItem {
  id: string
  label: string
  icon: LucideIcon
  path: string
}

export const navItems: NavItem[] = [
  { id: 'home', label: '首页', icon: Home, path: '/' },
  { id: 'bots', label: 'AI机器人', icon: Bot, path: '/bots' },
  { id: 'sessions', label: '渠道会话', icon: MessageCircle, path: '/sessions' },
  { id: 'channels', label: '渠道账号', icon: Radio, path: '/channels/accounts' },
  { id: 'customers', label: '客户管理', icon: Users, path: '/customers' },
  { id: 'overview', label: '数据面板', icon: BarChart3, path: '/overview' },
]

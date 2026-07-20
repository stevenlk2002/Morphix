import {
  Home,
  Bot,
  MessageCircle,
  Users,
  Workflow,
  Package,
  Building2,
  BarChart3,
  Cpu,
  type LucideIcon,
} from 'lucide-react'

export interface NavItem {
  id: string
  label: string
  icon?: LucideIcon
  path: string
  children?: NavItem[]
}

/**
 * 左侧功能栏导航树，严格对齐 prototype/index.html 第 2209-2241 行的层级结构。
 * - 顶层为一级菜单，部分含 children 子模块。
 * - 子项无需图标（对齐原型 renderNav：子项仅渲染 label）。
 */
export const navItems: NavItem[] = [
  { id: 'home', label: '首页', icon: Home, path: '/' },
  {
    id: 'ai',
    label: 'AI机器人',
    icon: Bot,
    path: '/bots',
    children: [
      { id: 'robots', label: '对话机器人', path: '/bots' },
      { id: 'message-logs', label: '托管消息日志', path: '/bots/logs' },
    ],
  },
  {
    id: 'channels',
    label: '渠道会话',
    icon: MessageCircle,
    path: '/channels/accounts',
    children: [
      { id: 'channel-accounts', label: '渠道账号管理', path: '/channels/accounts' },
      { id: 'channel-sessions', label: '渠道会话管理', path: '/channels/sessions' },
      { id: 'channel-contacts', label: '渠道联系人列表', path: '/channels/contacts' },
      { id: 'channel-settings', label: '特殊渠道设置', path: '/channels/settings' },
    ],
  },
  {
    id: 'customers',
    label: '客户管理',
    icon: Users,
    path: '/customers',
    children: [
      { id: 'customer-list', label: '客户列表', path: '/customers' },
      { id: 'customer-groups', label: '客户分组管理', path: '/customers/groups' },
      { id: 'tags', label: '标签管理', path: '/customers/tags' },
    ],
  },
  {
    id: 'operations',
    label: '运营管理',
    icon: Workflow,
    path: '/operations/tasks',
    children: [
      { id: 'operation-tasks', label: '运营任务', path: '/operations/tasks' },
      { id: 'operation-sops', label: '运营SOP', path: '/operations/sops' },
    ],
  },
  {
    id: 'resources',
    label: '资源管理',
    icon: Package,
    path: '/resources',
    children: [
      { id: 'my-resources', label: '我的资源', path: '/resources' },
      { id: 'my-orders', label: '我的订单', path: '/resources/orders' },
    ],
  },
  {
    id: 'organization',
    label: '组织管理',
    icon: Building2,
    path: '/organization/info',
    children: [
      { id: 'org-info', label: '组织信息管理', path: '/organization/info' },
      { id: 'org-auth', label: '授权用户管理', path: '/organization/auth' },
      { id: 'org-roles', label: '角色权限管理', path: '/organization/roles' },
    ],
  },
  { id: 'data-panel', label: '数据面板', icon: BarChart3, path: '/overview' },
  { id: 'llm-config', label: 'LLM配置', icon: Cpu, path: '/llm-config' },
]

/**
 * 将层级 navItems 扁平化为一维数组（含所有父项与子项），
 * 便于按路径检索（如 App.tsx 解析页面标题）。
 *
 * @param items 待扁平化的导航项，默认使用全局 navItems。
 * @returns 扁平化后的 NavItem 数组。
 */
export function flattenNavItems(items: NavItem[] = navItems): NavItem[] {
  const result: NavItem[] = []
  for (const item of items) {
    result.push(item)
    if (item.children && item.children.length > 0) {
      result.push(...flattenNavItems(item.children))
    }
  }
  return result
}

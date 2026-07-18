import { Routes, Route } from 'react-router-dom'
import { Workflow, Database } from 'lucide-react'
import HomePage from './pages/Home/Home'
import BotsPage from './pages/Bots/Bots'
import BotDetailPage from './pages/Bots/BotDetail'
import SessionsPage from './pages/Sessions/Sessions'
import SessionDetailPage from './pages/Sessions/SessionDetail'
import ChannelAccountsPage from './pages/Channels/ChannelAccounts'
import ChannelContactsPage from './pages/Channels/ChannelContacts'
import ChannelSessionsPage from './pages/Channels/ChannelSessions'
import CustomerListPage from './pages/Customers/CustomerList'
import DataOverviewPage from './pages/Overview/DataOverview'
import ChannelDistributionPage from './pages/Overview/ChannelDistribution'
import PlaceholderPage from './pages/Placeholder'

/**
 * v6 路由表。
 * - 资源域页面（Bots/Home/Sessions）直接使用资源 / 契约 API。
 * - prototype 独有页（渠道 / 客户 / 数据概览 / 渠道分布）由控制台内 React/TS 重建。
 */
export default function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<HomePage />} />
      <Route path="/bots" element={<BotsPage />} />
      <Route path="/bots/:botId" element={<BotDetailPage />} />
      <Route path="/sessions" element={<SessionsPage />} />
      <Route path="/sessions/:sessionId" element={<SessionDetailPage />} />
      <Route path="/channels/accounts" element={<ChannelAccountsPage />} />
      <Route path="/channels/contacts" element={<ChannelContactsPage />} />
      <Route path="/channels/sessions" element={<ChannelSessionsPage />} />
      <Route path="/customers" element={<CustomerListPage />} />
      <Route path="/overview" element={<DataOverviewPage />} />
      <Route path="/overview/distribution" element={<ChannelDistributionPage />} />
      <Route path="/sop" element={<PlaceholderPage title="运营管理" icon={Workflow} />} />
      <Route path="/resources" element={<PlaceholderPage title="资源管理" icon={Database} />} />
    </Routes>
  )
}

import { Routes, Route } from 'react-router-dom'
import HomePage from './pages/Home/Home'
import BotsPage from './pages/Bots/Bots'
import BotDetailPage from './pages/Bots/BotDetail'
import BotCreatePage from './pages/Bots/BotCreate'
import SessionsPage from './pages/Sessions/Sessions'
import SessionDetailPage from './pages/Sessions/SessionDetail'
import ChannelAccountsPage from './pages/Channels/ChannelAccounts'
import AccountAddPage from './pages/Channels/AccountAdd'
import ChannelHostingPage from './pages/Channels/ChannelHosting'
import ChannelContactsPage from './pages/Channels/ChannelContacts'
import ChannelSessionsPage from './pages/Channels/ChannelSessions'
import TeamCreatePage from './pages/Teams/TeamCreate'
import TeamManagePage from './pages/Teams/TeamManage'
import CustomerListPage from './pages/Customers/CustomerList'
import CustomerGroupsPage from './pages/Customers/Groups'
import TagsPage from './pages/Customers/Tags'
import BotLogsPage from './pages/Bots/Logs'
import ResourcesPage from './pages/Resources/Resources'
import OrdersPage from './pages/Resources/Orders'
import ChannelDistributionPage from './pages/Overview/ChannelDistribution'
import LlmConfigPage from './pages/LlmConfig/LlmConfig'
import OrgInfoPage from './pages/Organization/OrgInfo'
import AuthPage from './pages/Organization/Auth'
import RolesPage from './pages/Organization/Roles'
import ChannelSettingsPage from './pages/Channels/ChannelSettings'
import OperationTasksPage from './pages/Operations/OperationTasks'
import OperationTaskEditPage from './pages/Operations/OperationTaskEdit'
import OperationTaskCreatePage from './pages/Operations/OperationTaskCreatePage'
import SopListPage from './pages/Operations/SopList'
import SopCreateCustomerPage from './pages/Operations/SopCreateCustomer'
import SopCreateGroupPage from './pages/Operations/SopCreateGroup'
import SopRecordsPage from './pages/Operations/SopRecords'
import { OrchestratePage } from './pages/Bots/Orchestrate'
import DataPanelPage from './pages/DataPanel/DataPanel'
import MessagesPage from './pages/Messages/MessagesPage'

/**
 * v6 路由表。
 * - 资源域页面（Bots/Home/Sessions）直接使用资源 / 契约 API。
 * - prototype 独有页（渠道 / 客户 / 数据概览 / 渠道分布）由控制台内 React/TS 重建。
 * - 层级导航中暂无专属实现的子模块由 PlaceholderPage 兜底。
 */
export default function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<HomePage />} />
      <Route path="/bots" element={<BotsPage />} />
      <Route path="/bots/create" element={<BotCreatePage />} />
      <Route path="/bots/:botId" element={<BotDetailPage />} />
      <Route path="/bots/:botId/orchestrate" element={<OrchestratePage />} />
      <Route path="/bots/logs" element={<BotLogsPage />} />
      <Route path="/sessions" element={<SessionsPage />} />
      <Route path="/sessions/:sessionId" element={<SessionDetailPage />} />
      <Route path="/channels/accounts" element={<ChannelAccountsPage />} />
      <Route path="/channels/accounts/add" element={<AccountAddPage />} />
      <Route path="/channels/accounts/:id/hosting" element={<ChannelHostingPage />} />
      <Route path="/teams/create" element={<TeamCreatePage />} />
      <Route path="/teams/:id/manage" element={<TeamManagePage />} />
      <Route path="/channels/contacts" element={<ChannelContactsPage />} />
      <Route path="/channels/sessions" element={<ChannelSessionsPage />} />
      <Route path="/channels/settings" element={<ChannelSettingsPage />} />
      <Route path="/customers" element={<CustomerListPage />} />
      <Route path="/customers/groups" element={<CustomerGroupsPage />} />
      <Route path="/customers/tags" element={<TagsPage />} />
      <Route path="/operations/tasks" element={<OperationTasksPage />} />
      <Route path="/operations/tasks/create" element={<OperationTaskCreatePage />} />
      <Route path="/operations/tasks/:id/edit" element={<OperationTaskEditPage />} />
      <Route path="/operations/sops" element={<SopListPage />} />
      <Route path="/operations/sops/create-customer" element={<SopCreateCustomerPage />} />
      <Route path="/operations/sops/create-group" element={<SopCreateGroupPage />} />
      <Route path="/operations/sops/:id/records" element={<SopRecordsPage />} />
      <Route path="/resources" element={<ResourcesPage />} />
      <Route path="/resources/orders" element={<OrdersPage />} />
      <Route path="/organization/info" element={<OrgInfoPage />} />
      <Route path="/organization/auth" element={<AuthPage />} />
      <Route path="/organization/roles" element={<RolesPage />} />
      <Route path="/overview" element={<DataPanelPage />} />
      <Route path="/overview/distribution" element={<ChannelDistributionPage />} />
      <Route path="/llm-config" element={<LlmConfigPage />} />
      <Route path="/data-panel" element={<DataPanelPage />} />
      <Route path="/messages" element={<MessagesPage />} />
    </Routes>
  )
}

/** 渠道会话管理域 DTO 类型（snake_case DB → camelCase）。 */

/** 团队。 */
export interface TeamDTO {
  id: string
  name: string
  seatsLeft: number
  energyValue: number
}

/** 渠道账号（扩展 DTO）。 */
export interface AccountDTO {
  id: string
  name: string
  channel: string
  channelType: 'wecom' | 'wechat' | 'whatsapp' | 'business_whatsapp' | string
  protocol: string
  status: 'online' | 'offline' | 'warning' | string
  online: boolean
  sessionsCount: number
  teamId: string
  boundBot: string
  seatsLeft?: number | null
  onlineSessions?: number | null
  teamName?: string | null
}

/** 渠道联系人。 */
export interface ContactDTO {
  id: string
  accountId: string
  channel: string
  channelType: string
  name: string
  nickname: string
  type: 'customer' | 'internal' | 'customer_group' | 'internal_group' | string
  status: 'online' | 'offline' | string
  remark: string
  description: string
  addTime: string
  source: string
}

/** 客户档案。 */
export interface CustomerProfileDTO {
  id: string
  contactId: string
  phone: string
  email: string
  company: string
  position: string
  region: string
  age: number | null
  birthday: string
  remark: string
  addTime: string
  addChannel: string
  signature: string
}

/** 沟通记录。 */
export interface CommunicationRecordDTO {
  id: string
  customerId: string
  content: string
  aiSummary: string
  type: string
  createdAt: string
}

/** 自定义属性。 */
export interface CustomAttributeDTO {
  id: string
  customerId: string
  name: string
  value: string
}

/** 联系人详情（聚合）。 */
export interface ContactDetailDTO {
  contact: ContactDTO
  profile: CustomerProfileDTO | null
  communications: CommunicationRecordDTO[]
  attributes: CustomAttributeDTO[]
}

/** 渠道会话（IM 收件箱）。 */
export interface SessionDTO {
  id: string
  accountId: string
  contactId: string | null
  name: string
  channel: string
  channelType: string
  lastMessage: string
  lastTime: string
  unreadCount: number
  readStatus: 'read' | 'unread' | string
  hostedStatus: 'hosted' | 'unhosted' | string
  hostedBotId: string | null
  owner: string
  onlineStatus: 'online' | 'offline' | string
  sessionType: string
  externalTag: string
  addTime: string
  hostingChain: string
}

/** 聊天消息（复用 messages 表）。 */
export interface MessageDTO {
  id: string
  conversationId: string
  senderType: 'bot' | 'user' | 'system' | string
  content: string
  createdAt: string
}

/** 托管批量会话。 */
export interface HostingSessionDTO {
  id: string
  sessionKey: string
  accountId: string
  customerName: string
  customerRemark: string
  addTime: string
  hostedStatus: 'hosted' | 'unhosted' | string
  hostingChain: string
}

/** 托管规则。 */
export interface HostingRuleDTO {
  id: string | null
  accountId: string | null
  autoResumeSeconds: number | null
  autoCancelEnabled: boolean
}

/** 企微接入主体。 */
export interface WechatSubjectDTO {
  id: string
  fullName: string
  shortName: string
  corpId: string
  configJson: string
}

/** 托管可选机器人（静态）。 */
export interface HostingBotDTO {
  id: string
  name: string
}

/** 创建/更新企微主体请求体。 */
export interface WechatSubjectInput {
  fullName: string
  shortName: string
  corpId: string
  configJson?: string
}

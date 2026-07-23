/** 渠道会话管理域 DTO 类型（snake_case DB → camelCase）。 */

/** 团队。 */
export interface TeamDTO {
  id: string
  name: string
  seatsLeft: number
  energyValue: number
  /** 团队简介（本期新增）。 */
  description: string
}

/** 团队成员（冗余 account/nickname/role，来自授权用户）。 */
export interface TeamMemberDTO {
  id: string
  teamId: string
  userId: string
  account: string
  nickname: string
  role: string
  joinedAt: string
}

/** 更新团队请求体。 */
export interface TeamUpdateRequest {
  name?: string
  description?: string
}

/** 批量添加团队成员请求体。 */
export interface AddTeamMembersRequest {
  userIds: string[]
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
  // —— 账号卡片增强（本期） ——
  /** 企微真实头像 URL；空串表示未设置。 */
  avatar?: string | null
  /** 默认单聊机器人 id；空串表示未设置。 */
  defaultSingleBotId?: string | null
  /** 默认群聊机器人 id；空串表示未设置。 */
  defaultGroupBotId?: string | null
  /** 默认单聊机器人显示名（列表 JOIN 聚合）；空态为 null。 */
  defaultSingleBotName?: string | null
  /** 默认群聊机器人显示名（列表 JOIN 聚合）；空态为 null。 */
  defaultGroupBotName?: string | null
}

/** 已上线机器人枚举项（默认机器人选择器数据源）。 */
export interface AvailableBotDTO {
  id: string
  name: string
}

/** 设置默认单聊/群聊机器人请求体（null = 清空）。 */
export interface SetDefaultBotsRequest {
  singleBotId?: string | null
  groupBotId?: string | null
}

/** 切换账号上下线状态请求体。 */
export interface UpdateAccountStatusRequest {
  status: 'online' | 'offline'
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
  /** iPad 协议外部联系人标签（labelid[] 原样镜像，决策 #2）。 */
  tags?: string[]
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
  remoteSessionId: string | null
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

/** 企业微信托管：扫码后返回的用户信息（loginType=2 时携带）。 */
export interface WecomUserInfo {
  acctid?: string
  avatar?: string
  corpId?: string | number
  mobile?: string
  nickname?: string
  realname?: string
  userId?: string | number
  corpName?: string
}

/** 企业微信托管：启动扫码响应。 */
export interface WecomHostStartResp {
  uuid: string
  qrcode: string | null
  qrcodeData: string | null
  qrcodeKey: string
  ttl: number
  mock: boolean
}

/** 企业微信托管：验证码校验响应。 */
export interface WecomHostVerifyResp {
  ok: boolean
  skip?: boolean
}

/** 企业微信托管：轮询登录状态响应。 */
export interface WecomHostPollResp {
  loginType: 0 | 1 | 2
  userInfo: WecomUserInfo | null
  longLinkState: string
  mock: boolean
  account?: Record<string, unknown>
}

/** iPad 协议：群 DTO。 */
export interface GroupDTO {
  id: string
  accountId: string
  roomId: string
  groupType: 'customer_group' | 'internal_group' | string
  name: string
  total: number
  roomUrl: string
  noticeContent: string
  createTime: string
  updateTime: string
}

/** iPad 协议：群成员 DTO。 */
export interface GroupMemberDTO {
  id: string
  groupId: string
  uin: string
  userId: string
  nickname: string
  realname: string
  avatar: string
  roomNickname: string
  sex: number
  mobile: string
  joinTime: string
}

/** iPad 协议：群详情（含成员）。 */
export interface GroupDetailDTO {
  group: GroupDTO
  members: GroupMemberDTO[]
  noticeContent: string
  total: number
}

/** iPad 协议：同步触发响应。 */
export interface SyncResultDTO {
  started?: boolean
  skipped?: boolean
  accountId?: string
  message?: string
}

/** iPad 协议：同步状态。 */
export interface SyncStatusDTO {
  accountId: string
  syncStatus: '' | 'syncing' | 'success' | 'degraded' | 'error'
  lastSyncAt: string
  syncing: boolean
}

/** iPad 协议：发送文本消息响应。 */
export interface SendTextResultDTO {
  msgId: string
  ok: boolean
  serverId: string
}

/** iPad 协议：标签（映射后，决策 #9 双写）。 */
export interface LabelDTO {
  accountId: string
  labelId: string
  labelName: string
  labelType: number
  labelGroupId: string
  tagId: string
  syncType: number
}

/** iPad 协议：标签同步结果。 */
export interface LabelSyncResultDTO {
  accountId: string
  total: number
  synced: number
  skipped: boolean
}

/** iPad 协议：搜索添加外部联系人结果项。 */
export interface ContactSearchResultDTO {
  userId: string
  name: string
  sex: number
  headImg: string
  ticket: string
  openId: string
  corpId: string
  state: string
}

/** iPad 协议：搜索添加外部联系人请求体。 */
export interface AddSearchRequestDTO {
  vid: string
  openId?: string
  phone?: string
  content?: string
  ticket?: string
  useDirectAdd?: boolean
}

/** iPad 协议：消息历史回填结果。 */
export interface BackfillResultDTO {
  accountId: string
  sessionId: string
  upserted: number
  triggered: boolean
  message: string
}

/** iPad 协议：富媒体发送结果。 */
export interface SendMediaResultDTO {
  msgId: string
  serverId: string
  contentType: 'image' | 'file' | string
  mediaUrl: string
  ok: boolean
}

/** iPad 协议：联系人标签（已解析真实名称）。 */
export interface ContactLabelDTO {
  labelId: string
  labelName: string
}

/** iPad 协议：扩展消息（含 serverId/msgType/direction/contentType/media）。 */
export interface MessageExtDTO {
  id: string
  conversationId: string
  senderType: 'bot' | 'user' | 'system' | string
  content: string
  createdAt: string
  serverId: string
  msgType: number
  senderId: string
  direction: 'inbound' | 'outbound' | string
  contentType: 'text' | 'image' | 'file' | string
  mediaUrl: string
  mediaMeta: unknown
  isRead: boolean
  channelAccountId: string
}

/** 建群请求体（memberIds = Morphix 联系人 id；后端解析为 iPad user_id）。 */
export interface CreateGroupRequestDTO {
  memberIds: string[]
  roomName?: string
}

/** 一键已读（本地）响应。 */
export interface MarkReadLocalResultDTO {
  updated: number
}

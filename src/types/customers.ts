/** 客户管理域 DTO 类型（snake_case DB → camelCase）。 */

/** 客户列表项（聚合）。 */
export interface CustomerListItem {
  id: string
  contactId: string
  name: string
  nickname: string
  accountId: string
  account: string
  channel: string
  channelType: 'wecom' | 'wechat' | 'whatsapp' | string
  type: 'customer' | 'internal' | string
  aiSummaryEnabled: boolean
  lastCommunicationTime: string
  lastCommunicationContent: string
  lastCommunicationAiSummary: string
  addTime: string
  tags: CustomerTagRelation[]
  remark: string
  phone: string
  email: string
  company: string
  position: string
  region: string
  age: number | null
  birthday: string
  signature: string
  description: string
  source: string
  status: string
}

/** 标签关系（含组信息）。 */
export interface CustomerTagRelation {
  id: string
  name: string
  color: string
  groupId: string
  groupName: string
}

/** 标签组（含组内标签）。 */
export interface TagGroupDTO {
  id: string
  name: string
  isHot: boolean
  createdAt?: string
  tags: TagDTO[]
}

/** 标签。 */
export interface TagDTO {
  id: string
  name: string
  color: string
  rule?: string
}

/** 客户分组。 */
export interface CustomerGroupDTO {
  id: string
  name: string
  type: 'system' | 'custom' | string
  count: number
  createdAt: string
  updatedAt: string
  editor: string
}

/** 客户列表分页信封。 */
export interface CustomerListPage {
  items: CustomerListItem[]
  total: number
  page: number
  pageSize: number
  hasMore: boolean
}

/** 客户列表筛选参数。 */
export interface CustomerFilter {
  type?: 'external' | 'internal'
  accountId?: string
  channel?: string
  channelType?: string
  keyword?: string
  tagIds?: string
  dateFrom?: string
  dateTo?: string
  page?: number
  pageSize?: number
}

/** 客户分组（含成员）。 */
export interface CustomerGroupWithMembersDTO extends CustomerGroupDTO {
  members: CustomerGroupMemberDetail[]
}

/** 分组成员详情（含客户聚合数据，供详情抽屉使用）。 */
export interface CustomerGroupMemberDetail {
  customerId: string
  customerName: string
  contactId: string
  nickname: string
  accountId: string
  channel: string
  channelType: string
  type: string
  lastCommunicationTime: string
  lastCommunicationContent: string
  lastCommunicationAiSummary: string
  addTime: string
  tags: CustomerTagRelation[]
  remark: string
  phone: string
  email: string
  company: string
  position: string
  region: string
  age: number | null
  birthday: string
  signature: string
}

/** 批量 AI 总结请求。 */
export interface BatchAiSummaryRequest {
  contactIds: string[]
  enabled: boolean
}

/** 批量标签请求。 */
export interface BatchTagsRequest {
  contactIds: string[]
  tagIds: string[]
  mode: 'add' | 'remove' | 'replace'
}

/** 创建分组含成员请求。 */
export interface CustomerGroupCreateWithMembersRequest {
  name: string
  type?: string
  memberIds: string[]
}

/** 添加分组成员请求。 */
export interface AddMembersRequest {
  contactIds: string[]
}

/** 批量删除客户分组请求。 */
export interface CustomerGroupDeleteRequest {
  group_ids: string[]
}

/** 客户档案更新请求体。 */
export interface CustomerProfileUpdateRequest {
  phone?: string
  email?: string
  company?: string
  position?: string
  region?: string
  age?: number
  birthday?: string
  remark?: string
  aiSummaryEnabled?: boolean
}

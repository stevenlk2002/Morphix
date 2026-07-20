/**
 * 共享资源类型定义。
 * 本批次（LLM 配置 / 组织信息管理）率先使用，后续批次（客户、渠道、订单等）复用。
 */

/** 单个大模型接入配置。 */
export interface LlmModelConfig {
  vendor: string
  model: string
  apiKey: string
  apiBaseUrl?: string
  enabled?: boolean
}

/** LLM 配置：主模型 + 副模型（备用）。 */
export interface LlmConfig {
  primary: LlmModelConfig & { enabled: boolean }
  secondary: LlmModelConfig & { enabled: boolean }
}

/** 组织基本信息。 */
export interface OrgInfo {
  orgName: string
  contactName: string
  contactPhone: string
}

/**
 * 分页信封，后续批次接口返回复用。
 * @template T 列表项类型
 */
export interface Paginated<T> {
  items: T[]
  total: number
  page: number
  pageSize: number
}

/** 单个客户标签。 */
export interface Tag {
  id: string
  name: string
  color: string
  rule?: string
  groupId?: string
  groupName?: string
}

/** 标签组：一组同类客户标签。 */
export interface TagGroup {
  id: string
  name: string
  color: string
  tags: Tag[]
  isHot?: boolean
  createdAt?: string
}

/** 运营 SOP（标准操作流程）。 */
export interface Sop {
  id: string
  /** 客户SOP | 群聊SOP */
  type: string
  enabled: boolean
  /** 运行中 | 未运行 */
  status: string
  name: string
}

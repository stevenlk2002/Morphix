/**
 * 运营SOP API 封装。
 *
 * 端点：
 * - listSops     GET    /api/sops
 * - createSop    POST   /api/sops
 * - getSop       GET    /api/sops/:id
 * - updateSop    PUT    /api/sops/:id
 * - deleteSop    DELETE /api/sops/:id
 * - toggleSop    PATCH  /api/sops/:id/toggle
 */
import { api } from './client'
import type {
  SopItem,
  SopCreateRequest,
  SopUpdateRequest,
  SopDeleteResponse,
  SopListParams,
  SopRecord,
} from '../types/sops'

export const sopsApi = {
  /** SOP 列表（筛选 + 排序）。 */
  list: (params?: SopListParams) =>
    api.get<SopItem[]>('/sops', { params }),

  /** 创建 SOP。 */
  create: (data: SopCreateRequest) =>
    api.post<SopItem>('/sops', data),

  /** SOP 详情。 */
  get: (id: string) =>
    api.get<SopItem>(`/sops/${id}`),

  /** 更新 SOP。 */
  update: (id: string, data: SopUpdateRequest) =>
    api.put<SopItem>(`/sops/${id}`, data),

  /** 启停切换。 */
  toggle: (id: string, enabled: boolean) =>
    api.patch<SopItem>(`/sops/${id}/toggle`, { enabled }),

  /** 删除 SOP。 */
  delete: (id: string) =>
    api.delete<SopDeleteResponse>(`/sops/${id}`),

  /** SOP 运行记录列表。 */
  listRecords: (sopId: string) =>
    api.get<SopRecord[]>(`/sops/${sopId}/records`),
}

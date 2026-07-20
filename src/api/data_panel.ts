/**
 * 数据面板 API 封装。
 *
 * 端点：
 * - getMetrics      GET /api/data-panel/metrics
 * - getFilterOptions GET /api/data-panel/filter-options
 */
import { api } from './client'
import type {
  DataPanelMetricsResponse,
  DataPanelFilterOptionsResponse,
} from '../types/data_panel'

export interface MetricsParams extends Record<string, string | undefined> {
  start?: string
  end?: string
  channel?: string
  account?: string
  bot?: string
}

export const dataPanelApi = {
  /** 获取数据面板指标（聚合 total + 每日 daily）。 */
  getMetrics: (params?: MetricsParams) =>
    api.get<DataPanelMetricsResponse>('/data-panel/metrics', { params }),

  /** 获取筛选器下拉选项。 */
  getFilterOptions: () =>
    api.get<DataPanelFilterOptionsResponse>('/data-panel/filter-options'),
}

/**
 * DataPanel — 数据面板页面。
 *
 * 严格对齐原型 index.html 7192-7244 行：
 * - FilterCard：日期范围 + 渠道/账号/机器人下拉
 * - 6 张指标卡片（checked toggle）
 * - 1 张比率卡片（3 条 rate，checked toggle）
 * - SVG 图表 + legend
 */
import React, { useEffect, useState, useCallback, useMemo } from 'react'
import {
  Check,
  HelpCircle,
  MessageSquare,
  Users,
  Bot,
  Send,
  Bell,
} from 'lucide-react'
import { dataPanelApi } from '../../api/data_panel'
import { DataChart, DataChartLegend } from './DataChart'
import type {
  DailyMetric,
  MetricsTotal,
  FilterOption,
} from '../../types/data_panel'
import {
  METRIC_KEYS,
  RATE_KEYS,
  METRIC_LABELS,
  RATE_LABELS,
  METRIC_ACCENT,
  METRIC_HELP,
  RATE_HELP,
} from '../../types/data_panel'
import './DataPanel.css'

/** 指标对应的图标组件（与原型 icons 对应）。 */
const METRIC_ICONS: Record<string, React.ReactNode> = {
  new_sessions: <MessageSquare size={18} />,
  hosted_sessions: <Users size={18} />,
  bot_processed_sessions: <Bot size={18} />,
  total_messages: <Send size={18} />,
  bot_processed_messages: <Bot size={18} />,
  bot_transfers: <Bell size={18} />,
}

const DataPanel: React.FC = () => {
  // ---- 状态 ----
  const [loading, setLoading] = useState(true)
  const [total, setTotal] = useState<MetricsTotal | null>(null)
  const [daily, setDaily] = useState<DailyMetric[]>([])

  // 筛选器选项
  const [channelOptions, setChannelOptions] = useState<FilterOption[]>([])
  const [accountOptions, setAccountOptions] = useState<FilterOption[]>([])
  const [botOptions, setBotOptions] = useState<FilterOption[]>([])

  // 筛选器值
  const [dateRange, setDateRange] = useState('2026-07-03 → 2026-07-09')
  const [selectedChannel, setSelectedChannel] = useState('')
  const [selectedAccount, setSelectedAccount] = useState('')
  const [selectedBot, setSelectedBot] = useState('')

  // 卡片 checked 状态（默认全选）
  const [checkedMetrics, setCheckedMetrics] = useState<Set<string>>(
    new Set(METRIC_KEYS)
  )
  const [checkedRates, setCheckedRates] = useState<Set<string>>(
    new Set(RATE_KEYS)
  )

  // ---- 数据加载 ----
  const fetchData = useCallback(async () => {
    setLoading(true)
    try {
      const params: Record<string, string> = {}
      if (selectedChannel) params.channel = selectedChannel
      if (selectedAccount) params.account = selectedAccount
      if (selectedBot) params.bot = selectedBot
      const res = await dataPanelApi.getMetrics(params)
      setTotal(res.total)
      setDaily(res.daily)
    } catch (err) {
      console.error('Failed to fetch data panel metrics:', err)
    } finally {
      setLoading(false)
    }
  }, [selectedChannel, selectedAccount, selectedBot])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  useEffect(() => {
    // 加载筛选器选项
    dataPanelApi
      .getFilterOptions()
      .then((opts) => {
        setChannelOptions(opts.channels)
        setAccountOptions(opts.accounts)
        setBotOptions(opts.bots)
      })
      .catch(() => {
        /* 静默降级，使用默认选项 */
      })
  }, [])

  // ---- Toggle ----
  const toggleMetric = (key: string) => {
    setCheckedMetrics((prev) => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })
  }

  const toggleRate = (key: string) => {
    setCheckedRates((prev) => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })
  }

  // ---- 从 total 获取数值 ----
  const getMetricValue = (key: string): number => {
    if (!total) return 0
    return (total as unknown as Record<string, number>)[key] || 0
  }

  // ---- 转换为数组用于图表 ----
  const checkedMetricArr = useMemo(
    () => Array.from(checkedMetrics),
    [checkedMetrics]
  )
  const checkedRateArr = useMemo(() => Array.from(checkedRates), [checkedRates])

  return (
    <div>
      {/* ======== FilterCard ======== */}
      <div className="card" style={{ marginBottom: 20 }}>
        <div className="card-body">
          <div className="dp-filter-bar">
            <label>日期</label>
            <input
              className="input"
              value={dateRange}
              onChange={(e) => setDateRange(e.target.value)}
              readOnly
            />
            <label>渠道类型</label>
            <select
              className="select"
              value={selectedChannel}
              onChange={(e) => setSelectedChannel(e.target.value)}
            >
              {channelOptions.length > 0
                ? channelOptions.map((o) => (
                    <option key={o.value} value={o.value}>
                      {o.label}
                    </option>
                  ))
                : (
                  <>
                    <option value="">全部</option>
                    <option value="企业微信">企业微信</option>
                    <option value="微信">微信</option>
                    <option value="WhatsApp">WhatsApp</option>
                  </>
                )}
            </select>
            <label>托管账号</label>
            <select
              className="select"
              value={selectedAccount}
              onChange={(e) => setSelectedAccount(e.target.value)}
            >
              {accountOptions.length > 0
                ? accountOptions.map((o) => (
                    <option key={o.value} value={o.value}>
                      {o.label}
                    </option>
                  ))
                : (
                  <>
                    <option value="">全部</option>
                    <option value="竹绿-健康">竹绿-健康</option>
                    <option value="恒康倍力">恒康倍力</option>
                  </>
                )}
            </select>
            <label>托管机器人</label>
            <select
              className="select"
              value={selectedBot}
              onChange={(e) => setSelectedBot(e.target.value)}
            >
              {botOptions.length > 0
                ? botOptions.map((o) => (
                    <option key={o.value} value={o.value}>
                      {o.label}
                    </option>
                  ))
                : (
                  <>
                    <option value="">全部</option>
                    <option value="野风秋大健康机器人">野风秋大健康机器人</option>
                    <option value="AI客服-1">AI客服-1</option>
                  </>
                )}
            </select>
          </div>
        </div>
      </div>

      {/* ======== Metrics Grid + Rate Card ======== */}
      {loading ? (
        <div className="card" style={{ minHeight: 200, display: 'grid', placeItems: 'center' }}>
          <span style={{ color: 'var(--text-secondary)' }}>加载中…</span>
        </div>
      ) : (
        <>
          <div className="dp-metrics">
            {/* 6 张指标卡片 */}
            {METRIC_KEYS.map((key) => {
              const isChecked = checkedMetrics.has(key)
              const accent = METRIC_ACCENT[key]
              return (
                <div
                  key={key}
                  className={`dp-metric accent-${accent}${isChecked ? ' checked' : ''}`}
                  onClick={() => toggleMetric(key)}
                >
                  <div className="dp-metric-top">
                    <span className="dp-metric-check">
                      <Check size={10} strokeWidth={3} />
                    </span>
                    <span className="dp-metric-icon">{METRIC_ICONS[key]}</span>
                  </div>
                  <div className="dp-metric-label">
                    {METRIC_LABELS[key]}
                    <span
                      className="dp-metric-help"
                      onClick={(e) => e.stopPropagation()}
                    >
                      <HelpCircle size={12} />
                      <span className="dp-metric-tip">
                        {METRIC_HELP[key]}
                      </span>
                    </span>
                  </div>
                  <div className="dp-metric-value">{getMetricValue(key)}</div>
                </div>
              )
            })}

            {/* 比率卡片 */}
            <div className="dp-rate-card">
              <div className="dp-rates-title">指标筛选</div>
              {RATE_KEYS.map((key) => {
                const isChecked = checkedRates.has(key)
                return (
                  <div
                    key={key}
                    className={`dp-rate${isChecked ? ' checked' : ''}`}
                    onClick={() => toggleRate(key)}
                  >
                    <span className="dp-rate-check">
                      <Check size={10} strokeWidth={3} />
                    </span>
                    <span className="dp-rate-label">{RATE_LABELS[key]}</span>
                    <span className="dp-rate-help">
                      <span className="dp-rate-tip">{RATE_HELP[key]}</span>
                      <HelpCircle size={12} />
                    </span>
                  </div>
                )
              })}
            </div>
          </div>

          {/* ======== Chart Card ======== */}
          <div className="card">
            <div className="card-header">
              <span
                className="card-title"
                style={{ display: 'flex', alignItems: 'center', gap: 8 }}
              >
                <span>
                  数据总览
                  <span
                    style={{
                      fontWeight: 400,
                      fontSize: 13,
                      color: 'var(--text-secondary)',
                    }}
                  >
                    （近七天）
                  </span>
                </span>
                <span
                  className="tooltip"
                  data-tip="该处数据每十分钟更新一次"
                  style={{ color: 'var(--text-tertiary)', cursor: 'help' }}
                >
                  <HelpCircle size={14} />
                </span>
              </span>
            </div>
            <div className="dp-chart-body">
              <div className="chart-container">
                <DataChart
                  data={daily}
                  checkedMetrics={checkedMetricArr}
                  checkedRates={checkedRateArr}
                  height={320}
                />
              </div>
              <DataChartLegend
                checkedMetrics={checkedMetricArr}
                checkedRates={checkedRateArr}
              />
            </div>
          </div>
        </>
      )}
    </div>
  )
}

export default DataPanel

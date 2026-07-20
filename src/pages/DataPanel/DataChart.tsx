/**
 * DataChart — SVG 双轴图表组件。
 *
 * 严格对齐原型 index.html 5100-5269 行 drawDataChart() 逻辑：
 * - 左 Y 轴：绝对值 0-5（柱状图 6 维）
 * - 右 Y 轴：比率 0-100%（折线图 3 维）
 * - crosshair tooltip 跟随鼠标
 * - legend 底部图例
 */
import React, { useRef, useCallback, useEffect, useState } from 'react'
import type { DailyMetric } from '../../types/data_panel'
import {
  BAR_COLORS,
  LINE_COLORS,
  METRIC_LABELS,
  RATE_LABELS,
} from '../../types/data_panel'

interface TooltipRow {
  key: string
  label: string
  color: string
  isRate: boolean
}

const ALL_ROWS: TooltipRow[] = [
  { key: 'new_sessions', label: '新增会话数', color: BAR_COLORS.new_sessions, isRate: false },
  { key: 'hosted_sessions', label: '托管会话数', color: BAR_COLORS.hosted_sessions, isRate: false },
  { key: 'bot_processed_sessions', label: '机器人处理会话数', color: BAR_COLORS.bot_processed_sessions, isRate: false },
  { key: 'total_messages', label: '总消息数', color: BAR_COLORS.total_messages, isRate: false },
  { key: 'bot_processed_messages', label: '机器人处理消息数', color: BAR_COLORS.bot_processed_messages, isRate: false },
  { key: 'bot_transfers', label: '机器人转人工数', color: BAR_COLORS.bot_transfers, isRate: false },
  { key: 'msg_rate', label: '机器人消息处理率', color: LINE_COLORS.msg_rate, isRate: true },
  { key: 'session_rate', label: '机器人会话处理率', color: LINE_COLORS.session_rate, isRate: true },
  { key: 'transfer_rate', label: '机器人转人工率', color: LINE_COLORS.transfer_rate, isRate: true },
]

interface DataChartProps {
  data: DailyMetric[]
  checkedMetrics: string[]
  checkedRates: string[]
  width?: number
  height?: number
}

const PADDING = { top: 20, right: 60, bottom: 40, left: 40 }
const MAX_BAR = 5

/**
 * 由一系列点生成平滑曲线 path（Catmull-Rom 转三次贝塞尔）。
 * 曲线必然穿过所有数据点；tension 控制平滑度（0.5 为适中值，不出现过冲）。
 */
function smoothPath(points: Array<{ x: number; y: number }>, tension = 0.5): string {
  if (points.length === 0) return ''
  if (points.length === 1) {
    return `M${points[0].x.toFixed(1)},${points[0].y.toFixed(1)}`
  }
  const p = points
  let d = `M${p[0].x.toFixed(1)},${p[0].y.toFixed(1)}`
  for (let i = 0; i < p.length - 1; i++) {
    const p0 = p[i - 1] ?? p[i]
    const p1 = p[i]
    const p2 = p[i + 1]
    const p3 = p[i + 2] ?? p2
    const cp1x = p1.x + ((p2.x - p0.x) * tension) / 6
    const cp1y = p1.y + ((p2.y - p0.y) * tension) / 6
    const cp2x = p2.x - ((p3.x - p1.x) * tension) / 6
    const cp2y = p2.y - ((p3.y - p1.y) * tension) / 6
    d +=
      ` C${cp1x.toFixed(1)},${cp1y.toFixed(1)} ` +
      `${cp2x.toFixed(1)},${cp2y.toFixed(1)} ` +
      `${p2.x.toFixed(1)},${p2.y.toFixed(1)}`
  }
  return d
}

export const DataChart: React.FC<DataChartProps> = ({
  data,
  checkedMetrics,
  checkedRates,
  width: containerWidth,
  height: containerHeight = 320,
}) => {
  const containerRef = useRef<HTMLDivElement>(null)
  const svgRef = useRef<SVGSVGElement>(null)
  const [measuredWidth, setMeasuredWidth] = useState<number>(containerWidth || 0)
  const [tooltipPos, setTooltipPos] = useState<{ x: number; y: number } | null>(null)
  const [tooltipIdx, setTooltipIdx] = useState<number>(-1)

  // 测量容器实际宽度
  useEffect(() => {
    const el = containerRef.current
    if (!el) return
    const update = () => {
      const w = el.clientWidth
      if (w > 0) setMeasuredWidth(w)
    }
    update()
    const ro = new ResizeObserver(update)
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

  const w = measuredWidth || containerWidth || 700
  const h = containerHeight || 320
  const chartW = w - PADDING.left - PADDING.right
  const chartH = h - PADDING.top - PADDING.bottom

  const activeBars = checkedMetrics.filter((k) => k in BAR_COLORS)
  const activeRates = checkedRates.filter((k) => k in LINE_COLORS)

  const nBars = activeBars.length
  const gap = data.length > 0 ? chartW / data.length : 0
  const barW = nBars > 0 ? Math.min(22, (gap - 8) / nBars - 2) : 0

  const handleMouseMove = useCallback(
    (e: React.MouseEvent<SVGRectElement>) => {
      const svg = svgRef.current
      if (!svg || data.length === 0) return
      const rect = svg.getBoundingClientRect()
      // preserveAspectRatio="none" 时需换算出视口坐标
      const scaleX = w / rect.width
      const mx = (e.clientX - rect.left) * scaleX
      const chartX = PADDING.left
      let idx = Math.round(((mx - chartX) / chartW) * (data.length - 1))
      idx = Math.max(0, Math.min(data.length - 1, idx))
      setTooltipIdx(idx)
      setTooltipPos({ x: e.clientX, y: e.clientY })
    },
    [chartW, data.length, w]
  )

  const handleMouseLeave = useCallback(() => {
    setTooltipIdx(-1)
    setTooltipPos(null)
  }, [])

  const crosshairX =
    tooltipIdx >= 0 && data.length > 0
      ? PADDING.left + tooltipIdx * gap + gap / 2
      : 0

  // ---- 网格线与 Y 轴标签 ----
  const gridLines: React.ReactNode[] = []
  for (let i = 0; i <= 5; i++) {
    const y = PADDING.top + chartH - (i * chartH) / 5
    gridLines.push(
      <line
        key={`grid-${i}`}
        x1={PADDING.left}
        y1={y}
        x2={w - PADDING.right}
        y2={y}
        stroke="#f0f0f0"
        strokeDasharray="2,2"
      />
    )
    gridLines.push(
      <text
        key={`left-label-${i}`}
        x={PADDING.left - 4}
        y={y + 3}
        textAnchor="end"
        fontSize="10"
        fill="#999"
      >
        {Math.round((i * MAX_BAR) / 5)}
      </text>
    )
    gridLines.push(
      <text
        key={`right-label-${i}`}
        x={w - 40}
        y={y + 3}
        textAnchor="start"
        fontSize="10"
        fill="#999"
      >
        {i * 20}%
      </text>
    )
  }

  // ---- X 轴日期标签 ----
  const xLabels = data.map((d, i) => {
    const cx = PADDING.left + i * gap + gap / 2
    const label = d.date.length >= 10 ? d.date.slice(5) : d.date
    return (
      <text key={`xlabel-${i}`} x={cx} y={h - 20} textAnchor="middle" fontSize="10" fill="#999">
        {label}
      </text>
    )
  })

  // ---- 柱状图 ----
  const bars = data.flatMap((d, i) => {
    const cx = PADDING.left + i * gap + gap / 2
    return activeBars.map((key, j) => {
      const val = (d as unknown as Record<string, number>)[key] || 0
      const bh = (val / MAX_BAR) * chartH
      const x = cx - (nBars * barW) / 2 + j * barW
      const color = BAR_COLORS[key] || '#ccc'
      return (
        <rect
          key={`bar-${i}-${key}`}
          x={x}
          y={PADDING.top + chartH - bh}
          width={Math.max(barW - 1, 1)}
          height={bh}
          fill={color}
          rx="1"
        />
      )
    })
  })

  // ---- 折线图（平滑曲线） ----
  const lines = activeRates.map((key) => {
    const linePoints = data.map((d, i) => {
      const cx = PADDING.left + i * gap + gap / 2
      const val = (d as unknown as Record<string, number>)[key] || 0
      const cy = PADDING.top + chartH - (val / 100) * chartH
      return { x: cx, y: cy }
    })
    const linePath = smoothPath(linePoints)
    const color = LINE_COLORS[key] || '#000'
    return (
      <g key={`line-${key}`}>
        <path
          d={linePath}
          fill="none"
          stroke={color}
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        {data.map((d, i) => {
          const cx = PADDING.left + i * gap + gap / 2
          const val = (d as unknown as Record<string, number>)[key] || 0
          const cy = PADDING.top + chartH - (val / 100) * chartH
          return (
            <circle
              key={`dot-${key}-${i}`}
              cx={cx}
              cy={cy}
              r="3"
              fill={color}
              stroke="#fff"
              strokeWidth="1"
            />
          )
        })}
      </g>
    )
  })

  return (
    <div ref={containerRef} style={{ position: 'relative', width: '100%' }}>
      <svg
        ref={svgRef}
        width="100%"
        height={h}
        viewBox={`0 0 ${w} ${h}`}
        preserveAspectRatio="xMidYMid meet"
      >
        {gridLines}
        {bars}
        {lines}
        {xLabels}
        {/* Crosshair */}
        <line
          className="chart-crosshair"
          x1={crosshairX}
          y1={PADDING.top}
          x2={crosshairX}
          y2={PADDING.top + chartH}
          style={{ display: tooltipIdx >= 0 ? 'block' : 'none' }}
        />
        {/* Mouse overlay */}
        <rect
          x={PADDING.left}
          y={PADDING.top}
          width={chartW}
          height={chartH}
          fill="none"
          style={{ cursor: 'crosshair' }}
          onMouseMove={handleMouseMove}
          onMouseLeave={handleMouseLeave}
        />
      </svg>

      {/* Tooltip (fixed position overlay) */}
      {tooltipPos && tooltipIdx >= 0 && tooltipIdx < data.length && (
        <DataTooltip
          d={data[tooltipIdx]}
          rows={ALL_ROWS}
          mouseX={tooltipPos.x}
          mouseY={tooltipPos.y}
        />
      )}
    </div>
  )
}

// ---- Tooltip 子组件 ----

interface DataTooltipProps {
  d: DailyMetric
  rows: TooltipRow[]
  mouseX: number
  mouseY: number
}

const DataTooltip: React.FC<DataTooltipProps> = ({ d, rows, mouseX, mouseY }) => {
  const ref = useRef<HTMLDivElement>(null)
  const [style, setStyle] = useState<React.CSSProperties>({ display: 'none' })

  useEffect(() => {
    const el = ref.current
    if (!el) return
    // 先显示以测量尺寸
    el.style.display = 'block'
    const tipH = el.offsetHeight
    const tipW = el.offsetWidth

    let tx = mouseX + 12
    let ty = mouseY - tipH - 12
    if (tx + tipW > window.innerWidth) tx = mouseX - tipW - 12
    if (tx < 0) tx = 0
    if (ty + tipH > window.innerHeight) ty = mouseY + 12
    if (ty < 0) ty = 0

    setStyle({
      display: 'block',
      position: 'fixed',
      left: tx,
      top: ty,
    })
  }, [mouseX, mouseY])

  return (
    <div ref={ref} className="chart-tooltip" style={style}>
      <div className="chart-tooltip-date">{d.date}</div>
      {rows.map((r) => {
        const val = r.isRate
          ? `${(d as unknown as Record<string, number>)[r.key]}%`
          : (d as unknown as Record<string, number>)[r.key]
        return (
          <div key={r.key} className="chart-tooltip-row">
            <span className="chart-tooltip-dot" style={{ background: r.color }} />
            <span style={{ flex: 1 }}>{r.label}:</span>
            <span style={{ fontWeight: 600 }}>{val}</span>
          </div>
        )
      })}
    </div>
  )
}

// ---- Legend 组件 ----

interface DataChartLegendProps {
  checkedMetrics: string[]
  checkedRates: string[]
}

export const DataChartLegend: React.FC<DataChartLegendProps> = ({
  checkedMetrics,
  checkedRates,
}) => {
  const activeBars = checkedMetrics.filter((k) => k in BAR_COLORS)
  const activeRates = checkedRates.filter((k) => k in LINE_COLORS)

  const items: React.ReactNode[] = []

  activeBars.forEach((key) => {
    const color = BAR_COLORS[key]
    const label = METRIC_LABELS[key] || key
    items.push(
      <span key={key} className="chart-legend-item">
        <span className="chart-legend-dot" style={{ background: color }} />
        {label}
      </span>
    )
  })

  activeRates.forEach((key) => {
    const color = LINE_COLORS[key]
    const label = RATE_LABELS[key] || key
    items.push(
      <span key={key} className="chart-legend-item">
        <span
          className="chart-legend-dot"
          style={{ background: color, borderRadius: '50%' }}
        />
        {label}
      </span>
    )
  })

  if (items.length === 0) {
    items.push(
      <span key="empty" className="chart-legend-item" style={{ color: 'var(--text-secondary)' }}>
        未选择任何指标，请勾选
      </span>
    )
  }

  return <div className="chart-legend">{items}</div>
}

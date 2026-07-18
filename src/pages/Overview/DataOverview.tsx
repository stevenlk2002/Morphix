import '../../pages/prototype.css'

interface Gauge {
  percent: number
  delta: number
}

interface ChartPoint {
  date: string
  total: number
  bot: number
}

const SESSION_GAUGE: Gauge = { percent: 88.9, delta: 2.3 }
const MESSAGE_GAUGE: Gauge = { percent: 84.6, delta: -1.1 }

const CHART_DATA: ChartPoint[] = [
  { date: '07-12', total: 142, bot: 118 },
  { date: '07-13', total: 158, bot: 131 },
  { date: '07-14', total: 151, bot: 124 },
  { date: '07-15', total: 173, bot: 149 },
  { date: '07-16', total: 189, bot: 166 },
  { date: '07-17', total: 181, bot: 158 },
  { date: '07-18', total: 207, bot: 184 },
]

const PANELS = [
  { label: '托管会话总数', value: '1,243', delta: '+5.2%' },
  { label: '机器人处理消息', value: '12,860', delta: '+3.1%' },
  { label: '人工接管次数', value: '186', delta: '-1.4%' },
  { label: '平均响应时长', value: '1.8s', delta: '-0.3s' },
]

function Donut({ percent, color, label }: { percent: number; color: string; label: string }) {
  const r = 34
  const c = 2 * Math.PI * r
  const offset = c * (1 - percent / 100)
  return (
    <div className="proto-card" style={{ textAlign: 'center' }}>
      <svg viewBox="0 0 90 90" width="110" height="110">
        <circle cx="45" cy="45" r={r} fill="none" stroke="var(--border-light)" strokeWidth="8" />
        <circle
          cx="45"
          cy="45"
          r={r}
          fill="none"
          stroke={color}
          strokeWidth="8"
          strokeLinecap="round"
          strokeDasharray={c}
          strokeDashoffset={offset}
          transform="rotate(-90 45 45)"
        />
        <text x="45" y="44" textAnchor="middle" fontSize="16" fontWeight="700">
          {percent}%
        </text>
        <text x="45" y="60" textAnchor="middle" fontSize="9" fill="var(--text-secondary)">
          {label}
        </text>
      </svg>
    </div>
  )
}

function MiniChart() {
  const w = 600
  const h = 200
  const padL = 36
  const padR = 12
  const padT = 12
  const padB = 24
  const plotW = w - padL - padR
  const plotH = h - padT - padB
  const max = Math.max(...CHART_DATA.flatMap((d) => [d.total, d.bot])) * 1.1
  const x = (i: number) => padL + (plotW * i) / (CHART_DATA.length - 1)
  const y = (v: number) => padT + plotH - (v / max) * plotH

  const series = [
    { key: 'total' as const, color: 'var(--primary)' },
    { key: 'bot' as const, color: 'var(--purple)' },
  ]

  return (
    <div className="proto-card">
      <div className="proto-section-title">近七天会话趋势</div>
      <svg width="100%" height={h} viewBox={`0 0 ${w} ${h}`}>
        {series.map((s) => {
          const points = CHART_DATA.map((d, i) => ({ x: x(i), y: y(d[s.key]) }))
          const line = points
            .map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x.toFixed(1)},${p.y.toFixed(1)}`)
            .join(' ')
          return (
            <path key={s.key} d={line} fill="none" stroke={s.color} strokeWidth="2.5" />
          )
        })}
        {CHART_DATA.map((d, i) => (
          <text key={i} x={x(i)} y={h - 8} textAnchor="middle" fontSize="9" fill="var(--text-tertiary)">
            {d.date}
          </text>
        ))}
      </svg>
      <div style={{ display: 'flex', gap: 16, marginTop: 8 }}>
        <span className="proto-pill" style={{ background: 'var(--primary-light)', color: 'var(--primary)' }}>
          新增会话
        </span>
        <span className="proto-pill" style={{ background: 'var(--purple-bg)', color: 'var(--purple)' }}>
          机器人处理
        </span>
      </div>
    </div>
  )
}

export default function DataOverviewPage() {
  return (
    <div className="proto-page">
      <div className="page-header">
        <div>
          <h2 className="page-title">数据概览</h2>
          <p className="page-subtitle">机器人托管效果与运营核心指标</p>
        </div>
      </div>

      <div className="proto-donut-row">
        <Donut percent={SESSION_GAUGE.percent} color="var(--primary)" label="机器人处理会话占比" />
        <Donut percent={MESSAGE_GAUGE.percent} color="var(--purple)" label="机器人处理消息占比" />
      </div>

      <MiniChart />

      <div className="proto-grid">
        {PANELS.map((p) => (
          <div key={p.label} className="proto-card">
            <div className="proto-stat">
              <span className="proto-stat-value">{p.value}</span>
              <span className="proto-stat-label">{p.label}</span>
              <span className={p.delta.startsWith('-') ? 'proto-badge-danger proto-badge' : 'proto-badge-success proto-badge'}>
                {p.delta}
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

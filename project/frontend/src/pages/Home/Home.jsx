import { useEffect, useRef, useState } from 'react'
import { Activity, AlertCircle } from 'lucide-react'
import { dashboardApi } from '../../utils/api'
import './Home.css'

/* ------------------------------------------------------------------ *
 * 静态样例数据（与后端 dashboard 结构对齐，便于后续切换为真实 API）
 * ------------------------------------------------------------------ */
/* 数据总览图表 - 两个 Tab，每个 Tab 双系列（总量 + 机器人处理量） */
const CHART_TABS = [
  {
    key: 'sessions',
    label: '会话数',
    tooltip:
      '新增会话数：所选日期范围内首次产生客户消息的会话数量；机器人处理会话数：由机器人完成处理的托管会话数量。',
    series: [
      { name: '新增会话数', color: 'var(--primary)', key: 'total' },
      { name: '机器人处理会话数', color: 'var(--purple)', key: 'bot' },
    ],
  },
  {
    key: 'messages',
    label: '消息数',
    tooltip:
      '新增消息数：所选日期范围内新增的客户与客服消息总数；机器人处理消息数：由机器人直接回复的消息数量。',
    series: [
      { name: '新增消息数', color: 'var(--primary)', key: 'total' },
      { name: '机器人处理消息数', color: 'var(--purple)', key: 'bot' },
    ],
  },
]

const CHART_DATA = {
  sessions: [
    { date: '07-12', total: 142, bot: 118 }, { date: '07-13', total: 158, bot: 131 },
    { date: '07-14', total: 151, bot: 124 }, { date: '07-15', total: 173, bot: 149 },
    { date: '07-16', total: 189, bot: 166 }, { date: '07-17', total: 181, bot: 158 },
    { date: '07-18', total: 207, bot: 184 },
  ],
  messages: [
    { date: '07-12', total: 2100, bot: 1680 }, { date: '07-13', total: 2380, bot: 1922 },
    { date: '07-14', total: 2250, bot: 1796 }, { date: '07-15', total: 2610, bot: 2121 },
    { date: '07-16', total: 2890, bot: 2394 }, { date: '07-17', total: 2740, bot: 2256 },
    { date: '07-18', total: 3284, bot: 2779 },
  ],
}

const dashboardSample = {
  /* 数据总览双仪表盘 */
  gauges: {
    sessionRate: { percent: 88.9, delta: 2.3 },
    messageRate: { percent: 84.6, delta: -1.1 },
  },
  /* 我的机器人 */
  robots: {
    activeTemplates: 2,
    created: 8,
    online: 5,
    hostedSessions: 1243,
    expireAt: '--',
  },
  /* 我的渠道账号 */
  channels: {
    seatsLeft: 0,
    added: 4,
    online: 3,
    onlineSessions: 156,
    distribution: [
      { name: '企微', count: 2, color: 'var(--primary)' },
      { name: '个微', count: 1, color: 'var(--purple)' },
      { name: 'WhatsApp', count: 1, color: 'var(--teal)' },
      { name: '企业WhatsApp', count: 0, color: 'var(--warning)' },
    ],
    expireAt: '离线 -',
  },
  /* 未读消息 / 通知 */
  unread: [
    { id: 'u1', type: 'warning', text: '可用额度不足预警，请及时充值以免影响服务', time: '10分钟前' },
    { id: 'u2', type: 'info', text: '「订单查询机器人」已完成最新一轮训练同步', time: '1小时前' },
    { id: 'u3', type: 'info', text: '渠道账号「微信客服」已成功上线', time: '3小时前' },
    { id: 'u4', type: 'info', text: '「会员关怀助手」模板已更新至 v2.1', time: '昨天 18:20' },
  ],
}

/* ------------------------------------------------------------------ *
 * 环形进度（Donut）
 * ------------------------------------------------------------------ */
function Donut({ percent, color, label }) {
  const r = 34
  const c = 2 * Math.PI * r
  const offset = c * (1 - percent / 100)
  return (
    <div className="donut-wrap">
      <svg viewBox="0 0 90 90" width="90" height="90">
        <circle cx="45" cy="45" r={r} fill="none" stroke="var(--border-light)" strokeWidth="8" />
        <circle
          cx="45" cy="45" r={r} fill="none"
          stroke={color} strokeWidth="8" strokeLinecap="round"
          strokeDasharray={c} strokeDashoffset={offset}
          transform="rotate(-90 45 45)"
        />
        <text x="45" y="42" textAnchor="middle" className="donut-value">{percent}%</text>
        <text x="45" y="58" textAnchor="middle" className="donut-label">{label}</text>
      </svg>
    </div>
  )
}

/* ------------------------------------------------------------------ *
 * 自绘折线图（SVG 平滑曲线 + 十字准星 tooltip）
 * ------------------------------------------------------------------ */
function LineChart({ data, series, height = 280 }) {
  const ref = useRef(null)
  const [hover, setHover] = useState(null)
  const [size, setSize] = useState({ w: 600, h: height })

  useEffect(() => {
    const el = ref.current
    if (!el) return
    const ro = new ResizeObserver((entries) => {
      const w = entries[0].contentRect.width
      if (w > 0) setSize({ w, h: height })
    })
    ro.observe(el)
    return () => ro.disconnect()
  }, [height])

  const padL = 44
  const padR = 16
  const padT = 16
  const padB = 28
  const w = size.w
  const h = size.h
  const plotW = w - padL - padR
  const plotH = h - padT - padB
  const max = Math.max(...data.flatMap((d) => series.map((s) => d[s.key]))) * 1.1
  const min = 0

  const x = (i) => padL + (plotW * i) / (data.length - 1)
  const y = (v) => padT + plotH - ((v - min) / (max - min)) * plotH

  const gridLines = 4
  const onMove = (e) => {
    const rect = ref.current.getBoundingClientRect()
    const mx = e.clientX - rect.left
    let idx = Math.round(((mx - padL) / plotW) * (data.length - 1))
    idx = Math.max(0, Math.min(data.length - 1, idx))
    setHover({ idx, cx: x(idx) })
  }

  return (
    <div
      className="chart-container"
      ref={ref}
      style={{ height }}
      onMouseMove={onMove}
      onMouseLeave={() => setHover(null)}
    >
      <svg width="100%" height={h}>
        {Array.from({ length: gridLines + 1 }).map((_, i) => {
          const gy = padT + (plotH * i) / gridLines
          const val = Math.round(max - ((max - min) * i) / gridLines)
          return (
            <g key={i}>
              <line className="chart-grid" x1={padL} y1={gy} x2={w - padR} y2={gy} />
              <text className="chart-axis-text" x={padL - 8} y={gy + 4} textAnchor="end">{val}</text>
            </g>
          )
        })}
        {data.map((d, i) => (
          <text key={i} className="chart-axis-text" x={x(i)} y={h - 10} textAnchor="middle">
            {d.date}
          </text>
        ))}
        {series.map((s) => {
          const points = data.map((d, i) => ({ x: x(i), y: y(d[s.key]), d }))
          const linePath = points
            .map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x.toFixed(1)},${p.y.toFixed(1)}`)
            .join(' ')
          const areaPath =
            `${linePath} L${x(data.length - 1).toFixed(1)},${(padT + plotH).toFixed(1)} ` +
            `L${x(0).toFixed(1)},${(padT + plotH).toFixed(1)} Z`
          const gid = `area-${s.key}`
          return (
            <g key={s.key}>
              <defs>
                <linearGradient id={gid} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={s.color} stopOpacity="0.16" />
                  <stop offset="100%" stopColor={s.color} stopOpacity="0" />
                </linearGradient>
              </defs>
              <path d={areaPath} fill={`url(#${gid})`} />
              <path d={linePath} fill="none" stroke={s.color} strokeWidth="2.5" />
              {points.map((p, i) => (
                <circle key={i} cx={p.x} cy={p.y} r="3" fill="#fff" stroke={s.color} strokeWidth="2" />
              ))}
            </g>
          )
        })}
        {hover && (
          <g>
            <line className="chart-crosshair" x1={hover.cx} y1={padT} x2={hover.cx} y2={padT + plotH} />
            {series.map((s) => (
              <circle
                key={s.key}
                cx={hover.cx}
                cy={y(data[hover.idx][s.key])}
                r="5"
                fill={s.color}
                stroke="#fff"
                strokeWidth="2"
              />
            ))}
          </g>
        )}
      </svg>

      {hover && (
        <div
          className="chart-tooltip"
          style={{
            display: 'block',
            left: Math.min(Math.max(hover.cx + 12, 0), w - 190),
            top: 4,
          }}
        >
          <div className="chart-tooltip-date">{data[hover.idx].date}</div>
          {series.map((s) => (
            <div className="chart-tooltip-row" key={s.key}>
              <span className="chart-tooltip-dot" style={{ background: s.color }} />
              <span style={{ color: 'var(--text-secondary)' }}>{s.name}</span>
              <span style={{ marginLeft: 'auto', fontWeight: 600 }}>
                {data[hover.idx][s.key].toLocaleString()}{s.suffix || ''}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

/* ------------------------------------------------------------------ *
 * 卡片组件
 * ------------------------------------------------------------------ */
function GaugeCard({ title, percent, delta }) {
  const up = delta >= 0
  return (
    <div className="gauge-card">
      <Donut percent={Math.round(percent * 10) / 10} color="var(--primary)" label={title} />
      <div className="gauge-meta">
        <div className="gauge-percent">{percent}%</div>
        <div className={`gauge-delta ${up ? 'up' : 'down'}`}>
          {up ? '▲' : '▼'} {Math.abs(delta)}%
          <span className="gauge-delta-label">环比上一周期</span>
        </div>
      </div>
    </div>
  )
}

function MyRobotsCard({ r }) {
  return (
    <div className="card mini-card">
      <div className="card-header">
        <span className="card-title">我的机器人</span>
        <a href="#" className="card-link">管理 →</a>
      </div>
      <div className="card-body">
        <div className="stat-row">
          <div className="stat-block">
            <div className="stat-value">{r.activeTemplates}</div>
            <div className="stat-label">活跃模板</div>
          </div>
          <div className="stat-block">
            <div className="stat-value">{r.created}</div>
            <div className="stat-label">我的创建</div>
          </div>
          <div className="stat-block">
            <div className="stat-value">{r.online}</div>
            <div className="stat-label">在线</div>
          </div>
          <div className="stat-block">
            <div className="stat-value">{r.hostedSessions.toLocaleString()}</div>
            <div className="stat-label">托管会话</div>
          </div>
        </div>
        <div className="card-footnote">有效期：{r.expireAt}</div>
      </div>
    </div>
  )
}

function MyChannelsCard({ c }) {
  return (
    <div className="card mini-card">
      <div className="card-header">
        <span className="card-title">我的渠道账号</span>
        <a href="#" className="card-link">配置 →</a>
      </div>
      <div className="card-body">
        <div className="stat-row">
          <div className="stat-block">
            <div className="stat-value">{c.seatsLeft}</div>
            <div className="stat-label">可用坐席</div>
          </div>
          <div className="stat-block">
            <div className="stat-value">{c.added}</div>
            <div className="stat-label">添加账号</div>
          </div>
          <div className="stat-block">
            <div className="stat-value">{c.online}</div>
            <div className="stat-label">在线</div>
          </div>
          <div className="stat-block">
            <div className="stat-value">{c.onlineSessions}</div>
            <div className="stat-label">在线会话</div>
          </div>
        </div>
        <div className="channel-dist">
          {c.distribution.map((d) => (
            <div className="channel-dist-item" key={d.name}>
              <span className="channel-dist-dot" style={{ background: d.color }} />
              {d.name}
              <span className="channel-dist-count">{d.count}</span>
            </div>
          ))}
        </div>
        <div className="card-footnote">有效期：{c.expireAt}</div>
      </div>
    </div>
  )
}

function UnreadCard({ list }) {
  return (
    <div className="card mini-card">
      <div className="card-header">
        <span className="card-title">未读消息 / 通知</span>
        <a href="#" className="card-link">全部已读</a>
      </div>
      <div className="card-body">
        <div className="unread-list">
          {list.map((u) => (
            <div className="unread-item" key={u.id}>
              <span className={`unread-dot ${u.type}`} />
              <div className="unread-text">
                <div className="unread-desc">{u.text}</div>
                <div className="unread-time">{u.time}</div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

export default function HomePage() {
  const [data, setData] = useState(dashboardSample)
  const [tab, setTab] = useState('sessions')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const loadDashboard = async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await dashboardApi.get()
      setData(res)
    } catch (err) {
      setError('仪表盘数据加载失败，请稍后重试')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadDashboard()
  }, [])

  if (loading) {
    return (
      <div className="page-loading">
        <Activity className="spinner" size={32} />
        <p>加载中...</p>
      </div>
    )
  }

  if (error) {
    return (
      <div className="page-loading">
        <AlertCircle size={32} className="error-icon" />
        <p>{error}</p>
        <button className="retry-btn" onClick={loadDashboard}>重试</button>
      </div>
    )
  }

  const activeTab = CHART_TABS.find((t) => t.key === tab)
  const series = activeTab.series
  const chartData = CHART_DATA[tab]

  // gauges 后端契约为对象 { sessionRate, messageRate }，兜底避免结构偏差导致整页白屏
  const sessionGauge = data?.gauges?.sessionRate ?? { percent: 0, delta: 0 }
  const messageGauge = data?.gauges?.messageRate ?? { percent: 0, delta: 0 }

  return (
    <div className="home-page">
      {/* 数据总览 */}
      <div className="card">
        <div className="card-header">
          <span className="card-title">
            数据总览<span className="card-subtitle">（近七天）</span>
          </span>
          <a href="#" className="card-link">查看更多 →</a>
        </div>
        <div className="card-body overview-body">
          <div className="gauge-row">
            <GaugeCard
              title="机器人处理会话占比"
              percent={sessionGauge.percent}
              delta={sessionGauge.delta}
            />
            <GaugeCard
              title="机器人处理消息占比"
              percent={messageGauge.percent}
              delta={messageGauge.delta}
            />
          </div>

          <div className="chart-card">
            <div className="chart-tabs">
              {CHART_TABS.map((t) => (
                <button
                  key={t.key}
                  className={`chart-tab ${tab === t.key ? 'active' : ''}`}
                  onClick={() => setTab(t.key)}
                >
                  {t.label}
                </button>
              ))}
            </div>
            <LineChart data={chartData} series={series} height={280} />
            <div className="chart-legend">
              {series.map((s) => (
                <div className="chart-legend-item" key={s.key}>
                  <span className="chart-legend-dot" style={{ background: s.color }} />
                  {s.name}
                </div>
              ))}
            </div>
            <div className="chart-tooltip-desc">{activeTab.tooltip}</div>
          </div>
        </div>
      </div>

      <div className="home-row">
        <MyRobotsCard r={data.robots} />
        <MyChannelsCard c={data.channels} />
        <UnreadCard list={data.unread} />
      </div>
    </div>
  )
}

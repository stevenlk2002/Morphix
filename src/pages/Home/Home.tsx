import { useEffect, useRef, useState, type CSSProperties, type ReactNode } from 'react'
import { FileText, Bot, Check, MessageSquare, User, HelpCircle } from 'lucide-react'
import { Link, useNavigate } from 'react-router-dom'
import './Home.css'
import { dashboardApi } from '../../api/client'
import { dataPanelApi } from '../../api/data_panel'

interface Gauge {
  percent: number
  delta: number
}

interface DashboardData {
  gauges?: { sessionRate?: Gauge; messageRate?: Gauge }
  robots?: {
    activeTemplates: number
    created: number
    online: number
    hostedSessions: number
    expireAt: string
  }
  channels?: {
    seatsLeft: number
    added: number
    online: number
    onlineSessions: number
    distribution:
      | Array<{ name: string; count: number; color?: string }>
      | Record<string, number | string>
      | unknown
    expireAt: string
  }
  unread?: Array<{
    id: string
    type?: string
    text?: string
    title?: string
    desc?: string
    time?: string
  }>
}

interface ChartSeries {
  name: string
  color: string
  key: string
  suffix?: string
}

interface ChartPoint {
  date: string
  total: number
  bot: number
}

interface ChartDef {
  label: string
  text: string
}

interface ChartTab {
  key: string
  label: string
  /** 原型「?」气泡中的指标定义（顺序与 series 一一对应）。 */
  defs: ChartDef[]
  series: ChartSeries[]
}

const CHART_TABS: ChartTab[] = [
  {
    key: 'sessions',
    label: '会话数',
    defs: [
      {
        label: '新增会话数：',
        text: '近七天新出现在Morphix平台上的会话数，包含单聊、群聊；可能是新增好友的会话，也可能是添加渠道账号前已存在，添加后首次收到新消息的会话。',
      },
      {
        label: '机器人处理会话数：',
        text: '近七天机器人曾处理过其中客户消息的会话数，包含单聊、群聊。请注意，处理指机器人思考过用户发送的消息，可能思考后选择不回复或转人工。',
      },
    ],
    series: [
      { name: '新增会话数', color: 'var(--primary)', key: 'total' },
      { name: '机器人处理会话数', color: 'var(--purple)', key: 'bot' },
    ],
  },
  {
    key: 'messages',
    label: '消息数',
    defs: [
      {
        label: '新增消息数：',
        text: '近七天Morphix平台在各个托管会话中收到的外部消息数；会排除掉系统消息和企微内部联系人发送的消息。',
      },
      {
        label: '机器人处理消息数：',
        text: '近七天机器人曾处理过的客户消息数。请注意，处理指机器人思考过用户发送的消息，可能思考后选择不回复或转人工。',
      },
    ],
    series: [
      { name: '新增消息数', color: 'var(--primary)', key: 'total' },
      { name: '机器人处理消息数', color: 'var(--purple)', key: 'bot' },
    ],
  },
]

const CHART_DATA: Record<string, ChartPoint[]> = {
  sessions: [
    { date: '07-04', total: 0, bot: 0 }, { date: '07-05', total: 1, bot: 0 },
    { date: '07-06', total: 0, bot: 0 }, { date: '07-07', total: 0, bot: 0 },
    { date: '07-08', total: 0, bot: 0 }, { date: '07-09', total: 3, bot: 1 },
    { date: '07-10', total: 2, bot: 0 },
  ],
  messages: [
    { date: '07-04', total: 0, bot: 0 }, { date: '07-05', total: 0, bot: 0 },
    { date: '07-06', total: 0, bot: 0 }, { date: '07-07', total: 0, bot: 0 },
    { date: '07-08', total: 0, bot: 0 }, { date: '07-09', total: 4, bot: 2 },
    { date: '07-10', total: 0, bot: 0 },
  ],
}

const dashboardSample: DashboardData = {
  gauges: {
    // 保留有意义的 mock 百分比，避免渲染 0% 让界面显得坏掉。
    sessionRate: { percent: 88.9, delta: 2.3 },
    messageRate: { percent: 84.6, delta: -1.1 },
  },
  robots: {
    activeTemplates: 0,
    created: 2,
    online: 1,
    hostedSessions: 3,
    expireAt: '--',
  },
  channels: {
    seatsLeft: 0,
    added: 1,
    online: 1,
    onlineSessions: 174,
    distribution: [
      { name: '企微', count: 1 },
      { name: '个微', count: 0 },
      { name: 'WhatsApp', count: 0 },
      { name: '企业WhatsApp', count: 0 },
    ],
    expireAt: '2026-08-09',
  },
  unread: [
    {
      id: 'u1',
      type: 'warning',
      title: '可用额度不足预警',
      desc: '账户的可用额度仅剩余0.00元，为避免影响您的正常使用，请及时进入资源管理进行充值。',
      time: '2026-07-10 10:20:02',
    },
    {
      id: 'u2',
      title: '[竹绿-健康]已完成同步',
      desc: '[竹绿-健康]已于2026-07-09 22:43:43完成同步，您现在可以开始使用。',
      time: '2026-07-09 22:43:43',
    },
    {
      id: 'u3',
      title: '[竹绿-健康]已开始同步',
      desc: '[竹绿-健康]已于2026-07-09 22:41:39开始同步，预计将在20分钟内完成。',
      time: '2026-07-09 22:41:45',
    },
    {
      id: 'u4',
      title: '[竹绿-健康]已上线',
      desc: '[竹绿-健康]已于2026-07-09 22:41:39上线，您可以接收到该账号的消息。',
      time: '2026-07-09 22:41:40',
    },
  ],
}

// 指标定义文案（原型 gauge 标题旁「?」气泡，逐字对齐 index.html 7081 / 7098）
const SESSION_RATE_HELP = '机器人会话处理率=机器人处理会话数/有客户消息的托管会话数'
const MESSAGE_RATE_HELP = '机器人消息处理率=机器人处理消息数/总消息数'

// ---- 数据映射与平滑曲线工具 ----
type Dict = Record<string, unknown>

/** 安全转为数字，非有限值回退 fallback。 */
function numOr(v: unknown, fallback = 0): number {
  const n = typeof v === 'string' ? Number(v) : (v as number)
  return typeof n === 'number' && Number.isFinite(n) ? n : fallback
}

/** 安全转为字符串，null/undefined 回退 fallback。 */
function strOr(v: unknown, fallback = '--'): string {
  return v == null ? fallback : String(v)
}

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

/** 计算图表 tooltip 的 top：跟随鼠标 y，并 clamp 防止溢出容器底部。 */
function chartTipTop(my: number, h: number, rows: number): number {
  const tipH = 56 + 22 * rows
  let top = my + 12
  if (top + tipH > h) top = Math.max(h - tipH - 4, 4)
  return Math.max(top, 4)
}

/** 把后端 /api/dashboard 响应映射为前端 DashboardData（兼容字符串型数值与缺字段）。 */
function mapDashboard(raw: unknown): DashboardData {
  const d = (raw ?? {}) as Dict
  const gauges = (d.gauges ?? {}) as Dict
  const sr = (gauges.sessionRate ?? {}) as Dict
  const mr = (gauges.messageRate ?? {}) as Dict
  const robots = (d.robots ?? {}) as Dict
  const channels = (d.channels ?? {}) as Dict
  const rawUnread = Array.isArray(d.unread) ? (d.unread as Array<Dict>) : []
  return {
    gauges: {
      sessionRate: { percent: numOr(sr.percent), delta: numOr(sr.delta) },
      messageRate: { percent: numOr(mr.percent), delta: numOr(mr.delta) },
    },
    robots: {
      activeTemplates: numOr(robots.activeTemplates),
      created: numOr(robots.created),
      online: numOr(robots.online),
      hostedSessions: numOr(robots.hostedSessions),
      expireAt: strOr(robots.expireAt),
    },
    channels: {
      seatsLeft: numOr(channels.seatsLeft),
      added: numOr(channels.added),
      online: numOr(channels.online),
      onlineSessions: numOr(channels.onlineSessions),
      distribution: (channels.distribution ?? []) as
        | Array<{ name: string; count: number; color?: string }>
        | Record<string, number | string>
        | unknown,
      expireAt: strOr(channels.expireAt),
    },
    unread: rawUnread.map((u) => ({
      id: strOr(u.id, ''),
      type: typeof u.type === 'string' ? u.type : undefined,
      title: typeof u.title === 'string' ? u.title : undefined,
      desc:
        typeof u.desc === 'string'
          ? u.desc
          : typeof u.content === 'string'
            ? u.content
            : undefined,
      time: typeof u.time === 'string' ? u.time : undefined,
    })),
  }
}

/** 把后端 /api/data-panel/metrics 的 daily 序列映射为前端 CHART_DATA 结构。 */
function mapMetricsToChart(daily: unknown): Record<string, ChartPoint[]> {
  const arr = Array.isArray(daily) ? (daily as Array<Dict>) : []
  if (arr.length === 0) return CHART_DATA
  const toPoint = (
    getTotal: (d: Dict) => unknown,
    getBot: (d: Dict) => unknown,
  ) => (d: Dict): ChartPoint => {
    const full = typeof d.date === 'string' ? d.date : ''
    const date = full.length >= 10 ? full.slice(5) : full
    return { date, total: numOr(getTotal(d)), bot: numOr(getBot(d)) }
  }
  return {
    sessions: arr.map(toPoint((d) => d.new_sessions, (d) => d.bot_processed_sessions)),
    messages: arr.map(toPoint((d) => d.total_messages, (d) => d.bot_processed_messages)),
  }
}

/** 计算「近七天」日期范围（含今天），格式 YYYY-MM-DD。 */
function last7Days(): { start: string; end: string } {
  const end = new Date()
  const start = new Date()
  start.setDate(end.getDate() - 6)
  const fmt = (dt: Date) =>
    `${dt.getFullYear()}-${String(dt.getMonth() + 1).padStart(2, '0')}-${String(
      dt.getDate(),
    ).padStart(2, '0')}`
  return { start: fmt(start), end: fmt(end) }
}

function Donut({ percent, color, label }: { percent: number; color: string; label?: string }) {
  const r = 34
  const c = 2 * Math.PI * r
  const offset = c * (1 - percent / 100)
  return (
    <div className="donut-wrap">
      <svg viewBox="0 0 90 90" width="90" height="90">
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
        <text x="45" y="42" textAnchor="middle" className="donut-value">
          {percent}%
        </text>
        {label ? (
          <text x="45" y="58" textAnchor="middle" className="donut-label">
            {label}
          </text>
        ) : null}
      </svg>
    </div>
  )
}

function LineChart({ data, series, height = 280 }: { data: ChartPoint[]; series: ChartSeries[]; height?: number }) {
  const ref = useRef<HTMLDivElement>(null)
  const [hover, setHover] = useState<{ idx: number; cx: number; my: number } | null>(null)
  const [size, setSize] = useState<{ w: number; h: number }>({ w: 600, h: height })

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
  const max = Math.max(...data.flatMap((d) => series.map((s) => d[s.key as keyof ChartPoint] as number))) * 1.1
  const min = 0

  const x = (i: number) => padL + (plotW * i) / (data.length - 1)
  const y = (v: number) => padT + plotH - ((v - min) / (max - min)) * plotH

  const gridLines = 4
  const onMove = (e: React.MouseEvent<HTMLDivElement>) => {
    const rect = ref.current?.getBoundingClientRect()
    if (!rect) return
    const mx = e.clientX - rect.left
    const my = e.clientY - rect.top
    let idx = Math.round(((mx - padL) / plotW) * (data.length - 1))
    idx = Math.max(0, Math.min(data.length - 1, idx))
    setHover({ idx, cx: x(idx), my })
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
              <text className="chart-axis-text" x={padL - 8} y={gy + 4} textAnchor="end">
                {val}
              </text>
            </g>
          )
        })}
        {data.map((d, i) => (
          <text key={i} className="chart-axis-text" x={x(i)} y={h - 10} textAnchor="middle">
            {d.date}
          </text>
        ))}
        {series.map((s) => {
          const points = data.map((d, i) => ({
            x: x(i),
            y: y(d[s.key as keyof ChartPoint] as number),
            d,
          }))
          const linePath = smoothPath(points.map((p) => ({ x: p.x, y: p.y })))
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
                cy={y(data[hover.idx][s.key as keyof ChartPoint] as number)}
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
            left: Math.min(Math.max(hover.cx + 12, 0), w - 160),
            top: chartTipTop(hover.my, h, series.length),
          }}
        >
          <div className="chart-tooltip-date">{data[hover.idx].date}</div>
          {series.map((s) => (
            <div className="chart-tooltip-row" key={s.key}>
              <span className="chart-tooltip-dot" style={{ background: s.color }} />
              <span style={{ color: 'var(--text-secondary)' }}>{s.name}</span>
              <span style={{ marginLeft: 'auto', fontWeight: 600 }}>
                {(data[hover.idx][s.key as keyof ChartPoint] as number).toLocaleString()}
                {s.suffix || ''}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function GaugeCard({
  title,
  percent,
  delta,
  color,
  help,
}: {
  title: string
  percent: number
  delta: number
  color: string
  help?: string
}) {
  const up = delta >= 0
  return (
    <div className="gauge-card" style={{ '--gauge-color': color } as unknown as CSSProperties}>
      <div className="gauge-card-title">
        <span>{title}</span>
        {help ? (
          <span className="gauge-help tab-tooltip">
            <span className="tab-tooltip-bubble gauge-tip-bubble">{help}</span>
            <HelpCircle size={14} />
          </span>
        ) : null}
      </div>
      <Donut percent={Math.round(percent * 10) / 10} color={color} />
      <div className="gauge-card-change">
        较昨日 <span className={up ? 'up' : 'down'}>{up ? '▲' : '▼'} {Math.abs(delta)}%</span>
      </div>
    </div>
  )
}

// 归一化渠道分布数据：兼容后端返回的「数组」与「对象」两种形态。
// 数组元素可能缺少 color 字段；对象形态为 { name: count } 映射。
const DIST_PALETTE = [
  'var(--primary)',
  'var(--purple)',
  'var(--teal)',
  'var(--warning)',
  'var(--success)',
]

function normalizeDistribution(
  d: unknown,
): Array<{ name: string; count: number; color?: string }> {
  if (!d) return []
  // 数组形态：原样使用（元素含 name/count/color，color 可选）。
  if (Array.isArray(d)) {
    return d.map((item) => {
      const it = (item ?? {}) as { name?: unknown; count?: unknown; color?: string }
      return {
        name: String(it.name ?? ''),
        count: Number(it.count) || 0,
        color: it.color,
      }
    })
  }
  // 对象形态：{ 渠道名: 数量 } 映射，按序分配调色板颜色。
  if (typeof d === 'object') {
    return Object.entries(d as Record<string, unknown>).map(
      ([name, count], i) => ({
        name,
        count: Number(count) || 0,
        color: DIST_PALETTE[i % DIST_PALETTE.length],
      }),
    )
  }
  return []
}

function MiniStat({
  icon,
  title,
  value,
  iconStyle,
}: {
  icon: ReactNode
  title: string
  value: ReactNode
  iconStyle?: CSSProperties
}) {
  return (
    <div className="mini-stat">
      <div className="mini-stat-icon" style={iconStyle}>
        {icon}
      </div>
      <div className="mini-stat-info">
        <div className="mini-stat-title">{title}</div>
        <div className="mini-stat-value">{value}</div>
      </div>
    </div>
  )
}

function MyRobotsCard({
  r,
  onManage,
}: {
  r: NonNullable<DashboardData['robots']>
  onManage: () => void
}) {
  return (
    <div className="card home-bot">
      <div className="card-header">
        <span className="card-title">我的机器人</span>
        <button type="button" className="btn btn-ghost btn-sm" onClick={onManage}>
          前往管理
        </button>
      </div>
      <div className="card-body robots-body">
        <div className="mini-stat-grid">
          <MiniStat icon={<FileText size={20} />} title="生效中机器人模板" value={r.activeTemplates} />
          <MiniStat
            icon={<Bot size={20} />}
            title="已创建机器人"
            value={r.created}
            iconStyle={{ background: '#eaf2f9', color: '#6a9bcc' }}
          />
          <MiniStat
            icon={<Check size={20} />}
            title="已上线机器人"
            value={r.online}
            iconStyle={{ background: '#eef6ea', color: '#7fb069' }}
          />
          <MiniStat
            icon={<MessageSquare size={20} />}
            title="总托管会话数"
            value={r.hostedSessions}
            iconStyle={{ background: '#fdf3e3', color: '#e8a649' }}
          />
        </div>
        <div className="card-footnote">最近过期时间：{r.expireAt}</div>
      </div>
    </div>
  )
}

function MyChannelsCard({
  c,
  onManage,
}: {
  c: NonNullable<DashboardData['channels']>
  onManage: () => void
}) {
  const distribution = normalizeDistribution(c.distribution)
  const maxCount = distribution.reduce((m, d) => Math.max(m, d.count), 0) || 1
  return (
    <div className="card home-channel">
      <div className="card-header">
        <span className="card-title">我的渠道账号</span>
        <span className="badge badge-default">剩余席位 {c.seatsLeft}</span>
        <button type="button" className="btn btn-ghost btn-sm" onClick={onManage}>
          前往管理
        </button>
      </div>
      <div className="card-body channel-body">
        <div className="channel-main">
          <div className="mini-stat-grid channel-mini-grid">
            <MiniStat
              icon={<User size={20} />}
              title="已添加渠道账号"
              value={c.added}
              iconStyle={{ background: '#f1ebfa', color: '#a88bd8' }}
            />
            <MiniStat
              icon={<MessageSquare size={20} />}
              title="在线渠道账号"
              value={c.online}
              iconStyle={{ background: '#e6f4f1', color: '#5fb5a6' }}
            />
            <MiniStat
              icon={<MessageSquare size={20} />}
              title="总在线会话数"
              value={c.onlineSessions}
              iconStyle={{ background: '#f9e8e8', color: '#d76b6b' }}
            />
          </div>
          <div className="channel-footnote">
            <span>最近过期时间 {c.expireAt}</span>
            <span>离线 -</span>
          </div>
        </div>
        <div className="dist-panel">
          <div className="dist-panel-title">渠道账号分布</div>
          {distribution.map((d) => (
            <div className="dist-item" key={d.name}>
              <span className="dist-label">{d.name}</span>
              <div className="dist-track">
                <div
                  className="dist-fill"
                  style={{
                    width: `${Math.max(0, Math.min(100, (d.count / maxCount) * 100))}%`,
                    background: '#3b82f6',
                  }}
                />
              </div>
              <span className="dist-value">{d.count}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

function UnreadCard({
  list,
  onViewAll,
}: {
  list: NonNullable<DashboardData['unread']>
  onViewAll: () => void
}) {
  return (
    <div className="card home-unread">
      <div className="card-header">
        <span className="card-title">未读消息</span>
        <button type="button" className="btn btn-ghost btn-sm" onClick={onViewAll}>
          查看全部
        </button>
      </div>
      <div className="card-body unread-body">
        {list.map((u, i) => {
          const isWarning = u.type === 'warning'
          const isLast = i === list.length - 1
          return (
            <div className={`unread-row${isLast ? ' is-last' : ''}`} key={u.id}>
              <div className={`unread-title${isWarning ? ' warning' : ''}`}>{u.title ?? u.text}</div>
              <div className="unread-desc">{u.desc}</div>
              <div className="unread-time">{u.time}</div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

const REFRESH_INTERVAL_MS = 10 * 60 * 1000

export default function HomePage() {
  const navigate = useNavigate()
  const [tab, setTab] = useState('sessions')

  // 先以静态样例作为初始 state，避免接口尚未返回时白屏；
  // 首次加载即拉取真实数据，并每 10 分钟轮询刷新（失败时保留上一次数据）。
  const [data, setData] = useState<DashboardData>(dashboardSample)
  const [chartData, setChartData] = useState<Record<string, ChartPoint[]>>(CHART_DATA)

  useEffect(() => {
    let alive = true
    const range = last7Days()

    const loadDashboard = async () => {
      try {
        const res = await dashboardApi.get()
        if (alive && res) setData(mapDashboard(res))
      } catch (err) {
        // 接口失败：保留上一次数据，不闪空。
        console.warn('[Home] /api/dashboard 刷新失败，保留上一次数据', err)
      }
    }

    const loadMetrics = async () => {
      try {
        const res = await dataPanelApi.getMetrics(range)
        if (alive && res && Array.isArray(res.daily) && res.daily.length > 0) {
          setChartData(mapMetricsToChart(res.daily))
        } else {
          // metrics 不含对应字段时保留 CHART_DATA mock，并加注释提示。
          // TODO: 后端返回结构与预期不一致时，在此确认字段映射。
          console.warn('[Home] /api/data-panel/metrics 返回为空，保留示例数据')
        }
      } catch (err) {
        console.warn('[Home] /api/data-panel/metrics 刷新失败，保留上一次数据', err)
      }
    }

    const loadAll = () => {
      void loadDashboard()
      void loadMetrics()
    }

    loadAll()
    const timer = setInterval(loadAll, REFRESH_INTERVAL_MS)
    return () => {
      alive = false
      clearInterval(timer)
    }
  }, [])

  const activeTab =
    CHART_TABS.find((t) => t.key === tab) ?? CHART_TABS[0]
  const series = activeTab.series

  const sessionGauge = data?.gauges?.sessionRate ?? { percent: 0, delta: 0 }
  const messageGauge = data?.gauges?.messageRate ?? { percent: 0, delta: 0 }

  return (
    <div className="home-page">
      <div className="home-grid">
        <div className="card home-overview">
          <div className="card-header">
            <span className="card-title">
              <span>
                数据总览<span className="card-subtitle">（近七天）</span>
              </span>
              <span
                className="tooltip"
                data-tip="该处数据每十分钟更新一次"
                style={{ color: 'var(--text-tertiary)', cursor: 'help' }}
              >
                <HelpCircle size={14} />
              </span>
            </span>
            <Link to="/overview" className="card-link">
              查看更多 →
            </Link>
          </div>
          <div className="card-body overview-body">
            <div className="overview-left">
              <div className="chart-card">
                <div className="chart-tabs">
                  {CHART_TABS.map((t) => (
                    <button
                      key={t.key}
                      type="button"
                      className={`chart-tab ${tab === t.key ? 'active' : ''}`}
                      onClick={() => setTab(t.key)}
                    >
                      {t.label}
                      <span className="tab-help tab-tooltip">
                        <span className="tab-tooltip-bubble">
                          {t.defs.map((d, i) => (
                            <div className="def-row" key={i}>
                              <span className="def-label">{d.label}</span>
                              <span className="def-text">{d.text}</span>
                            </div>
                          ))}
                        </span>
                        <HelpCircle size={14} />
                      </span>
                    </button>
                  ))}
                </div>
                <LineChart data={chartData[tab]} series={series} height={280} />
                <div className="chart-legend">
                  {series.map((s) => (
                    <div className="chart-legend-item" key={s.key}>
                      <span className="chart-legend-dot" style={{ background: s.color }} />
                      {s.name}
                    </div>
                  ))}
                </div>
              </div>
            </div>
            <div className="overview-right">
              <GaugeCard
                title="今日机器人会话处理率"
                help={SESSION_RATE_HELP}
                percent={sessionGauge.percent}
                delta={sessionGauge.delta}
                color="#3b82f6"
              />
              <GaugeCard
                title="今日机器人消息处理率"
                help={MESSAGE_RATE_HELP}
                percent={messageGauge.percent}
                delta={messageGauge.delta}
                color="#a88bd8"
              />
            </div>
          </div>
        </div>

        {data.robots && <MyRobotsCard r={data.robots} onManage={() => navigate('/bots')} />}
        {data.channels && (
          <MyChannelsCard c={data.channels} onManage={() => navigate('/channels/accounts')} />
        )}
        {data.unread && <UnreadCard list={data.unread} onViewAll={() => navigate('/messages')} />}
      </div>
    </div>
  )
}

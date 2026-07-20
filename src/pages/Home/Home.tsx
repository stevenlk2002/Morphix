import { useEffect, useRef, useState, type CSSProperties, type ReactNode } from 'react'
import { FileText, Bot, Check, MessageSquare, User, HelpCircle } from 'lucide-react'
import { Link, useNavigate } from 'react-router-dom'
import './Home.css'

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

// 指标定义文案（原型 gauge 标题旁「?」气泡）
const SESSION_RATE_HELP = '机器人会话处理率 = 机器人处理会话数 / 有客户消息的托管会话数'
const MESSAGE_RATE_HELP = '机器人消息处理率 = 机器人处理消息数 / 总消息数'

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
  const [hover, setHover] = useState<{ idx: number; cx: number } | null>(null)
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

const USE_MOCK = true

export default function HomePage() {
  const navigate = useNavigate()
  const [tab, setTab] = useState('sessions')

  // Mock-first：无后端时直接渲染样例数据，避免「仪表盘数据加载失败」报错与 loading 态。
  // 后端就绪时：将 USE_MOCK 改为 false，并在此改为真实 API 结果：
  //   const res = await dashboardApi.get(); setData(res as DashboardData)
  const data: DashboardData = USE_MOCK ? dashboardSample : dashboardSample

  const activeTab =
    CHART_TABS.find((t) => t.key === tab) ?? CHART_TABS[0]
  const series = activeTab.series
  const chartData = CHART_DATA[tab]

  const sessionGauge = data?.gauges?.sessionRate ?? { percent: 0, delta: 0 }
  const messageGauge = data?.gauges?.messageRate ?? { percent: 0, delta: 0 }

  return (
    <div className="home-page">
      <div className="home-grid">
        <div className="card home-overview">
          <div className="card-header">
            <span className="card-title">
              数据总览<span className="card-subtitle">（近七天）</span>
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
                <LineChart data={chartData} series={series} height={280} />
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
        {data.unread && <UnreadCard list={data.unread} onViewAll={() => navigate('/sessions')} />}
      </div>
    </div>
  )
}

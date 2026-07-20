import { useState } from 'react'
import {
  Sparkles,
  Bot,
  MessageSquare,
  Wallet,
  Receipt,
  FileText,
  Download,
  type LucideIcon,
} from 'lucide-react'
import Button from '../../components/common/Button'
import '../../pages/prototype.css'
import './Resources.css'

/** 是否使用本地 mock 数据。接入真实后端时置为 false 并取消注释下方 fetch 调用。 */
const USE_MOCK = true

// 后端接口契约（mock 阶段暂未启用，接入真实后端时取消注释并替换本地状态）：
// GET /api/resources      -> 拉取账户余额、套餐、各资源额度
// GET /api/resource-logs  -> 拉取动能值明细 / 席位到期日

/** 动能值明细 / 席位到期日 两种明细页签。 */
type ResourceTab = 'detail' | 'seats'

/** 明细记录筛选维度：全部 / 消耗 / 获得。 */
type LogFilter = 'all' | 'consume' | 'gain'

/** 单条动能值明细。 */
interface ResourceLog {
  id: string
  /** 发生时间（YYYY-MM-DD）。 */
  time: string
  /** 动能值变动点数，负数为消耗，正数为获得。 */
  points: number
  /** 变动类型。 */
  type: '消耗' | '获得'
}

/** 单个席位到期信息（「席位到期日」页签）。 */
interface SeatInfo {
  id: string
  /** 席位名称（渠道账号）。 */
  name: string
  /** 所属渠道。 */
  channel: string
  /** 到期日（YYYY-MM-DD）。 */
  expireAt: string
  /** 状态文案。 */
  status: '正常' | '即将到期' | '已过期'
}

/** 资源卡片中的单个统计项。 */
interface ResourceStat {
  /** 统计值（剩余点数 / 已创建数量等）。 */
  value: number | string
  /** 统计项标签。 */
  label: string
}

/** 资源卡片底部动作按钮描述。 */
interface ResourceAction {
  /** 按钮文案。 */
  label: string
  /** 按钮变体（与 Button 组件一致）。 */
  variant: 'primary' | 'secondary'
}

/** 资源卡片数据结构（由 MOCK 数组渲染）。 */
interface ResourceCard {
  id: string
  /** 卡片图标组件。 */
  icon: LucideIcon
  /** 卡片标题。 */
  title: string
  /** 图标底色（原型中的柔和色块）。 */
  iconBg: string
  /** 统计项列表（2 项）。 */
  stats: ResourceStat[]
  /** 底部动作按钮。 */
  actions: ResourceAction[]
}

/** 账户套餐信息。 */
interface PlanInfo {
  /** 套餐名称徽标。 */
  name: string
}

/** 可用余额明细（用于公式展示）。 */
interface BalanceDetail {
  recharge: number
  gift: number
  unsettled: number
}

/** 资源卡片种子数据。 */
const MOCK_CARDS: ResourceCard[] = [
  {
    id: 'kinetic',
    icon: Sparkles,
    title: '系统动能值',
    iconBg: '#f5c99b',
    stats: [
      { value: 908, label: '动能值剩余点数' },
      { value: 0, label: '今天已用点数' },
    ],
    actions: [{ label: '充值', variant: 'primary' }],
  },
  {
    id: 'bot-quota',
    icon: Bot,
    title: '机器人额度',
    iconBg: '#a8dcc1',
    stats: [
      { value: 2, label: '已创建机器人' },
      { value: 2, label: '机器人额度' },
    ],
    actions: [{ label: '升级套餐解锁更多额度', variant: 'secondary' }],
  },
  {
    id: 'channel-account',
    icon: MessageSquare,
    title: '渠道账号',
    iconBg: '#a8c8e8',
    stats: [
      { value: 1, label: '已创建席位' },
      { value: 1, label: '席位额度' },
    ],
    actions: [
      { label: '购买席位', variant: 'primary' },
      { label: '续费席位', variant: 'secondary' },
    ],
  },
]

/** 动能值明细种子数据（2-3 行）。 */
const MOCK_LOGS: ResourceLog[] = [
  { id: 'log-1', time: '2026-07-09', points: -92, type: '消耗' },
  { id: 'log-2', time: '2026-07-08', points: 100, type: '获得' },
  { id: 'log-3', time: '2026-07-07', points: -15, type: '消耗' },
]

/** 席位到期日种子数据。 */
const MOCK_SEATS: SeatInfo[] = [
  { id: 'seat-1', name: '微信渠道席位', channel: '微信', expireAt: '2026-08-09', status: '正常' },
]

/** 套餐种子数据。 */
const MOCK_PLAN: PlanInfo = { name: 'Basic' }

/** 余额明细种子数据（均从原型规格取值）。 */
const MOCK_BALANCE: BalanceDetail = { recharge: 0, gift: 0, unsettled: 0 }

/** 金额格式化（保留两位小数，带千分位）。 */
function formatMoney(value: number): string {
  return value.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

/**
 * 我的资源页（/resources）。
 * mock-first：使用种子数据 + 本地状态实现完整交互（自动续费开关、页签切换、明细筛选），
 * 不依赖后端。
 */
export default function ResourcesPage() {
  const [autoRenew, setAutoRenew] = useState<boolean>(false)
  const [activeTab, setActiveTab] = useState<ResourceTab>('detail')
  const [logs] = useState<ResourceLog[]>(USE_MOCK ? MOCK_LOGS : [])
  const [seats] = useState<SeatInfo[]>(USE_MOCK ? MOCK_SEATS : [])
  const [plan] = useState<PlanInfo>(MOCK_PLAN)
  const [balance] = useState<BalanceDetail>(MOCK_BALANCE)

  const [logFilter, setLogFilter] = useState<LogFilter>('all')
  const [dateStart, setDateStart] = useState('')
  const [dateEnd, setDateEnd] = useState('')
  const [note, setNote] = useState<string>('')

  let noteTimer: ReturnType<typeof window.setTimeout> | null = null

  /** 展示一条内联提示（按钮占位行为）。2.5s 后自动消失。 */
  const showNote = (message: string) => {
    setNote(message)
    if (noteTimer) window.clearTimeout(noteTimer)
    noteTimer = window.setTimeout(() => setNote(''), 2500)
  }

  /** 自动续费开关切换。 */
  const toggleAutoRenew = () => setAutoRenew((prev) => !prev)

  /** 明细类型筛选（同一按钮再次点击则重置为全部）。 */
  const handleLogFilter = (target: Exclude<LogFilter, 'all'>) => {
    setLogFilter((prev) => (prev === target ? 'all' : target))
  }

  /** 余额可用金额（充值 + 赠送 - 未结清）。 */
  const availableBalance = balance.recharge + balance.gift - balance.unsettled

  const visibleLogs = logs.filter((log) => {
    if (logFilter === 'consume') return log.type === '消耗'
    if (logFilter === 'gain') return log.type === '获得'
    return true
  })

  const statusBadge = (status: SeatInfo['status']) => {
    if (status === '正常') return 'proto-badge-success'
    if (status === '即将到期') return 'proto-badge-warning'
    return 'proto-badge-danger'
  }

  return (
    <div className="proto-page">
      <div className="page-header">
        <div>
          <h2 className="page-title">我的资源</h2>
          <p className="page-subtitle">查看账户余额与各项资源额度使用情况</p>
        </div>
      </div>

      {/* ---- 顶部：套餐 / 余额 / 资源卡片 ---- */}
      <div className="proto-card">
        <div className="resource-plan-bar">
          <span className="resource-plan-badge">
            <Sparkles size={14} />
            {plan.name}
          </span>
          <label className="resource-auto-renew">
            <span>自动续费：{autoRenew ? '已开启' : '未开启'}</span>
            <button
              type="button"
              className={`proto-switch ${autoRenew ? 'on' : ''}`}
              role="switch"
              aria-checked={autoRenew}
              aria-label="自动续费开关"
              onClick={toggleAutoRenew}
            >
              <span className="proto-switch-knob" />
            </button>
          </label>
        </div>

        <div className="resource-balance">
          <span className="resource-balance-label">可用余额</span>
          <span className="resource-balance-value">¥{formatMoney(availableBalance)}</span>
          <span className="resource-balance-formula">
            =（充值金额：¥{formatMoney(balance.recharge)} + 赠送金额：¥{formatMoney(balance.gift)}）—
            未结清金额：¥{formatMoney(balance.unsettled)}
          </span>
        </div>

        <div className="resource-balance-actions">
          <Button
            variant="primary"
            size="sm"
            icon={<Wallet size={14} />}
            onClick={() => showNote('「充值余额」功能开发中')}
          >
            充值余额
          </Button>
          <Button
            variant="ghost"
            size="sm"
            icon={<Receipt size={14} />}
            onClick={() => showNote('「收支明细」功能开发中')}
          >
            收支明细
          </Button>
          <Button
            variant="ghost"
            size="sm"
            icon={<FileText size={14} />}
            onClick={() => showNote('「月账单」功能开发中')}
          >
            月账单
          </Button>
        </div>

        <div className="resource-cards">
          {MOCK_CARDS.map((card) => {
            const CardIcon = card.icon
            return (
              <div className="proto-card resource-card" key={card.id}>
                <div className="resource-card-head">
                  <span className="resource-card-icon" style={{ background: card.iconBg }}>
                    <CardIcon size={18} />
                  </span>
                  <span className="proto-card-title">{card.title}</span>
                </div>
                <div className="resource-card-body">
                  {card.stats.map((stat, idx) => (
                    <div className="resource-card-item" key={idx}>
                      <span className="resource-card-value">{stat.value}</span>
                      <span className="resource-card-label">{stat.label}</span>
                    </div>
                  ))}
                </div>
                <div className="resource-card-actions">
                  {card.actions.map((action, idx) => (
                    <Button
                      key={idx}
                      variant={action.variant}
                      size="sm"
                      onClick={() => showNote(`「${action.label}」功能开发中`)}
                    >
                      {action.label}
                    </Button>
                  ))}
                </div>
              </div>
            )
          })}
        </div>
      </div>

      {/* ---- 底部：明细页签 / 筛选 / 表格 ---- */}
      <div className="proto-card">
        <div className="resource-tabs">
          <button
            type="button"
            className={`resource-tab ${activeTab === 'detail' ? 'active' : ''}`}
            onClick={() => setActiveTab('detail')}
          >
            动能值明细
          </button>
          <button
            type="button"
            className={`resource-tab ${activeTab === 'seats' ? 'active' : ''}`}
            onClick={() => setActiveTab('seats')}
          >
            席位到期日
          </button>
        </div>

        <div className="resource-filter-bar">
          <div className="resource-filter-group">
            <Button
              variant="ghost"
              size="sm"
              className={logFilter === 'consume' ? 'is-active' : ''}
              onClick={() => handleLogFilter('consume')}
            >
              消耗
            </Button>
            <Button
              variant="ghost"
              size="sm"
              className={logFilter === 'gain' ? 'is-active' : ''}
              onClick={() => handleLogFilter('gain')}
            >
              获得
            </Button>
          </div>
          <div className="resource-filter-group resource-filter-date">
            <input
              className="input"
              type="date"
              value={dateStart}
              onChange={(e) => setDateStart(e.target.value)}
              aria-label="开始日期"
            />
            <span className="resource-date-sep">-</span>
            <input
              className="input"
              type="date"
              value={dateEnd}
              onChange={(e) => setDateEnd(e.target.value)}
              aria-label="结束日期"
            />
            <Button
              variant="secondary"
              size="sm"
              icon={<Download size={14} />}
              onClick={() => showNote('已触发导出（演示）')}
            >
              导出
            </Button>
          </div>
        </div>

        {activeTab === 'detail' ? (
          <table className="proto-table">
            <thead>
              <tr>
                <th>时间</th>
                <th>动能值（点）</th>
                <th>类型</th>
              </tr>
            </thead>
            <tbody>
              {visibleLogs.length === 0 ? (
                <tr>
                  <td colSpan={3} className="resource-empty">
                    暂无明细数据
                  </td>
                </tr>
              ) : (
                visibleLogs.map((log) => (
                  <tr key={log.id}>
                    <td>{log.time}</td>
                    <td className={log.points < 0 ? 'resource-points-minus' : 'resource-points-plus'}>
                      {log.points > 0 ? `+${log.points}` : log.points}
                    </td>
                    <td>
                      <span
                        className={`proto-badge ${
                          log.type === '消耗' ? 'proto-badge-danger' : 'proto-badge-success'
                        }`}
                      >
                        {log.type}
                      </span>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        ) : (
          <table className="proto-table">
            <thead>
              <tr>
                <th>席位名称</th>
                <th>渠道</th>
                <th>到期日</th>
                <th>状态</th>
              </tr>
            </thead>
            <tbody>
              {seats.length === 0 ? (
                <tr>
                  <td colSpan={4} className="resource-empty">
                    暂无席位数据
                  </td>
                </tr>
              ) : (
                seats.map((seat) => (
                  <tr key={seat.id}>
                    <td>{seat.name}</td>
                    <td>{seat.channel}</td>
                    <td>{seat.expireAt}</td>
                    <td>
                      <span className={`proto-badge ${statusBadge(seat.status)}`}>{seat.status}</span>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        )}

        {note && (
          <div className="proto-notice proto-notice-success">
            <Sparkles size={14} /> {note}
          </div>
        )}
      </div>
    </div>
  )
}

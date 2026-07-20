import { useMemo, useState } from 'react'
import { ShoppingBag, Search, Download } from 'lucide-react'
import Button from '../../components/common/Button'
import Modal from '../../components/common/Modal'
import '../../pages/prototype.css'
import './Orders.css'

/** 是否使用本地 mock 数据。接入真实后端时置为 false 并取消注释下方 fetch 调用。 */
const USE_MOCK = true

// 后端接口契约（mock 阶段暂未启用，接入真实后端时取消注释并替换本地状态）：
// GET /api/orders  -> 拉取当前账户的订单列表（返回字段：orderNo / product / type /
//                      createdAt / paidAt / status / amount）
// 注意：后端当前尚未提供该接口，页面保持 mock-first。

/** 订单状态枚举值。 */
type OrderStatus = '已支付' | '待支付' | '已退款'

/** 订单行（对应后端 GET /api/orders 返回的字段）。 */
interface Order {
  /** 订单号。 */
  orderNo: string
  /** 商品名称。 */
  product: string
  /** 订单类型（新购 / 版本订阅）。 */
  type: string
  /** 创建时间（YYYY-MM-DD HH:mm:ss）。 */
  createdAt: string
  /** 支付/开通时间（YYYY-MM-DD HH:mm:ss，未支付为 '-'）。 */
  paidAt: string
  /** 订单状态。 */
  status: OrderStatus
  /** 应付金额（已格式化，含货币符号）。 */
  amount: string
}

/** 状态徽标样式映射。 */
const STATUS_BADGE: Record<OrderStatus, string> = {
  已支付: 'proto-badge-success',
  待支付: 'proto-badge-warning',
  已退款: 'proto-badge-danger',
}

/** 本地种子数据：2 个给定订单 + 2 个用于验证筛选的多样状态订单。 */
const MOCK: Order[] = [
  {
    orderNo: '2075160093289754624',
    product: '渠道账号（1个月）',
    type: '新购',
    createdAt: '2026-07-09 18:08:16',
    paidAt: '2026-07-09 18:08:29',
    status: '已支付',
    amount: '¥100',
  },
  {
    orderNo: '2075181255756493376',
    product: 'Basic版会员订阅-月',
    type: '版本订阅',
    createdAt: '2026-07-09 17:33:08',
    paidAt: '2026-07-09 17:33:25',
    status: '已支付',
    amount: '¥198',
  },
  {
    orderNo: '2075200000000000001',
    product: '高级版会员订阅-季',
    type: '版本订阅',
    createdAt: '2026-07-10 09:12:33',
    paidAt: '-',
    status: '待支付',
    amount: '¥568',
  },
  {
    orderNo: '2075211111111111111',
    product: '渠道账号（3个月）',
    type: '新购',
    createdAt: '2026-07-08 20:45:11',
    paidAt: '2026-07-08 20:45:30',
    status: '已退款',
    amount: '¥280',
  },
]

/**
 * 我的订单页（/resources/orders）。
 * mock-first：种子数据 + 本地状态，支持按订单号（子串）与创建日期区间过滤。
 * 查询按钮应用筛选条件；重置按钮清空筛选条件；导出为占位操作。
 */
export default function OrdersPage() {
  const [orders] = useState<Order[]>(USE_MOCK ? MOCK : [])

  // 筛选输入框的本地值（即时受控）。
  const [orderNoInput, setOrderNoInput] = useState('')
  const [dateFromInput, setDateFromInput] = useState('')
  const [dateToInput, setDateToInput] = useState('')

  // 已应用的筛选条件（点击「查询」时生效）。
  const [appliedOrderNo, setAppliedOrderNo] = useState('')
  const [appliedDateFrom, setAppliedDateFrom] = useState('')
  const [appliedDateTo, setAppliedDateTo] = useState('')

  // 导出提示（占位）。
  const [exportNote, setExportNote] = useState(false)

  // 详情弹窗。
  const [detailOpen, setDetailOpen] = useState(false)
  const [detailOrder, setDetailOrder] = useState<Order | null>(null)

  const filtered = useMemo(() => {
    const kw = appliedOrderNo.trim().toLowerCase()
    return orders.filter((o) => {
      if (kw && !o.orderNo.toLowerCase().includes(kw)) return false
      // 日期区间基于创建日期（createdAt 前 10 位 YYYY-MM-DD）比较。
      const day = o.createdAt.slice(0, 10)
      if (appliedDateFrom && day < appliedDateFrom) return false
      if (appliedDateTo && day > appliedDateTo) return false
      return true
    })
  }, [orders, appliedOrderNo, appliedDateFrom, appliedDateTo])

  const handleQuery = () => {
    setAppliedOrderNo(orderNoInput)
    setAppliedDateFrom(dateFromInput)
    setAppliedDateTo(dateToInput)
    setExportNote(false)
  }

  const handleReset = () => {
    setOrderNoInput('')
    setDateFromInput('')
    setDateToInput('')
    setAppliedOrderNo('')
    setAppliedDateFrom('')
    setAppliedDateTo('')
    setExportNote(false)
  }

  const handleExport = () => {
    // 后端导出接口尚未提供，此处仅给出占位提示。
    setExportNote(true)
  }

  const openDetail = (o: Order) => {
    setDetailOrder(o)
    setDetailOpen(true)
  }

  return (
    <div className="proto-page">
      <div className="page-header">
        <div>
          <h2 className="page-title">
            <ShoppingBag size={18} className="page-title-icon" /> 我的订单
          </h2>
          <p className="page-subtitle">查看账户订单与支付记录</p>
        </div>
      </div>

      <div className="proto-card">
        <h3 className="proto-card-title">我的订单</h3>

        <div className="orders-filter-bar">
          <div className="form-group orders-filter-item">
            <label className="form-label">订单号</label>
            <input
              className="input"
              type="text"
              placeholder="订单号"
              value={orderNoInput}
              onChange={(e) => setOrderNoInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') handleQuery()
              }}
            />
          </div>

          <div className="form-group orders-filter-item orders-filter-date">
            <label className="form-label">创建时间</label>
            <div className="orders-date-range">
              <input
                className="input orders-date-input"
                type="date"
                value={dateFromInput}
                onChange={(e) => setDateFromInput(e.target.value)}
              />
              <span className="orders-date-sep">→</span>
              <input
                className="input orders-date-input"
                type="date"
                value={dateToInput}
                onChange={(e) => setDateToInput(e.target.value)}
              />
            </div>
          </div>

          <div className="orders-filter-actions">
            <Button variant="secondary" size="sm" onClick={handleReset}>
              重置
            </Button>
            <Button
              variant="primary"
              size="sm"
              className="btn-query"
              icon={<Search size={14} />}
              onClick={handleQuery}
            >
              查询
            </Button>
            <Button variant="primary" size="sm" icon={<Download size={14} />} onClick={handleExport}>
              导出
            </Button>
          </div>
        </div>

        {exportNote && (
          <div className="orders-export-note proto-tip">
            <Download size={16} />
            <span>导出功能待后端接口上线后开放，当前为演示占位。</span>
          </div>
        )}

        {filtered.length === 0 ? (
          <div className="orders-empty">
            <ShoppingBag size={48} className="orders-empty-icon" />
            <p className="orders-empty-text">暂无符合条件的订单</p>
          </div>
        ) : (
          <table className="proto-table">
            <thead>
              <tr>
                <th>订单号</th>
                <th>商品</th>
                <th>订单类型</th>
                <th>创建时间</th>
                <th>支付/开通时间</th>
                <th>订单状态</th>
                <th className="orders-amount-col">应付金额</th>
                <th className="orders-action-col">操作</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((o) => (
                <tr key={o.orderNo}>
                  <td className="orders-no-cell">{o.orderNo}</td>
                  <td>{o.product}</td>
                  <td>{o.type}</td>
                  <td className="text-secondary">{o.createdAt}</td>
                  <td className="text-secondary">{o.paidAt}</td>
                  <td>
                    <span className={`proto-badge ${STATUS_BADGE[o.status]}`}>{o.status}</span>
                  </td>
                  <td className="orders-amount-cell">{o.amount}</td>
                  <td>
                    <Button variant="ghost" size="sm" onClick={() => openDetail(o)}>
                      详情
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* 订单详情 */}
      <Modal
        open={detailOpen}
        title="订单详情"
        onClose={() => setDetailOpen(false)}
        footer={
          <Button variant="ghost" size="sm" onClick={() => setDetailOpen(false)}>
            关闭
          </Button>
        }
      >
        {detailOrder && (
          <dl className="orders-detail">
            <div className="orders-detail-row">
              <dt>订单号</dt>
              <dd>{detailOrder.orderNo}</dd>
            </div>
            <div className="orders-detail-row">
              <dt>商品</dt>
              <dd>{detailOrder.product}</dd>
            </div>
            <div className="orders-detail-row">
              <dt>订单类型</dt>
              <dd>{detailOrder.type}</dd>
            </div>
            <div className="orders-detail-row">
              <dt>创建时间</dt>
              <dd>{detailOrder.createdAt}</dd>
            </div>
            <div className="orders-detail-row">
              <dt>支付/开通时间</dt>
              <dd>{detailOrder.paidAt}</dd>
            </div>
            <div className="orders-detail-row">
              <dt>订单状态</dt>
              <dd>
                <span className={`proto-badge ${STATUS_BADGE[detailOrder.status]}`}>
                  {detailOrder.status}
                </span>
              </dd>
            </div>
            <div className="orders-detail-row">
              <dt>应付金额</dt>
              <dd className="orders-detail-amount">{detailOrder.amount}</dd>
            </div>
          </dl>
        )}
      </Modal>
    </div>
  )
}

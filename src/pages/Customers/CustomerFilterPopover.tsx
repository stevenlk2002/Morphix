import { Filter } from 'lucide-react'

interface Props {
  open: boolean
  onToggle: () => void
}

/**
 * 「更多筛选」popover（原型 8511-8525）。
 * P1：全部筛选字段，当前简化版保留框架结构。
 */
export default function CustomerFilterPopover({ open, onToggle }: Props) {
  return (
    <div className="customer-filter-wrap">
      <button className="btn btn-secondary btn-sm" onClick={onToggle}>
        更多筛选 <Filter size={14} style={{ marginLeft: 4 }} />
      </button>
      <div
        className={`customer-filter-popover${open ? ' open' : ''}`}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="customer-filter-field">
          <label>最后沟通时间</label>
          <div className="date-range">
            <input type="date" className="input" />
            <span>-</span>
            <input type="date" className="input" />
          </div>
        </div>
        <div className="customer-filter-field">
          <label>距上次沟通天数</label>
          <select className="select" style={{ width: '100%' }}>
            <option>请选择</option>
            <option>1天内</option>
            <option>3天内</option>
            <option>7天内</option>
          </select>
        </div>
        <div className="customer-filter-field">
          <label>最后沟通记录</label>
          <input className="input" placeholder="请输入" style={{ width: '100%' }} />
        </div>
        <div className="customer-filter-field">
          <label>添加时间</label>
          <div className="date-range">
            <input type="date" className="input" />
            <span>-</span>
            <input type="date" className="input" />
          </div>
        </div>
        <div className="customer-filter-field">
          <label>标签</label>
          <select className="select" style={{ width: '100%' }}>
            <option>请选择标签</option>
          </select>
        </div>
        <div className="customer-filter-field">
          <label>备注</label>
          <input className="input" placeholder="请输入" style={{ width: '100%' }} />
        </div>
        <div className="customer-filter-field">
          <label>区域</label>
          <select className="select" style={{ width: '100%' }}>
            <option>请选择</option>
          </select>
        </div>
        <div className="customer-filter-field">
          <label>年龄</label>
          <select className="select" style={{ width: '100%' }}>
            <option>请选择</option>
            <option>18-30</option>
            <option>31-40</option>
          </select>
        </div>
        <div className="customer-filter-field">
          <label>生日</label>
          <div className="date-range">
            <input type="date" className="input" />
            <span>-</span>
            <input type="date" className="input" />
          </div>
        </div>
        <div className="customer-filter-actions">
          <button className="btn btn-secondary btn-sm" onClick={onToggle}>
            取消
          </button>
          <button className="btn btn-primary btn-sm" onClick={onToggle}>
            确定
          </button>
        </div>
      </div>
    </div>
  )
}

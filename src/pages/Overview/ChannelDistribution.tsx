import '../../pages/prototype.css'

interface ChannelDist {
  name: string
  count: number
  color: string
}

const DIST: ChannelDist[] = [
  { name: '企业微信', count: 42, color: 'var(--primary)' },
  { name: '个人微信', count: 28, color: 'var(--purple)' },
  { name: 'WhatsApp', count: 16, color: 'var(--teal)' },
  { name: '企业 WhatsApp', count: 9, color: 'var(--warning)' },
  { name: '其他', count: 5, color: 'var(--text-tertiary)' },
]

export default function ChannelDistributionPage() {
  const total = DIST.reduce((sum, d) => sum + d.count, 0)
  const max = Math.max(...DIST.map((d) => d.count))

  return (
    <div className="proto-page">
      <div className="page-header">
        <div>
          <h2 className="page-title">渠道分布</h2>
          <p className="page-subtitle">各渠道账号 / 会话数量占比</p>
        </div>
      </div>

      <div className="proto-card">
        <div className="proto-section-title">渠道账号分布（共 {total} 个）</div>
        {DIST.map((d) => (
          <div className="proto-bar" key={d.name}>
            <span className="proto-bar-label">{d.name}</span>
            <span className="proto-bar-track">
              <span
                className="proto-bar-fill"
                style={{ width: `${(d.count / max) * 100}%`, background: d.color }}
              />
            </span>
            <span className="proto-bar-value">{d.count}</span>
          </div>
        ))}
      </div>

      <div className="proto-grid">
        {DIST.map((d) => (
          <div key={d.name} className="proto-card">
            <div className="proto-stat">
              <span className="proto-stat-value" style={{ color: d.color }}>
                {Math.round((d.count / total) * 100)}%
              </span>
              <span className="proto-stat-label">{d.name}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

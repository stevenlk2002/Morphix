import { ShieldAlert, Cpu } from 'lucide-react'

const DECISION_TYPE_META = {
  routing: { label: '路由', cls: 'tag-info' },
  workflow_select: { label: '工作流选择', cls: 'tag-info' },
  bot_select: { label: '机器人选择', cls: 'tag-info' },
  interrupt: { label: '中断', cls: 'tag-warning' },
  resume: { label: '恢复', cls: 'tag-success' },
  fallback: { label: '兜底', cls: 'tag-warning' },
}

const AGENT_STATUS_META = {
  pending: { label: '待处理', cls: 'tag-neutral' },
  succeeded: { label: '成功', cls: 'tag-success' },
  failed: { label: '失败', cls: 'tag-danger' },
  blocked: { label: '被拦截', cls: 'tag-warning' },
}

function formatTime(value) {
  if (!value) return '—'
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return value
  return d.toLocaleString('zh-CN', { hour12: false })
}

export default function AuditTab({ decisions, invocations }) {
  return (
    <div className="audit-tab">
      <section className="audit-section">
        <h3 className="audit-section-title">
          <ShieldAlert size={16} />
          策略决策记录
          <span className="audit-count">{decisions.length}</span>
        </h3>
        {decisions.length === 0 ? (
          <div className="sd-empty">暂无策略决策记录</div>
        ) : (
          <div className="audit-table-wrap">
            <table className="audit-table">
              <thead>
                <tr>
                  <th>决策类型</th>
                  <th>决策</th>
                  <th>理由码</th>
                  <th>模型</th>
                  <th>时间</th>
                </tr>
              </thead>
              <tbody>
                {decisions.map((d) => {
                  const meta = DECISION_TYPE_META[d.decision_type] || { label: d.decision_type, cls: 'tag-neutral' }
                  return (
                    <tr key={d.policy_decision_id}>
                      <td><span className={`tag ${meta.cls}`}>{meta.label}</span></td>
                      <td className="audit-decision">{d.decision}</td>
                      <td>
                        {d.reason_codes?.length > 0
                          ? d.reason_codes.map((c) => <span key={c} className="tag tag-neutral">{c}</span>)
                          : '—'}
                      </td>
                      <td className="mono">{d.model_profile || '—'}</td>
                      <td className="text-secondary">{formatTime(d.decided_at)}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="audit-section">
        <h3 className="audit-section-title">
          <Cpu size={16} />
          Agent 调用记录
          <span className="audit-count">{invocations.length}</span>
        </h3>
        {invocations.length === 0 ? (
          <div className="sd-empty">暂无 Agent 调用记录</div>
        ) : (
          <div className="audit-table-wrap">
            <table className="audit-table">
              <thead>
                <tr>
                  <th>Agent 类型</th>
                  <th>模型</th>
                  <th>状态</th>
                  <th>置信度</th>
                  <th>延迟</th>
                  <th>预估成本</th>
                </tr>
              </thead>
              <tbody>
                {invocations.map((a) => {
                  const sm = AGENT_STATUS_META[a.status] || AGENT_STATUS_META.pending
                  return (
                    <tr key={a.agent_invocation_id}>
                      <td>{a.agent_type}</td>
                      <td className="mono">{a.model_name}</td>
                      <td><span className={`tag ${sm.cls}`}>{sm.label}</span></td>
                      <td>{(a.confidence != null ? a.confidence : 0).toFixed(2)}</td>
                      <td>{a.latency_ms}ms</td>
                      <td>${a.estimated_cost.toFixed(4)}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  )
}

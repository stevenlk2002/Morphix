import { useEffect, useState } from 'react'
import { AlertCircle, RefreshCw, ChevronRight, Circle, Loader2, PauseCircle, XCircle, CheckCircle2, MinusCircle } from 'lucide-react'
import { getWorkflowRun, listNodeExecutions } from '../../../services/sessions'

const RUN_STATUS_META = {
  pending: { label: '待执行', cls: 'tag-neutral', icon: Circle },
  running: { label: '运行中', cls: 'tag-info', icon: Loader2 },
  waiting: { label: '等待中', cls: 'tag-warning', icon: PauseCircle },
  interrupted: { label: '已中断', cls: 'tag-warning', icon: PauseCircle },
  failed: { label: '失败', cls: 'tag-danger', icon: XCircle },
  succeeded: { label: '成功', cls: 'tag-success', icon: CheckCircle2 },
  cancelled: { label: '已取消', cls: 'tag-neutral', icon: MinusCircle },
}

const NODE_STATUS_META = {
  pending: { label: '待执行', cls: 'tag-neutral', icon: Circle },
  running: { label: '运行中', cls: 'tag-info', icon: Loader2 },
  waiting: { label: '等待中', cls: 'tag-warning', icon: PauseCircle },
  failed: { label: '失败', cls: 'tag-danger', icon: XCircle },
  completed: { label: '完成', cls: 'tag-success', icon: CheckCircle2 },
  skipped: { label: '跳过', cls: 'tag-neutral', icon: MinusCircle },
}

function formatTime(value) {
  if (!value) return '—'
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return value
  return d.toLocaleString('zh-CN', { hour12: false })
}

export default function RunTimelineTab({ conversationId, runs, projectId }) {
  const [selectedRunId, setSelectedRunId] = useState(runs[0]?.run_id || '')
  const [runDetail, setRunDetail] = useState(null)
  const [nodes, setNodes] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const effectiveRunId = selectedRunId || runs[0]?.run_id || ''

  async function loadRun(runId) {
    if (!runId) return
    setLoading(true)
    setError('')
    try {
      const [detail, nodeData] = await Promise.all([
        getWorkflowRun(runId),
        listNodeExecutions(runId, { pageSize: 50 }),
      ])
      setRunDetail(detail)
      setNodes(nodeData.items || [])
    } catch (e) {
      setError(e?.message || '加载运行详情失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadRun(effectiveRunId)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [effectiveRunId])

  if (runs.length === 0) {
    return <div className="sd-empty">该会话暂无工作流运行记录</div>
  }

  const runStatus = RUN_STATUS_META[runDetail?.status] || RUN_STATUS_META.pending
  const RunIcon = runStatus.icon

  return (
    <div className="runs-tab">
      <div className="runs-list-col">
        <div className="runs-list-title">运行列表</div>
        {runs.map((r) => {
          const sm = RUN_STATUS_META[r.status] || RUN_STATUS_META.pending
          const Icon = sm.icon
          return (
            <button
              key={r.run_id}
              className={`run-item ${effectiveRunId === r.run_id ? 'active' : ''}`}
              onClick={() => setSelectedRunId(r.run_id)}
            >
              <span className={`tag ${sm.cls}`}><Icon size={12} />{sm.label}</span>
              <span className="run-item-id">{r.run_id.slice(0, 8)}</span>
              <span className="run-item-time">{formatTime(r.started_at)}</span>
            </button>
          )
        })}
      </div>

      <div className="runs-detail-col">
        {error && (
          <div className="sd-inline-error">
            <AlertCircle size={16} />
            {error}
            <button className="btn btn-ghost btn-sm" onClick={() => loadRun(effectiveRunId)}><RefreshCw size={14} />重试</button>
          </div>
        )}

        {runDetail && (
          <div className="run-detail-card">
            <div className="run-detail-head">
              <span className={`tag ${runStatus.cls}`}><RunIcon size={14} className={runDetail.status === 'running' ? 'spin' : ''} />{runStatus.label}</span>
              <span className="run-detail-id mono">{runDetail.run_id}</span>
            </div>
            <dl className="run-detail-grid">
              <div><dt>触发类型</dt><dd>{r_trigger(runDetail.trigger_type)}</dd></div>
              <div><dt>工作流版本</dt><dd className="mono">{runDetail.workflow_version_id || '—'}</dd></div>
              <div><dt>开始时间</dt><dd>{formatTime(runDetail.started_at)}</dd></div>
              <div><dt>结束时间</dt><dd>{formatTime(runDetail.ended_at)}</dd></div>
              {runDetail.error_code && (
                <div className="run-error"><dt>错误</dt><dd>{runDetail.error_code} {runDetail.error_message}</dd></div>
              )}
              {runDetail.result_summary && (
                <div className="run-result"><dt>结果摘要</dt><dd>{runDetail.result_summary}</dd></div>
              )}
            </dl>
          </div>
        )}

        <div className="nodes-title">节点执行轨迹</div>
        {loading && nodes.length === 0 ? (
          <div className="sd-empty"><RefreshCw size={16} className="spin" /> 加载节点…</div>
        ) : nodes.length === 0 ? (
          <div className="sd-empty">暂无节点执行记录</div>
        ) : (
          <ol className="node-timeline">
            {nodes.map((n, idx) => {
              const nm = NODE_STATUS_META[n.status] || NODE_STATUS_META.pending
              const Icon = nm.icon
              return (
                <li key={n.node_execution_id} className="node-item">
                  <div className="node-marker">
                    <Icon size={16} className={n.status === 'running' ? 'spin' : ''} />
                    {idx < nodes.length - 1 && <span className="node-line" />}
                  </div>
                  <div className="node-content">
                    <div className="node-head">
                      <span className="node-name">{n.node_type}</span>
                      <span className="node-id mono">{n.node_id}</span>
                      <span className={`tag ${nm.cls}`}>{nm.label}</span>
                      {n.attempt_no > 1 && <span className="text-secondary">第{n.attempt_no}次</span>}
                    </div>
                    <div className="node-sub text-secondary">
                      {n.executor_type && <span>执行者: {n.executor_type}</span>}
                      {n.duration_ms != null && <span>耗时: {n.duration_ms}ms</span>}
                      {n.error_code && <span className="tag tag-danger">{n.error_code}</span>}
                    </div>
                  </div>
                </li>
              )
            })}
          </ol>
        )}
      </div>
    </div>
  )
}

function r_trigger(v) {
  const map = { manual: '手动', inbound_message: '入站消息', retry: '重试', campaign: '营销活动' }
  return map[v] || v
}

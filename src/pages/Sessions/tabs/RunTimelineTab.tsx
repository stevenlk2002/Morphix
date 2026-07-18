import { useEffect, useState } from 'react'
import {
  AlertCircle,
  RefreshCw,
  Circle,
  Loader2,
  PauseCircle,
  XCircle,
  CheckCircle2,
  MinusCircle,
  type LucideIcon,
} from 'lucide-react'
import { getWorkflowRun, listNodeExecutions } from '../../../services/sessions'
import type { WorkflowRunDetail, NodeExecution, WorkflowRunStatus, NodeStatus } from '../../../types/control'

const RUN_STATUS_META: Record<WorkflowRunStatus, { label: string; cls: string; icon: LucideIcon }> = {
  pending: { label: '待执行', cls: 'tag-neutral', icon: Circle },
  running: { label: '运行中', cls: 'tag-info', icon: Loader2 },
  waiting: { label: '等待中', cls: 'tag-warning', icon: PauseCircle },
  interrupted: { label: '已中断', cls: 'tag-warning', icon: PauseCircle },
  failed: { label: '失败', cls: 'tag-danger', icon: XCircle },
  completed: { label: '成功', cls: 'tag-success', icon: CheckCircle2 },
  cancelled: { label: '已取消', cls: 'tag-neutral', icon: MinusCircle },
}

const NODE_STATUS_META: Record<NodeStatus, { label: string; cls: string; icon: LucideIcon }> = {
  pending: { label: '待执行', cls: 'tag-neutral', icon: Circle },
  running: { label: '运行中', cls: 'tag-info', icon: Loader2 },
  waiting: { label: '等待中', cls: 'tag-warning', icon: PauseCircle },
  failed: { label: '失败', cls: 'tag-danger', icon: XCircle },
  completed: { label: '完成', cls: 'tag-success', icon: CheckCircle2 },
  skipped: { label: '跳过', cls: 'tag-neutral', icon: MinusCircle },
}

function formatTime(value?: string | null): string {
  if (!value) return '—'
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return value
  return d.toLocaleString('zh-CN', { hour12: false })
}

function triggerLabel(v: string): string {
  const map: Record<string, string> = {
    manual: '手动',
    inbound_message: '入站消息',
    retry: '重试',
    campaign: '营销活动',
  }
  return map[v] || v
}

interface RunTimelineTabProps {
  conversationId: string
  runs: WorkflowRunDetail[]
  projectId: string
}

export default function RunTimelineTab({ conversationId: _conversationId, runs, projectId: _projectId }: RunTimelineTabProps) {
  const [selectedRunId, setSelectedRunId] = useState(runs[0]?.runId || '')
  const [runDetail, setRunDetail] = useState<WorkflowRunDetail | null>(null)
  const [nodes, setNodes] = useState<NodeExecution[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const effectiveRunId = selectedRunId || runs[0]?.runId || ''

  async function loadRun(runId: string) {
    if (!runId) return
    setLoading(true)
    setError('')
    try {
      const [detail, nodeData] = await Promise.all([
        getWorkflowRun(runId),
        listNodeExecutions({ runId, pageSize: 50 }),
      ])
      setRunDetail(detail)
      setNodes(nodeData.items || [])
    } catch (e) {
      setError(e instanceof Error ? e.message : '加载运行详情失败')
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

  const runStatus = RUN_STATUS_META[runDetail?.status ?? 'pending'] || RUN_STATUS_META.pending
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
              key={r.runId}
              type="button"
              className={`run-item ${effectiveRunId === r.runId ? 'active' : ''}`}
              onClick={() => setSelectedRunId(r.runId)}
            >
              <span className={`tag ${sm.cls}`}>
                <Icon size={12} />
                {sm.label}
              </span>
              <span className="run-item-id">{r.runId.slice(0, 8)}</span>
              <span className="run-item-time">{formatTime(r.startedAt)}</span>
            </button>
          )
        })}
      </div>

      <div className="runs-detail-col">
        {error && (
          <div className="sd-inline-error">
            <AlertCircle size={16} />
            {error}
            <button type="button" className="btn btn-ghost btn-sm" onClick={() => loadRun(effectiveRunId)}>
              <RefreshCw size={14} />重试
            </button>
          </div>
        )}

        {runDetail && (
          <div className="run-detail-card">
            <div className="run-detail-head">
              <span className={`tag ${runStatus.cls}`}>
                <RunIcon size={14} className={runDetail.status === 'running' ? 'spin' : ''} />
                {runStatus.label}
              </span>
              <span className="run-detail-id mono">{runDetail.runId}</span>
            </div>
            <dl className="run-detail-grid">
              <div>
                <dt>触发类型</dt>
                <dd>{triggerLabel(runDetail.triggerType)}</dd>
              </div>
              <div>
                <dt>工作流版本</dt>
                <dd className="mono">{runDetail.workflowVersionId || '—'}</dd>
              </div>
              <div>
                <dt>开始时间</dt>
                <dd>{formatTime(runDetail.startedAt)}</dd>
              </div>
              <div>
                <dt>结束时间</dt>
                <dd>{formatTime(runDetail.endedAt)}</dd>
              </div>
              {runDetail.errorCode && (
                <div className="run-error">
                  <dt>错误</dt>
                  <dd>
                    {runDetail.errorCode} {runDetail.errorMessage}
                  </dd>
                </div>
              )}
              {runDetail.resultSummary && (
                <div className="run-result">
                  <dt>结果摘要</dt>
                  <dd>{runDetail.resultSummary}</dd>
                </div>
              )}
            </dl>
          </div>
        )}

        <div className="nodes-title">节点执行轨迹</div>
        {loading && nodes.length === 0 ? (
          <div className="sd-empty">
            <RefreshCw size={16} className="spin" /> 加载节点…
          </div>
        ) : nodes.length === 0 ? (
          <div className="sd-empty">暂无节点执行记录</div>
        ) : (
          <ol className="node-timeline">
            {nodes.map((n, idx) => {
              const nm = NODE_STATUS_META[n.status] || NODE_STATUS_META.pending
              const Icon = nm.icon
              return (
                <li key={n.nodeExecutionId} className="node-item">
                  <div className="node-marker">
                    <Icon size={16} className={n.status === 'running' ? 'spin' : ''} />
                    {idx < nodes.length - 1 && <span className="node-line" />}
                  </div>
                  <div className="node-content">
                    <div className="node-head">
                      <span className="node-name">{n.nodeType}</span>
                      <span className="node-id mono">{n.nodeId}</span>
                      <span className={`tag ${nm.cls}`}>{nm.label}</span>
                      {n.attemptNo > 1 && <span className="text-secondary">第{n.attemptNo}次</span>}
                    </div>
                    <div className="node-sub text-secondary">
                      {n.executorType && <span>执行者: {n.executorType}</span>}
                      {n.durationMs != null && <span>耗时: {n.durationMs}ms</span>}
                      {n.errorCode && <span className="tag tag-danger">{n.errorCode}</span>}
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

import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  ArrowLeft,
  RefreshCw,
  AlertCircle,
  MessageSquare,
  Activity,
  ShieldCheck,
  Hand,
  type LucideIcon,
} from 'lucide-react'
import {
  getConversation,
  getConversationRuntime,
  listWorkflowRuns,
  listPolicyDecisions,
  listAgentInvocations,
} from '../../services/sessions'
import type {
  ConversationDetail,
  ConversationRuntime,
  WorkflowRunDetail,
  PolicyDecision,
  AgentInvocation,
} from '../../types/control'
import MessageStreamTab from './tabs/MessageStreamTab'
import RunTimelineTab from './tabs/RunTimelineTab'
import AuditTab from './tabs/AuditTab'
import HandoffTab from './tabs/HandoffTab'
import './SessionDetail.css'

interface TabDef {
  id: string
  label: string
  icon: LucideIcon
}

const TABS: TabDef[] = [
  { id: 'messages', label: '消息流', icon: MessageSquare },
  { id: 'runs', label: '运行轨迹', icon: Activity },
  { id: 'audit', label: '审计 / 决策', icon: ShieldCheck },
  { id: 'handoff', label: '接管', icon: Hand },
]

const PROJECT_ID = '01JPROJECT'

export default function SessionDetailPage() {
  const { sessionId } = useParams<{ sessionId: string }>()
  const navigate = useNavigate()

  const [detail, setDetail] = useState<ConversationDetail | null>(null)
  const [runtime, setRuntime] = useState<ConversationRuntime | null>(null)
  const [runs, setRuns] = useState<WorkflowRunDetail[]>([])
  const [decisions, setDecisions] = useState<PolicyDecision[]>([])
  const [invocations, setInvocations] = useState<AgentInvocation[]>([])
  const [activeTab, setActiveTab] = useState('messages')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  async function fetchAll() {
    if (!sessionId) return
    setLoading(true)
    setError('')
    try {
      const [d, r, runData, decData] = await Promise.all([
        getConversation(sessionId),
        getConversationRuntime(sessionId, PROJECT_ID),
        listWorkflowRuns({ projectId: PROJECT_ID, conversationId: sessionId, pageSize: 50 }),
        listPolicyDecisions({ conversationId: sessionId, pageSize: 50 }),
      ])
      setDetail(d)
      setRuntime(r)
      const runItems = runData.items || []
      setRuns(runItems)
      setDecisions(decData.items || [])
      // 契约 agent-invocations 为「按运行」维度，逐运行聚合。
      const invChunks = await Promise.all(
        runItems.map((run) => listAgentInvocations({ runId: run.runId }))
      )
      setInvocations(invChunks.flatMap((chunk) => chunk.items || []))
    } catch (e) {
      setError(e instanceof Error ? e.message : '加载会话详情失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchAll()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId])

  if (loading) {
    return (
      <div className="sd-loading">
        <RefreshCw size={20} className="spin" />
        <span>加载会话详情…</span>
      </div>
    )
  }

  if (error || !detail) {
    return (
      <div className="sd-error">
        <AlertCircle size={20} />
        <span>{error || '未找到会话'}</span>
        <button type="button" className="btn btn-ghost" onClick={() => navigate('/sessions')}>
          返回列表
        </button>
      </div>
    )
  }

  return (
    <div className="sd-page">
      <div className="sd-topbar">
        <button type="button" className="btn btn-ghost btn-sm" onClick={() => navigate('/sessions')}>
          <ArrowLeft size={16} />
          返回
        </button>
        <div className="sd-subject">
          <span className="sd-subject-text">{detail.subject || '(无主题)'}</span>
          <span className="sd-subject-id">{detail.conversationId}</span>
        </div>
        <button type="button" className="btn btn-ghost btn-sm" onClick={fetchAll}>
          <RefreshCw size={16} />
          刷新
        </button>
      </div>

      <div className="sd-tabs">
        {TABS.map((t) => {
          const Icon = t.icon
          const badge =
            t.id === 'runs'
              ? runs.length
              : t.id === 'audit'
                ? decisions.length + invocations.length
                : null
          return (
            <button
              key={t.id}
              type="button"
              className={`sd-tab ${activeTab === t.id ? 'active' : ''}`}
              onClick={() => setActiveTab(t.id)}
            >
              <Icon size={16} />
              {t.label}
              {badge ? <span className="sd-tab-badge">{badge}</span> : null}
            </button>
          )
        })}
      </div>

      <div className="sd-content">
        {activeTab === 'messages' && (
          <MessageStreamTab conversationId={sessionId ?? ''} runtime={runtime} contact={detail.contact ?? null} />
        )}
        {activeTab === 'runs' && (
          <RunTimelineTab conversationId={sessionId ?? ''} runs={runs} projectId={PROJECT_ID} />
        )}
        {activeTab === 'audit' && <AuditTab decisions={decisions} invocations={invocations} />}
        {activeTab === 'handoff' && (
          <HandoffTab
            conversationId={sessionId ?? ''}
            detail={detail}
            runtime={runtime}
            onChanged={fetchAll}
            projectId={PROJECT_ID}
          />
        )}
      </div>
    </div>
  )
}

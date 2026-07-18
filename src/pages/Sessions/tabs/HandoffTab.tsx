import { useState, useEffect } from 'react'
import { Hand, Undo2, Play, Pause, RefreshCw, X, AlertCircle } from 'lucide-react'
import {
  takeOverConversation,
  returnConversation,
  createWorkflowRun,
  interruptWorkflowRun,
  resumeWorkflowRun,
  cancelWorkflowRun,
} from '../../../services/sessions'
import type { ConversationDetail, ConversationRuntime, HandoffStatus, OwnerType } from '../../../types/control'

const HANDOFF_LABEL: Record<string, string> = {
  none: '无',
  requested: '申请中',
  active: '接管中',
  returning: '交还中',
  returned: '已交还',
}

const OWNER_LABEL: Record<OwnerType, string> = { ai: 'AI', human: '人工' }

interface HandoffTabProps {
  conversationId: string
  detail: ConversationDetail
  runtime: ConversationRuntime | null
  onChanged?: () => void
  projectId: string
}

type ActionName = 'takeOver' | 'return' | 'run' | 'interrupt' | 'resume' | 'cancel'

const ACTION_LABEL: Record<ActionName, string> = {
  takeOver: '人工接管',
  return: '交还控制权',
  run: '手动触发运行',
  interrupt: '中断运行',
  resume: '恢复运行',
  cancel: '取消运行',
}

export default function HandoffTab({ conversationId, detail, runtime, onChanged, projectId }: HandoffTabProps) {
  const [operatorId, setOperatorId] = useState('op-001')
  const [reason, setReason] = useState('')
  const [actionLoading, setActionLoading] = useState('')
  const [error, setError] = useState('')
  const [toast, setToast] = useState('')

  useEffect(() => {
    if (!toast) return
    const t = setTimeout(() => setToast(''), 2600)
    return () => clearTimeout(t)
  }, [toast])

  const handoff: HandoffStatus = detail?.handoffStatus || 'none'
  const ownerType: OwnerType = detail?.ownerType || 'ai'
  const isHandedOff = handoff === 'active' || handoff === 'requested'
  const activeRunId = runtime?.activeRunId || ''

  async function runAction(name: ActionName, fn: () => Promise<unknown>) {
    setActionLoading(name)
    setError('')
    try {
      await fn()
      setToast(`${ACTION_LABEL[name]}成功`)
      setReason('')
      onChanged?.()
    } catch (e) {
      setError(e instanceof Error ? e.message : `${ACTION_LABEL[name]}失败`)
    } finally {
      setActionLoading('')
    }
  }

  return (
    <div className="handoff-tab">
      <div className="handoff-status-card">
        <div className="handoff-status-row">
          <span className="handoff-status-item">
            <span className="handoff-status-label">当前归属</span>
            <span className={`tag ${ownerType === 'human' ? 'tag-danger' : 'tag-success'}`}>
              {OWNER_LABEL[ownerType] || ownerType}
            </span>
          </span>
          <span className="handoff-status-item">
            <span className="handoff-status-label">接管状态</span>
            <span className="tag tag-neutral">{HANDOFF_LABEL[handoff] || handoff}</span>
          </span>
          {detail?.latestHandoff?.operatorId && (
            <span className="handoff-status-item">
              <span className="handoff-status-label">操作员</span>
              <span className="mono">{detail.latestHandoff.operatorId}</span>
            </span>
          )}
        </div>
      </div>

      <div className="handoff-form">
        <div className="handoff-field">
          <label>操作员 ID</label>
          <input
            type="text"
            value={operatorId}
            onChange={(e) => setOperatorId(e.target.value)}
            placeholder="op-001"
          />
        </div>
        <div className="handoff-field handoff-field-grow">
          <label>操作原因（可选）</label>
          <input
            type="text"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="例如：客户投诉需人工介入"
          />
        </div>
      </div>

      {error && (
        <div className="sd-inline-error">
          <AlertCircle size={16} />
          {error}
        </div>
      )}

      <div className="handoff-actions">
        {!isHandedOff ? (
          <button
            type="button"
            className="btn btn-danger"
            disabled={actionLoading !== '' || !operatorId.trim()}
            onClick={() =>
              runAction('takeOver', () =>
                takeOverConversation(conversationId, {
                  projectId,
                  operatorId: operatorId.trim(),
                  reason: reason.trim() || '手动接管',
                })
              )
            }
          >
            <Hand size={16} />
            {actionLoading === 'takeOver' ? '处理中…' : '人工接管'}
          </button>
        ) : (
          <button
            type="button"
            className="btn btn-primary"
            disabled={actionLoading !== '' || !operatorId.trim()}
            onClick={() =>
              runAction('return', () =>
                returnConversation(conversationId, {
                  projectId,
                  operatorId: operatorId.trim(),
                  resumeMode: 'continue',
                })
              )
            }
          >
            <Undo2 size={16} />
            {actionLoading === 'return' ? '处理中…' : '交还控制权'}
          </button>
        )}

        <button
          type="button"
          className="btn btn-ghost"
          disabled={actionLoading !== '' || !detail?.currentWorkflowVersionId}
          onClick={() =>
            runAction('run', () =>
              createWorkflowRun({
                projectId,
                conversationId,
                workflowVersionId: detail.currentWorkflowVersionId,
                triggerType: 'manual',
              })
            )
          }
          title={detail?.currentWorkflowVersionId ? '' : '缺少当前工作流版本'}
        >
          <Play size={16} />
          {actionLoading === 'run' ? '处理中…' : '手动触发运行'}
        </button>

        <button
          type="button"
          className="btn btn-ghost"
          disabled={actionLoading !== '' || !activeRunId}
          onClick={() =>
            runAction('interrupt', () =>
              interruptWorkflowRun(activeRunId, {
                reason: reason.trim() || '手动中断',
                operatorId: operatorId.trim(),
              })
            )
          }
          title={activeRunId ? '' : '无活跃运行'}
        >
          <Pause size={16} />
          {actionLoading === 'interrupt' ? '处理中…' : '中断运行'}
        </button>

        <button
          type="button"
          className="btn btn-ghost"
          disabled={actionLoading !== '' || !activeRunId}
          onClick={() =>
            runAction('resume', () =>
              resumeWorkflowRun(activeRunId, {
                resumeMode: 'continue',
                operatorId: operatorId.trim(),
              })
            )
          }
          title={activeRunId ? '' : '无活跃运行'}
        >
          <RefreshCw size={16} />
          {actionLoading === 'resume' ? '处理中…' : '恢复运行'}
        </button>

        <button
          type="button"
          className="btn btn-ghost"
          disabled={actionLoading !== '' || !activeRunId}
          onClick={() =>
            runAction('cancel', () =>
              cancelWorkflowRun(activeRunId, {
                reason: reason.trim() || '手动取消',
                operatorId: operatorId.trim(),
              })
            )
          }
          title={activeRunId ? '' : '无活跃运行'}
        >
          <X size={16} />
          {actionLoading === 'cancel' ? '处理中…' : '取消运行'}
        </button>
      </div>

      {toast && <div className="handoff-toast">{toast}</div>}

      <p className="handoff-hint text-secondary">
        提示：人工接管后 AI 暂停托管；交还控制权后 AI 按交还模式恢复。运行控制类操作作用于当前活跃运行（
        {activeRunId ? activeRunId.slice(0, 8) : '无'}）。
      </p>
    </div>
  )
}

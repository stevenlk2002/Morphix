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

const HANDOFF_LABEL = {
  none: '无',
  requested: '申请中',
  active: '接管中',
  returning: '交还中',
  returned: '已交还',
}

const OWNER_LABEL = { ai: 'AI', human: '人工' }

export default function HandoffTab({ conversationId, detail, runtime, onChanged, projectId }) {
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

  const handoff = detail?.handoff_status || 'none'
  const ownerType = detail?.owner_type || 'ai'
  const isHandedOff = handoff === 'active' || handoff === 'requested'
  const activeRunId = runtime?.active_run_id || ''

  async function runAction(name, fn) {
    setActionLoading(name)
    setError('')
    try {
      await fn()
      setToast(`${labelOf(name)}成功`)
      setReason('')
      onChanged?.()
    } catch (e) {
      setError(e?.message || `${labelOf(name)}失败`)
    } finally {
      setActionLoading('')
    }
  }

  function labelOf(name) {
    return {
      takeOver: '人工接管',
      return: '交还控制权',
      run: '手动触发运行',
      interrupt: '中断运行',
      resume: '恢复运行',
      cancel: '取消运行',
    }[name] || name
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
          {detail?.latest_handoff?.operator_id && (
            <span className="handoff-status-item">
              <span className="handoff-status-label">操作员</span>
              <span className="mono">{detail.latest_handoff.operator_id}</span>
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
            className="btn btn-danger"
            disabled={actionLoading || !operatorId.trim()}
            onClick={() => runAction('takeOver', () => takeOverConversation(conversationId, {
              projectId, operator_id: operatorId.trim(), reason: reason.trim() || '手动接管',
            }))}
          >
            <Hand size={16} />
            {actionLoading === 'takeOver' ? '处理中…' : '人工接管'}
          </button>
        ) : (
          <button
            className="btn btn-primary"
            disabled={actionLoading || !operatorId.trim()}
            onClick={() => runAction('return', () => returnConversation(conversationId, {
              projectId, operator_id: operatorId.trim(), resume_mode: 'resume_from_state',
            }))}
          >
            <Undo2 size={16} />
            {actionLoading === 'return' ? '处理中…' : '交还控制权'}
          </button>
        )}

        <button
          className="btn btn-ghost"
          disabled={actionLoading || !detail?.current_workflow_version_id}
          onClick={() => runAction('run', () => createWorkflowRun({
            project_id: projectId,
            conversation_id: conversationId,
            workflow_version_id: detail.current_workflow_version_id,
            trigger_type: 'manual',
          }))}
          title={detail?.current_workflow_version_id ? '' : '缺少当前工作流版本'}
        >
          <Play size={16} />
          {actionLoading === 'run' ? '处理中…' : '手动触发运行'}
        </button>

        <button
          className="btn btn-ghost"
          disabled={actionLoading || !activeRunId}
          onClick={() => runAction('interrupt', () => interruptWorkflowRun(activeRunId, {
            reason: reason.trim() || '手动中断', operator_id: operatorId.trim(),
          }))}
          title={activeRunId ? '' : '无活跃运行'}
        >
          <Pause size={16} />
          {actionLoading === 'interrupt' ? '处理中…' : '中断运行'}
        </button>

        <button
          className="btn btn-ghost"
          disabled={actionLoading || !activeRunId}
          onClick={() => runAction('resume', () => resumeWorkflowRun(activeRunId, {
            resume_mode: 'resume_from_state', operator_id: operatorId.trim(),
          }))}
          title={activeRunId ? '' : '无活跃运行'}
        >
          <RefreshCw size={16} />
          {actionLoading === 'resume' ? '处理中…' : '恢复运行'}
        </button>

        <button
          className="btn btn-ghost"
          disabled={actionLoading || !activeRunId}
          onClick={() => runAction('cancel', () => cancelWorkflowRun(activeRunId, {
            reason: reason.trim() || '手动取消', operator_id: operatorId.trim(),
          }))}
          title={activeRunId ? '' : '无活跃运行'}
        >
          <X size={16} />
          {actionLoading === 'cancel' ? '处理中…' : '取消运行'}
        </button>
      </div>

      {toast && <div className="handoff-toast">{toast}</div>}

      <p className="handoff-hint text-secondary">
        提示：人工接管后 AI 暂停托管；交还控制权后 AI 按交还模式恢复。运行控制类操作作用于当前活跃运行（{activeRunId ? activeRunId.slice(0, 8) : '无'}）。
      </p>
    </div>
  )
}

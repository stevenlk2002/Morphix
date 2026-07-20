import { useState, useEffect } from 'react'
import { X, ChevronLeft, ChevronRight, Plus } from 'lucide-react'
import Button from '../../components/common/Button'
import type { ContentBlock, TaskType, ScheduleConfig } from '../../types/operations'
import {
  TASK_TYPE_OPTIONS,
  HOSTING_ACTION_OPTIONS,
  defaultScheduleConfig,
  scheduleConfigToApiFields,
} from '../../types/operations'
import { operationsTasksApi } from '../../api/operations'
import ContentBlockEditor from './components/ContentBlockEditor'
import TargetSelector from './components/TargetSelector'
import ScheduleForm from './components/ScheduleForm'

interface Props {
  open: boolean
  onClose: () => void
  onCreated: () => void
}

/** 显示 toast 提示。 */
function showToast(message: string) {
  const el = document.getElementById('ops-toast')
  if (el) {
    el.textContent = message
    el.classList.add('ops-toast-show')
    setTimeout(() => el.classList.remove('ops-toast-show'), 2500)
  }
}

const STEP_LABELS = ['选择任务类型', '设置任务参数', '选择运营对象', '设置任务运行时间']

export default function OperationTaskCreateModal({ open, onClose, onCreated }: Props) {
  const [step, setStep] = useState(1)

  // Step 1: 类型
  const [taskType, setTaskType] = useState<TaskType>('群发任务')

  // Step 2: 参数
  const [name, setName] = useState('')
  const [channelType, setChannelType] = useState('企业微信')
  const [sessionType, setSessionType] = useState('群聊')
  const [contentBlocks, setContentBlocks] = useState<ContentBlock[]>([])
  const [hostingAction, setHostingAction] = useState('保持不变')

  // Step 3: 对象
  const [selectedSessionIds, setSelectedSessionIds] = useState<string[]>([])
  const [selectedGroupIds, setSelectedGroupIds] = useState<string[]>([])

  // Step 4: 时间
  const [scheduleConfig, setScheduleConfig] = useState<ScheduleConfig>(defaultScheduleConfig())

  const [submitting, setSubmitting] = useState(false)

  // 切换步骤 2 会话类型时清空步骤 3 已选对象
  useEffect(() => {
    setSelectedSessionIds([])
    setSelectedGroupIds([])
  }, [sessionType])

  if (!open) return null

  const reset = () => {
    setStep(1)
    setTaskType('群发任务')
    setName('')
    setChannelType('企业微信')
    setSessionType('群聊')
    setContentBlocks([])
    setHostingAction('保持不变')
    setSelectedSessionIds([])
    setSelectedGroupIds([])
    setScheduleConfig(defaultScheduleConfig())
  }

  const handleClose = () => {
    reset()
    onClose()
  }

  const canNext = (): boolean => {
    switch (step) {
      case 1:
        return !!taskType
      case 2:
        return name.trim().length > 0
      case 3:
        return selectedSessionIds.length > 0 || selectedGroupIds.length > 0
      case 4:
        if (scheduleConfig.type === 'cron') return scheduleConfig.cron.length > 0
        if (scheduleConfig.type === 'once') return scheduleConfig.runTime.length > 0
        return true
      default:
        return false
    }
  }

  const handleCreate = async () => {
    setSubmitting(true)
    try {
      const scheduleFields = scheduleConfigToApiFields(scheduleConfig)
      await operationsTasksApi.create({
        name: name.trim(),
        task_type: taskType,
        channel_type: channelType,
        session_type: sessionType,
        content_blocks: contentBlocks,
        hosting_action: hostingAction,
        ...scheduleFields,
        targets: [
          ...selectedSessionIds.map((sid) => ({
            session_id: sid,
            target_type: 'static',
          })),
          ...selectedGroupIds.map((gid) => ({
            group_id: gid,
            target_type: 'group',
          })),
        ],
      })
      showToast('运营任务创建成功')
      reset()
      onCreated()
    } catch (err) {
      const detail: string = (err as any)?.response?.data?.detail || (err as any)?.message || '未知错误'
      showToast(`创建失败：${detail}`)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="ops-modal-overlay" onClick={(e) => e.target === e.currentTarget && handleClose()}>
      <div className="ops-modal">
        {/* Header */}
        <div className="ops-modal-header">
          <span className="ops-modal-title">创建运营任务</span>
          <button className="btn btn-ghost btn-sm" onClick={handleClose} style={{ padding: 4 }}>
            <X size={18} />
          </button>
        </div>

        {/* Stepper */}
        <div className="ops-stepper">
          {STEP_LABELS.map((label, i) => {
            const num = i + 1
            const isActive = step === num
            const isDone = step > num
            let cls = 'ops-step'
            if (isActive) cls += ' active'
            if (isDone) cls += ' done'
            return (
              <span key={num} style={{ display: 'flex', alignItems: 'center' }}>
                {i > 0 && <span className={`ops-step-line${isDone ? '' : ''}`} />}
                <span className={cls}>
                  <span className="ops-step-num">
                    {isDone ? '✓' : num}
                  </span>
                  {label}
                </span>
              </span>
            )
          })}
        </div>

        {/* Body */}
        <div className="ops-modal-body">
          {/* Step 1: 选择任务类型 */}
          {step === 1 && (
            <div className="ops-form-group">
              <label className="ops-form-label">任务类型</label>
              <div className="ops-type-cards">
                {TASK_TYPE_OPTIONS.map((opt) => (
                  <div
                    key={opt.value}
                    className={`ops-type-card ${taskType === opt.value ? 'selected' : ''}`}
                    onClick={() => setTaskType(opt.value)}
                  >
                    <div className="ops-type-card-icon">{opt.icon}</div>
                    <div className="ops-type-card-label">{opt.label}</div>
                    <div className="ops-type-card-desc">{opt.desc}</div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Step 2: 设置任务参数 */}
          {step === 2 && (
            <>
              <div className="ops-form-group">
                <label className="ops-form-label">
                  任务名称 <span className="required">*</span>
                </label>
                <input
                  className="input"
                  value={name}
                  maxLength={10}
                  placeholder="请输入任务名称"
                  onChange={(e) => setName(e.target.value)}
                />
                <div className={`ops-char-count ${name.length > 10 ? 'over' : ''}`}>
                  {name.length} / 10
                </div>
              </div>

              <div className="ops-form-group">
                <label className="ops-form-label">
                  群发渠道 <span className="required">*</span>
                </label>
                <select className="select" value={channelType} onChange={(e) => setChannelType(e.target.value)}>
                  <option value="企业微信">企业微信</option>
                </select>
              </div>

              <div className="ops-form-group">
                <label className="ops-form-label">
                  会话类型 <span className="required">*</span>
                </label>
                <select className="select" value={sessionType} onChange={(e) => setSessionType(e.target.value)}>
                  <option value="群聊">群聊</option>
                  <option value="单聊">单聊</option>
                </select>
              </div>

              <div className="ops-form-group">
                <label className="ops-form-label">群发内容</label>
                <ContentBlockEditor blocks={contentBlocks} onChange={setContentBlocks} />
              </div>

              <div className="ops-form-group">
                <label className="ops-form-label">
                  运行后托管机器人 <span className="required">*</span>
                </label>
                <select className="select" value={hostingAction} onChange={(e) => setHostingAction(e.target.value)}>
                  <option value="">请选择运行后托管机器人</option>
                  {HOSTING_ACTION_OPTIONS.map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {opt.label}
                    </option>
                  ))}
                </select>
              </div>
            </>
          )}

          {/* Step 3: 选择运营对象 */}
          {step === 3 && (
            <TargetSelector
              sessionType={sessionType === '单聊' ? 'single' : 'group'}
              channel={channelType}
              selectedSessionIds={selectedSessionIds}
              onChange={setSelectedSessionIds}
              selectedGroupIds={selectedGroupIds}
              onGroupChange={setSelectedGroupIds}
            />
          )}

          {/* Step 4: 设置运行时间 */}
          {step === 4 && (
            <ScheduleForm
              value={scheduleConfig}
              onChange={setScheduleConfig}
            />
          )}
        </div>

        {/* Footer */}
        <div className="ops-modal-footer">
          <Button
            variant="secondary"
            size="sm"
            icon={step > 1 ? <ChevronLeft size={14} /> : undefined}
            onClick={() => (step > 1 ? setStep(step - 1) : handleClose())}
          >
            {step > 1 ? '上一步' : '取消'}
          </Button>
          <div style={{ display: 'flex', gap: 8 }}>
            <span style={{ fontSize: 13, color: 'var(--text-tertiary)', alignSelf: 'center' }}>
              {step} / 4
            </span>
            {step < 4 ? (
              <Button
                variant="primary"
                size="sm"
                icon={<ChevronRight size={14} />}
                disabled={!canNext()}
                onClick={() => setStep(step + 1)}
              >
                下一步
              </Button>
            ) : (
              <Button
                variant="primary"
                size="sm"
                icon={<Plus size={14} />}
                disabled={!canNext() || submitting}
                onClick={handleCreate}
              >
                {submitting ? '创建中...' : '创建任务'}
              </Button>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

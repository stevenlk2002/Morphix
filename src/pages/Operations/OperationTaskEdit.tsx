import { useState, useEffect, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { ArrowLeft } from 'lucide-react'
import Button from '../../components/common/Button'
import type { OperationTaskDetail, ContentBlock, ScheduleConfig } from '../../types/operations'
import {
  HOSTING_ACTION_OPTIONS,
  defaultScheduleConfig,
  apiFieldsToScheduleConfig,
  scheduleConfigToApiFields,
} from '../../types/operations'
import { operationsTasksApi } from '../../api/operations'
import ContentBlockEditor from './components/ContentBlockEditor'
import TargetSelector from './components/TargetSelector'
import ScheduleForm from './components/ScheduleForm'
import './OperationTasks.css'

function showToast(message: string) {
  const el = document.getElementById('ops-toast')
  if (el) {
    el.textContent = message
    el.classList.add('ops-toast-show')
    setTimeout(() => el.classList.remove('ops-toast-show'), 2500)
  }
}

type EditTab = 'params' | 'targets' | 'schedule'

export default function OperationTaskEditPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()

  const [task, setTask] = useState<OperationTaskDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [tab, setTab] = useState<EditTab>('params')
  const [saving, setSaving] = useState(false)

  // 编辑态字段
  const [name, setName] = useState('')
  const [channelType, setChannelType] = useState('企业微信')
  const [sessionType, setSessionType] = useState('群聊')
  const [contentBlocks, setContentBlocks] = useState<ContentBlock[]>([])
  const [hostingAction, setHostingAction] = useState('保持不变')
  const [selectedSessionIds, setSelectedSessionIds] = useState<string[]>([])
  const [selectedGroupIds, setSelectedGroupIds] = useState<string[]>([])
  const [scheduleConfig, setScheduleConfig] = useState<ScheduleConfig>(defaultScheduleConfig())

  /** 加载任务详情 */
  const loadTask = useCallback(async () => {
    if (!id) return
    setLoading(true)
    try {
      const data = await operationsTasksApi.get(id)
      setTask(data)
      // 回填表单
      setName(data.name || '')
      setChannelType(data.channel_type || '企业微信')
      setSessionType(data.session_type || '群聊')
      setContentBlocks(data.content_blocks || [])
      setHostingAction(data.hosting_action || '保持不变')
      setScheduleConfig(apiFieldsToScheduleConfig(data))
      setSelectedSessionIds(
        (data.targets || [])
          .filter((t) => t.target_type !== 'group')
          .map((t) => t.session_id)
      )
      setSelectedGroupIds(
        (data.targets || [])
          .filter((t) => t.target_type === 'group')
          .map((t) => t.group_id || t.session_id)
      )
    } catch (err) {
      console.error('加载任务详情失败:', err)
      showToast('加载失败')
      navigate('/operations/tasks')
    } finally {
      setLoading(false)
    }
  }, [id, navigate])

  useEffect(() => {
    loadTask()
  }, [loadTask])

  /** 保存 */
  const handleSave = async () => {
    if (!id) return
    setSaving(true)
    try {
      const scheduleFields = scheduleConfigToApiFields(scheduleConfig)
      // 保存参数 + 时间
      await operationsTasksApi.update(id, {
        name: name.trim(),
        channel_type: channelType,
        session_type: sessionType,
        content_blocks: contentBlocks,
        hosting_action: hostingAction,
        ...scheduleFields,
      })

      // 保存运营对象
      await operationsTasksApi.setTargets(
        id,
        [
          ...selectedSessionIds.map((sid) => ({ session_id: sid, target_type: 'static' })),
          ...selectedGroupIds.map((gid) => ({ group_id: gid, target_type: 'group' })),
        ]
      )

      showToast('保存成功')
      navigate('/operations/tasks')
    } catch (err) {
      console.error('保存失败:', err)
      showToast('保存失败，请重试')
    } finally {
      setSaving(false)
    }
  }

  if (loading) {
    return (
      <div className="proto-page">
        <div style={{ textAlign: 'center', padding: 48, color: 'var(--text-secondary)' }}>
          加载中...
        </div>
      </div>
    )
  }

  if (!task) {
    return (
      <div className="proto-page">
        <div style={{ textAlign: 'center', padding: 48, color: 'var(--text-secondary)' }}>
          任务不存在
        </div>
      </div>
    )
  }

  return (
    <div className="proto-page">
      {/* 返回栏 */}
      <div className="ops-edit-header">
        <button
          className="ops-edit-back"
          onClick={() => navigate('/operations/tasks')}
          aria-label="返回列表"
        >
          <ArrowLeft size={20} />
        </button>
        <span className="ops-edit-title">编辑：{task.name}</span>
      </div>

      {/* Tab 切换 */}
      <div className="ops-edit-tabs">
        {(['params', 'targets', 'schedule'] as EditTab[]).map((t) => (
          <div
            key={t}
            className={`ops-edit-tab ${tab === t ? 'active' : ''}`}
            onClick={() => setTab(t)}
          >
            {t === 'params' ? '任务参数' : t === 'targets' ? '运营对象' : '任务时间'}
          </div>
        ))}
      </div>

      {/* Tab 内容 */}
      {tab === 'params' && (
        <div style={{ maxWidth: 700 }}>
          <div className="ops-form-group">
            <label className="ops-form-label">
              任务名称 <span className="required">*</span>
            </label>
            <input
              className="input"
              value={name}
              maxLength={10}
              onChange={(e) => setName(e.target.value)}
            />
            <div className={`ops-char-count ${name.length > 10 ? 'over' : ''}`}>
              {name.length} / 10
            </div>
          </div>
          <div className="ops-form-group">
            <label className="ops-form-label">群发渠道</label>
            <select className="select" value={channelType} onChange={(e) => setChannelType(e.target.value)}>
              <option value="企业微信">企业微信</option>
            </select>
          </div>
          <div className="ops-form-group">
            <label className="ops-form-label">会话类型</label>
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
            <label className="ops-form-label">运行后托管机器人</label>
            <select className="select" value={hostingAction} onChange={(e) => setHostingAction(e.target.value)}>
              {HOSTING_ACTION_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>{opt.label}</option>
              ))}
            </select>
          </div>
        </div>
      )}

      {tab === 'targets' && (
        <TargetSelector
          sessionType={sessionType === '单聊' ? 'single' : 'group'}
          channel={channelType}
          selectedSessionIds={selectedSessionIds}
          onChange={setSelectedSessionIds}
          selectedGroupIds={selectedGroupIds}
          onGroupChange={setSelectedGroupIds}
          taskId={id}
        />
      )}

      {tab === 'schedule' && (
        <div style={{ maxWidth: 600 }}>
          <ScheduleForm
            value={scheduleConfig}
            onChange={setScheduleConfig}
          />
        </div>
      )}

      {/* 保存按钮 */}
      <div style={{ marginTop: 24, display: 'flex', gap: 12 }}>
        <Button variant="primary" size="sm" onClick={handleSave} disabled={saving}>
          {saving ? '保存中...' : '保存'}
        </Button>
        <Button variant="ghost" size="sm" onClick={() => navigate('/operations/tasks')}>
          取消
        </Button>
      </div>

      {/* Toast */}
      <div id="ops-toast" className="ops-toast" />
    </div>
  )
}

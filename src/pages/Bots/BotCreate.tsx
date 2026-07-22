import { Fragment, useState, type ReactNode } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import Button from '../../components/common/Button'
import { toast, errText } from '../../utils/toast'
import { botsApi } from '../../api/client'
import './BotCreate.css'

/** 向导步骤序号（1-based）。 */
type Step = 1 | 2 | 3

/** 模板模式选中的机器人类型。 */
type TemplateType = 'qa' | 'reception' | null

/** 创建机器人请求体（对齐后端 BotCreateRequest）。 */
interface BotCreatePayload {
  name: string
  project: string
  workflow: string
  tone: string
  trainingPrompt: string
}

interface StepperProps {
  /** 当前激活步骤（1-based）。 */
  current: number
  /** 步骤标题数组，如 ['选择机器人工作流程', '设置机器人名称', '创建完成！进一步训练']。 */
  steps: string[]
}

/**
 * 步骤条（复用原型 .stepper 渲染规则）。
 * - 步号 < current：done 态，显示 ✓。
 * - 步号 == current：active 态。
 * - 步号 > current：普通态。
 */
function Stepper({ current, steps }: StepperProps) {
  return (
    <div className="stepper">
      {steps.map((label, idx) => {
        const num = idx + 1
        let state = ''
        let content: ReactNode = num
        if (num < current) {
          state = 'done'
          content = '✓'
        } else if (num === current) {
          state = 'active'
        }
        return (
          <Fragment key={label}>
            {idx > 0 && <div className="step-line" />}
            <div className={`step ${state}`.trim()}>
              <div className="step-num">{content}</div>
              <span>{label}</span>
            </div>
          </Fragment>
        )
      })}
    </div>
  )
}

/** 模板模式三步标题。 */
const TEMPLATE_STEPS = ['选择机器人工作流程', '设置机器人名称', '创建完成！进一步训练']

/** 编排模式三步标题。 */
const ORCHESTRATE_STEPS = ['选择编排入口', '编排流程', '保存上线']

/** 成功插画（对应原型 svgIllustration('success')），颜色复用主题变量。 */
function SuccessIllustration() {
  return (
    <svg
      className="create-illus-svg"
      viewBox="0 0 200 200"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      role="img"
      aria-label="创建成功"
    >
      <circle cx="100" cy="100" r="70" fill="var(--success-bg)" />
      <circle cx="100" cy="100" r="50" fill="#ffffff" stroke="var(--success)" strokeWidth="3" />
      <path
        d="M78 100l16 16 32-36"
        stroke="var(--success)"
        strokeWidth="5"
        fill="none"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <circle cx="160" cy="50" r="12" fill="var(--primary-light)" />
      <circle cx="40" cy="60" r="8" fill="var(--success-bg)" />
      <circle cx="50" cy="150" r="10" fill="var(--primary-light)" />
    </svg>
  )
}

/** 机器人插画（对应原型 svgIllustration('robot')），颜色复用主题变量。 */
function RobotIllustration() {
  return (
    <svg
      className="create-illus-svg"
      viewBox="0 0 200 200"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      role="img"
      aria-label="机器人"
    >
      <circle cx="100" cy="70" r="40" fill="var(--primary-light)" />
      <rect x="60" y="110" width="80" height="70" rx="14" fill="#ffffff" stroke="var(--border)" strokeWidth="2" />
      <circle cx="85" cy="65" r="5" fill="var(--primary)" />
      <circle cx="115" cy="65" r="5" fill="var(--primary)" />
      <path d="M88 88q12 10 24 0" stroke="var(--primary)" strokeWidth="3" fill="none" strokeLinecap="round" />
      <rect x="90" y="35" width="20" height="12" rx="4" fill="var(--primary)" />
      <rect x="30" y="125" width="20" height="40" rx="6" fill="var(--primary-light)" />
      <rect x="150" y="125" width="20" height="40" rx="6" fill="var(--primary-light)" />
    </svg>
  )
}

/** 根据模板类型组装创建请求体。 */
function buildTemplatePayload(type: TemplateType, name: string): BotCreatePayload {
  const base: BotCreatePayload = {
    name: name.trim(),
    project: 'Morphix',
    workflow: '知识库问答流程',
    tone: '亲切专业',
    trainingPrompt: '',
  }
  if (type === 'reception') {
    base.workflow = '接待主流程'
  }
  return base
}

/**
 * 创建机器人向导页（/bots/create）。
 * - mode=template（默认）：三步向导（选模板 → 命名 → 完成）。
 * - mode=orchestrate：单页（从编排创建）。
 * 真实接入后端 POST /api/bots，彻底移除演示占位。
 */
export default function BotCreatePage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const mode = searchParams.get('mode') === 'orchestrate' ? 'orchestrate' : 'template'

  // 模板模式三步向导状态
  const [step, setStep] = useState<Step>(1)
  const [selectedType, setSelectedType] = useState<TemplateType>(null)
  const [name, setName] = useState('')
  const [creating, setCreating] = useState(false)
  const [createdId, setCreatedId] = useState<string>('')

  const goList = () => navigate('/bots')

  /** 模板模式：提交创建请求。 */
  const handleCreate = async () => {
    if (!name.trim()) {
      toast('请先为机器人起一个名字')
      return
    }
    const payload = buildTemplatePayload(selectedType, name)
    setCreating(true)
    try {
      const created = (await botsApi.create(payload)) as { id?: string }
      const id = created.id ?? ''
      if (!id) {
        toast('创建失败：未返回机器人ID')
        return
      }
      setCreatedId(id)
      setStep(3)
    } catch (e) {
      toast(`创建失败：${errText(e)}`)
    } finally {
      setCreating(false)
    }
  }

  /** 编排模式：提交创建请求并跳转到编排台。 */
  const handleOrchestrateCreate = async () => {
    const payload: BotCreatePayload = {
      name: '我的编排机器人',
      project: 'Morphix',
      workflow: '自定义编排流程',
      tone: '亲切专业',
      trainingPrompt: '',
    }
    setCreating(true)
    try {
      const created = (await botsApi.create(payload)) as { id?: string }
      const id = created.id ?? ''
      if (!id) {
        toast('创建失败：未返回机器人ID')
        return
      }
      navigate(`/bots/${id}/orchestrate`)
    } catch (e) {
      toast(`创建失败：${errText(e)}`)
    } finally {
      setCreating(false)
    }
  }

  // ===== 编排模式（单页） =====
  if (mode === 'orchestrate') {
    return (
      <div className="create-page">
        <Stepper current={1} steps={ORCHESTRATE_STEPS} />
        <div className="create-card create-card--md create-done">
          <div className="create-illus">
            <RobotIllustration />
          </div>
          <h3 className="create-done-title">从编排创建机器人</h3>
          <p className="create-done-desc">
            通过拖拽节点，从零开始设计机器人的对话流程与业务逻辑。
          </p>
          <div className="create-actions create-actions--center">
            <Button variant="secondary" size="md" onClick={goList}>
              上一步
            </Button>
            <Button
              variant="primary"
              size="lg"
              onClick={handleOrchestrateCreate}
              disabled={creating}
            >
              {creating ? '生成中…' : '开始编排'}
            </Button>
          </div>
        </div>
      </div>
    )
  }

  // ===== 模板模式（三步向导） =====
  return (
    <div className="create-page">
      <Stepper current={step} steps={TEMPLATE_STEPS} />

      {/* 步骤1：选择机器人模板 */}
      {step === 1 && (
        <div className="create-card create-card--wide">
          <div style={{ textAlign: 'center', marginBottom: 24 }}>
            <h3 className="create-title">请选择一个机器人，以开始创建</h3>
          </div>
          <div className="tpl-grid">
            <button
              type="button"
              className={`tpl-card ${selectedType === 'qa' ? 'selected' : ''}`}
              onClick={() => setSelectedType('qa')}
            >
              <div className="tpl-illus tpl-illus--qa">
                <span className="tpl-illus-icon">?</span>
              </div>
              <div className="tpl-name">问答机器人</div>
              <div className="tpl-meta">根据知识库，进行问答的机器人</div>
            </button>
            <button
              type="button"
              className={`tpl-card ${selectedType === 'reception' ? 'selected' : ''}`}
              onClick={() => setSelectedType('reception')}
            >
              <div className="tpl-illus tpl-illus--reception">
                <span className="tpl-illus-icon">☺</span>
              </div>
              <div className="tpl-name">接待机器人</div>
              <div className="tpl-meta">按接待流程对用户进行基础接待</div>
            </button>
          </div>
          <div className="create-actions">
            <Button variant="secondary" size="md" onClick={goList}>
              上一步
            </Button>
            <Button
              variant="primary"
              size="md"
              onClick={() => setStep(2)}
              disabled={!selectedType}
            >
              下一步
            </Button>
          </div>
        </div>
      )}

      {/* 步骤2：设置机器人名称 */}
      {step === 2 && (
        <div className="create-card create-card--md">
          <h3 className="create-title">给你的机器人取个名字吧！</h3>
          <p className="create-subtitle">
            起名建议：品牌名+核心功能描述+机器人，如雀巢售后客服机器人、蜗牛保险销售机器人等
          </p>
          <div className="create-name-field">
            <input
              id="botNameInput"
              className="create-name-input"
              placeholder="请起一个能体现机器人功能的名字（仅自己可见，客户不可见）"
              maxLength={30}
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </div>
          <div id="botNameCount" className="create-name-count">
            {name.length} / 30
          </div>
          <div className="create-actions">
            <Button variant="secondary" size="md" onClick={() => setStep(1)}>
              上一步
            </Button>
            <Button
              variant="primary"
              size="md"
              onClick={handleCreate}
              disabled={creating}
            >
              {creating ? '生成中…' : 'AI生成机器人'}
            </Button>
          </div>
        </div>
      )}

      {/* 步骤3：创建完成 */}
      {step === 3 && (
        <div className="create-card create-card--narrow create-done">
          <div className="create-illus">
            <SuccessIllustration />
          </div>
          <h3 className="create-done-title">
            <span className="star">✦</span> 恭喜！您的机器人已创建完成~
          </h3>
          <p className="create-done-desc">
            但它还需要进一步的知识和训练才能正式开始工作哦！
            <br />
            请继续前往训练吧！
          </p>
          <div className="create-actions create-actions--center">
            <Button
              variant="primary"
              size="lg"
              onClick={() => navigate(`/bots/${createdId}`)}
            >
              前往训练机器人
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}

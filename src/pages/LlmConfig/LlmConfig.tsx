import { useState } from 'react'
import { Eye, EyeOff, Check, Save, RefreshCw, Info, AlertCircle } from 'lucide-react'
import Button from '../../components/common/Button'
import type { LlmModelConfig } from '../../types/resource'
import '../../pages/prototype.css'
import './LlmConfig.css'

/** 完整模型配置（含 enabled 必填字段）。 */
type FullModelConfig = LlmModelConfig & { enabled: boolean }

/** 厂商 -> 可选模型名映射，随厂商选择联动模型下拉框。 */
const VENDOR_MODELS: Record<string, string[]> = {
  OpenAI: ['GPT-4o', 'GPT-4o mini', 'GPT-4 Turbo'],
  Anthropic: ['Claude 3.5 Sonnet', 'Claude 3 Opus', 'Claude 3 Haiku'],
  阿里云: ['通义千问-Max', '通义千问-Plus', '通义千问-Turbo'],
  百度: ['文心一言 4.0', '文心一言 3.5'],
}

const VENDORS: string[] = Object.keys(VENDOR_MODELS)

/** 主模型种子数据（已启用）。 */
const DEFAULT_PRIMARY: FullModelConfig = {
  vendor: 'OpenAI',
  model: 'GPT-4o',
  apiKey: 'sk-orchestrator-7f3a9c2e1b4d',
  apiBaseUrl: 'https://api.openai.com/v1',
  enabled: true,
}

/** 副模型种子数据（未配置）。 */
const DEFAULT_SECONDARY: FullModelConfig = {
  vendor: 'Anthropic',
  model: 'Claude 3.5 Sonnet',
  apiKey: '',
  apiBaseUrl: '',
  enabled: false,
}

interface ModelCardProps {
  /** 主 / 副 标记。 */
  roleLabel: string
  /** 角色徽标样式类（model-role-primary / model-role-secondary）。 */
  roleBadgeClass: string
  /** 卡片标题。 */
  title: string
  /** 状态文案（已启用 / 未配置）。 */
  statusLabel: string
  /** 状态徽标变体。 */
  statusVariant: 'success' | 'neutral'
  /** 当前受控配置。 */
  config: FullModelConfig
  /** 配置变更回调（受控）。 */
  onChange: (next: FullModelConfig) => void
  /** 是否在底部展示"连接正常"标识（主模型默认展示）。 */
  showConnectionOk?: boolean
}

/**
 * 单张模型配置卡片（主 / 副共用）。
 * 表单通过 props.config + onChange 完成受控，本地仅维护 UI 态（显示密钥、测试中、结果提示）。
 */
function ModelCard({
  roleLabel,
  roleBadgeClass,
  title,
  statusLabel,
  statusVariant,
  config,
  onChange,
  showConnectionOk = false,
}: ModelCardProps) {
  const [showKey, setShowKey] = useState(false)
  const [testing, setTesting] = useState(false)
  const [testOk, setTestOk] = useState(false)
  const [testError, setTestError] = useState(false)
  const [saved, setSaved] = useState(false)

  const patch = (next: Partial<FullModelConfig>) => {
    onChange({ ...config, ...next })
    setSaved(false)
  }

  const handleVendorChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const vendor = e.target.value
    // 切换厂商时，模型自动重置为该厂商首个模型
    patch({ vendor, model: VENDOR_MODELS[vendor][0] })
  }

  const toggleKeyVisibility = () => setShowKey((v) => !v)

  const handleTest = () => {
    if (!config.apiKey.trim()) {
      setTestError(true)
      setTestOk(false)
      return
    }
    setTestError(false)
    setTesting(true)
    setTestOk(false)
    // 模拟异步连接测试
    window.setTimeout(() => {
      setTesting(false)
      setTestOk(true)
    }, 900)
  }

  const handleSave = () => {
    setSaved(true)
    setTestError(false)
  }

  return (
    <div className="proto-card model-card">
      <div className="model-card-head">
        <span className="model-card-title">
          <span className={`model-role-badge ${roleBadgeClass}`}>{roleLabel}</span>
          {title}
        </span>
        <span className={`proto-badge proto-badge-${statusVariant}`}>{statusLabel}</span>
      </div>

      <div className="form-group">
        <label className="form-label">
          模型厂商 <span className="required">*</span>
        </label>
        <select className="select" value={config.vendor} onChange={handleVendorChange}>
          {VENDORS.map((v) => (
            <option key={v} value={v}>
              {v}
            </option>
          ))}
        </select>
      </div>

      <div className="form-group">
        <label className="form-label">
          模型 <span className="required">*</span>
        </label>
        <select
          className="select"
          value={config.model}
          onChange={(e) => patch({ model: e.target.value })}
        >
          {VENDOR_MODELS[config.vendor].map((m) => (
            <option key={m} value={m}>
              {m}
            </option>
          ))}
        </select>
      </div>

      <div className="form-group">
        <label className="form-label">
          API Key <span className="required">*</span>
        </label>
        <div className="input-affix">
          <input
            className="input"
            type={showKey ? 'text' : 'password'}
            value={config.apiKey}
            placeholder={`请输入 ${config.vendor} API Key`}
            onChange={(e) => patch({ apiKey: e.target.value })}
          />
          <button
            type="button"
            className="affix-btn"
            title="显示 / 隐藏"
            aria-label="显示或隐藏 API Key"
            onClick={toggleKeyVisibility}
          >
            {showKey ? <EyeOff size={16} /> : <Eye size={16} />}
          </button>
        </div>
        <div className="form-hint">请填写对应厂商开放平台获取的 API Key，密钥将以加密方式存储。</div>
      </div>

      <div className="form-group">
        <label className="form-label">API 地址（可选）</label>
        <input
          className="input"
          type="text"
          value={config.apiBaseUrl ?? ''}
          placeholder="https://api.example.com/v1"
          onChange={(e) => patch({ apiBaseUrl: e.target.value })}
        />
      </div>

      <div className="proto-actions model-actions">
        <Button
          variant="secondary"
          size="sm"
          icon={<RefreshCw size={14} className={testing ? 'spin' : undefined} />}
          disabled={testing}
          onClick={handleTest}
        >
          {testing ? '测试中…' : '测试连接'}
        </Button>
        <Button variant="primary" size="sm" icon={<Save size={14} />} onClick={handleSave}>
          保存配置
        </Button>
        {showConnectionOk && testOk && (
          <span className="model-ok">
            <Check size={14} /> 连接正常
          </span>
        )}
      </div>

      {saved && (
        <div className="proto-notice proto-notice-success">
          <Check size={14} /> {roleLabel}模型配置已保存
        </div>
      )}
      {testOk && !saved && (
        <div className="proto-notice proto-notice-success">
          <Check size={14} /> 连接测试成功
        </div>
      )}
      {testError && (
        <div className="proto-notice proto-notice-error">
          <AlertCircle size={14} /> 请先填写 API Key 再进行连接测试
        </div>
      )}
    </div>
  )
}

/**
 * LLM 配置页（/llm-config）。
 * mock-first：使用种子数据 + 本地受控状态实现完整交互，不依赖后端。
 */
export default function LlmConfigPage() {
  const [primary, setPrimary] = useState<FullModelConfig>(DEFAULT_PRIMARY)
  const [secondary, setSecondary] = useState<FullModelConfig>(DEFAULT_SECONDARY)

  return (
    <div className="proto-page proto-page-narrow">
      <div className="page-header">
        <div>
          <h2 className="page-title">LLM 配置</h2>
          <p className="page-subtitle">
            配置主、副大模型用于机器人推理。系统优先调用主模型，主模型失败 / 超时 / 限流时自动切换至副模型，保障服务连续性。
          </p>
        </div>
      </div>

      <div className="proto-tip">
        <Info size={16} />
        <div>
          <strong>默认支持模型：</strong>
          OpenAI（GPT-4o）、Anthropic（Claude 3.5）、阿里云（通义千问-Max）、百度（文心一言 4.0）。API Key 仅保存于当前租户，平台不会用于其他用途。
        </div>
      </div>

      <ModelCard
        roleLabel="主"
        roleBadgeClass="model-role-primary"
        title="主模型"
        statusLabel="已启用"
        statusVariant="success"
        config={primary}
        showConnectionOk
        onChange={setPrimary}
      />

      <ModelCard
        roleLabel="副"
        roleBadgeClass="model-role-secondary"
        title="副模型（备用）"
        statusLabel="未配置"
        statusVariant="neutral"
        config={secondary}
        onChange={setSecondary}
      />
    </div>
  )
}

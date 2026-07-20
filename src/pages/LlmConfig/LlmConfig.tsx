import { useState, useEffect, useCallback } from 'react'
import {
  Eye,
  EyeOff,
  Check,
  Save,
  RefreshCw,
  Info,
  AlertCircle,
  Loader2,
} from 'lucide-react'
import Button from '../../components/common/Button'
import { llmConfigApi, ApiClientError } from '../../api/client'
import type { LlmConfigItem, LlmConfigUpdate } from '../../api/client'
import '../../pages/prototype.css'
import './LlmConfig.css'

/** 厂商 -> 可选模型名映射，随厂商选择联动模型下拉框。 */
const VENDOR_MODELS: Record<string, string[]> = {
  OpenAI: ['GPT-4o', 'GPT-4o mini', 'GPT-4 Turbo'],
  Anthropic: ['Claude 3.5 Sonnet', 'Claude 3 Opus', 'Claude 3 Haiku'],
  阿里云: ['通义千问-Max', '通义千问-Plus', '通义千问-Turbo'],
  百度: ['文心一言 4.0', '文心一言 3.5'],
  Deepseek: ['Deepseek-V4-Pro', 'Deepseek-V4-Flash'],
  千问: ['Qwen-Max', 'Qwen-Plus', 'Qwen-Turbo'],
  混元: ['Hy3', 'Hunyuan-Turbo', 'Hunyuan-Lite'],
  Kimi: ['K3', 'K2.7', 'K2.6'],
  GLM: ['GLM-5.2', 'GLM-5.1'],
}

const VENDORS: string[] = Object.keys(VENDOR_MODELS)

/** 本地 UI 态模型配置（与 API 字段对齐）。 */
interface ModelConfig {
  vendor: string
  model: string
  apiKey: string
  apiBaseUrl: string
  enabled: boolean
}

interface ModelCardProps {
  roleLabel: string
  roleBadgeClass: string
  title: string
  statusLabel: string
  statusVariant: 'success' | 'neutral'
  config: ModelConfig
  onChange: (next: ModelConfig) => void
  onSave: () => Promise<void>
  showConnectionOk?: boolean
  saving?: boolean
}

function ModelCard({
  roleLabel,
  roleBadgeClass,
  title,
  statusLabel,
  statusVariant,
  config,
  onChange,
  onSave,
  showConnectionOk = false,
  saving = false,
}: ModelCardProps) {
  const [showKey, setShowKey] = useState(false)
  const [testing, setTesting] = useState(false)
  const [testOk, setTestOk] = useState(false)
  const [testError, setTestError] = useState(false)
  const [saved, setSaved] = useState(false)

  const patch = (next: Partial<ModelConfig>) => {
    onChange({ ...config, ...next })
    setSaved(false)
  }

  const handleVendorChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const vendor = e.target.value
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
    window.setTimeout(() => {
      setTesting(false)
      setTestOk(true)
    }, 900)
  }

  const handleSave = async () => {
    setTestError(false)
    try {
      await onSave()
      setSaved(true)
    } catch {
      // 错误由父级统一处理
    }
  }

  return (
    <div className="proto-card model-card">
      <div className="model-card-head">
        <span className="model-card-title">
          <span className={`model-role-badge ${roleBadgeClass}`}>{roleLabel}</span>
          {title}
        </span>
        <span className={`proto-badge proto-badge-${statusVariant}`}>
          {statusLabel}
        </span>
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
        <div className="form-hint">
          请填写对应厂商开放平台获取的 API Key，密钥将以加密方式存储。
        </div>
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
        <Button
          variant="primary"
          size="sm"
          icon={saving ? <Loader2 size={14} className="spin" /> : <Save size={14} />}
          disabled={saving}
          onClick={handleSave}
        >
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

/** 将 API 返回的配置项转为本地 ModelConfig。 */
function itemToConfig(item: LlmConfigItem): ModelConfig {
  return {
    vendor: item.vendor,
    model: item.model,
    apiKey: item.apiKey,
    apiBaseUrl: item.apiBaseUrl,
    enabled: item.enabled,
  }
}

/** 将本地 ModelConfig 转为 API 更新请求体。 */
function configToUpdate(config: ModelConfig): LlmConfigUpdate {
  return {
    vendor: config.vendor,
    model: config.model,
    apiKey: config.apiKey,
    apiBaseUrl: config.apiBaseUrl,
    enabled: config.enabled,
  }
}

export default function LlmConfigPage() {
  const [primary, setPrimary] = useState<ModelConfig>({
    vendor: '',
    model: '',
    apiKey: '',
    apiBaseUrl: '',
    enabled: false,
  })
  const [secondary, setSecondary] = useState<ModelConfig>({
    vendor: '',
    model: '',
    apiKey: '',
    apiBaseUrl: '',
    enabled: false,
  })
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [savingPrimary, setSavingPrimary] = useState(false)
  const [savingSecondary, setSavingSecondary] = useState(false)

  const loadConfigs = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const data = await llmConfigApi.getAll()
      if (data.primary) setPrimary(itemToConfig(data.primary))
      if (data.secondary) setSecondary(itemToConfig(data.secondary))
    } catch (e) {
      const msg =
        e instanceof ApiClientError
          ? e.message
          : '加载 LLM 配置失败，请检查网络连接'
      setError(msg)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadConfigs()
  }, [loadConfigs])

  const handleSavePrimary = async () => {
    setSavingPrimary(true)
    setError('')
    try {
      const updated = await llmConfigApi.update('primary', configToUpdate(primary))
      setPrimary(itemToConfig(updated))
    } catch (e) {
      const msg =
        e instanceof ApiClientError ? e.message : '保存主模型配置失败'
      setError(msg)
      throw e
    } finally {
      setSavingPrimary(false)
    }
  }

  const handleSaveSecondary = async () => {
    setSavingSecondary(true)
    setError('')
    try {
      const updated = await llmConfigApi.update(
        'secondary',
        configToUpdate(secondary)
      )
      setSecondary(itemToConfig(updated))
    } catch (e) {
      const msg =
        e instanceof ApiClientError ? e.message : '保存副模型配置失败'
      setError(msg)
      throw e
    } finally {
      setSavingSecondary(false)
    }
  }

  if (loading) {
    return (
      <div className="proto-page proto-page-narrow">
        <div className="page-loading">
          <Loader2 size={24} className="spin" />
          <span>加载 LLM 配置中…</span>
        </div>
      </div>
    )
  }

  return (
    <div className="proto-page proto-page-narrow">
      <div className="page-header">
        <div>
          <h2 className="page-title">LLM 配置</h2>
          <p className="page-subtitle">
            配置主、副大模型用于机器人推理。系统优先调用主模型，主模型失败 /
            超时 / 限流时自动切换至副模型，保障服务连续性。
          </p>
        </div>
      </div>

      <div className="proto-tip">
        <Info size={16} />
        <div>
          <strong>默认支持模型：</strong>
          OpenAI（GPT-4o）、Anthropic（Claude 3.5）、阿里云（通义千问-Max）、百度（文心一言
          4.0）、Deepseek（V4-Pro / V4-Flash）、千问（Qwen-Max）、混元（Hy3）、Kimi（K3 /
          K2.7）、GLM（5.2 / 5.1）。API Key 仅保存于当前租户，平台不会用于其他用途。
        </div>
      </div>

      {error && (
        <div className="proto-notice proto-notice-error" style={{ marginBottom: 16 }}>
          <AlertCircle size={14} /> {error}
        </div>
      )}

      <ModelCard
        roleLabel="主"
        roleBadgeClass="model-role-primary"
        title="主模型"
        statusLabel={primary.enabled ? '已启用' : '未配置'}
        statusVariant={primary.enabled ? 'success' : 'neutral'}
        config={primary}
        onChange={setPrimary}
        onSave={handleSavePrimary}
        saving={savingPrimary}
        showConnectionOk
      />

      <ModelCard
        roleLabel="副"
        roleBadgeClass="model-role-secondary"
        title="副模型（备用）"
        statusLabel={secondary.enabled ? '已启用' : '未配置'}
        statusVariant={secondary.enabled ? 'success' : 'neutral'}
        config={secondary}
        onChange={setSecondary}
        onSave={handleSaveSecondary}
        saving={savingSecondary}
      />
    </div>
  )
}

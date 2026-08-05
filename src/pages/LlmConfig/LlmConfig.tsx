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
  Deepseek: ['deepseek-v4-pro', 'deepseek-v4-flash'],
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
  /** true 表示服务端已有密钥（GET 返回的脱敏占位符），本地未改动；保存时不应把占位符回传。 */
  apiKeyMasked: boolean
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
  configId: string                    /** 'primary' | 'secondary' — 用于调用后端 test 接口 */
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
  configId,
  onChange,
  onSave,
  showConnectionOk = false,
  saving = false,
}: ModelCardProps) {
  const [showKey, setShowKey] = useState(false)
  const [testing, setTesting] = useState(false)
  const [testOk, setTestOk] = useState(false)
  const [testError, setTestError] = useState(false)
  const [testErrorMsg, setTestErrorMsg] = useState('')
  const [saved, setSaved] = useState(false)

  const patch = (next: Partial<ModelConfig>) => {
    onChange({ ...config, ...next })
    setSaved(false)
  }

  /**
   * 当前厂商可选模型列表。
   * 注意：vendor 可能是空串（后端未配置）或静态映射外的厂商（如 DB 里存了「智谱 / Ollama」），
   * 此处必须兜底为空数组，否则 `.map` 会抛 TypeError 导致整页白屏。
   */
  const models: string[] = VENDOR_MODELS[config.vendor] ?? []
  const isKnownVendor: boolean = VENDORS.includes(config.vendor)
  /** 若当前 model 不在候选列表中，补进选项，避免受控 select 值与 UI 显示不一致。 */
  const modelOptions: string[] =
    config.model && models.length > 0 && !models.includes(config.model)
      ? [config.model, ...models]
      : models

  const handleVendorChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const vendor = e.target.value
    // 未知厂商同样兜底，避免下标访问 undefined。
    const nextModel = (VENDOR_MODELS[vendor] ?? [])[0] ?? ''
    patch({ vendor, model: nextModel })
  }

  const toggleKeyVisibility = () => setShowKey((v) => !v)

  const handleTest = async () => {
    // 即使 apiKeyMasked=true（本地无 key），后端 test 接口会用 DB 中的真实密钥测试
    setTestError(false)
    setTestErrorMsg('')
    setTestOk(false)
    setTesting(true)
    try {
      const res = await llmConfigApi.testConnection(configId)
      if (res.ok) {
        setTestOk(true)
      } else {
        setTestError(true)
        setTestErrorMsg(res.message || '连接测试失败')
      }
    } catch (e) {
      setTestError(true)
      setTestErrorMsg(e instanceof ApiClientError ? e.message : '网络异常，请检查后端服务')
    } finally {
      setTesting(false)
    }
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
        <select
          className="select"
          value={config.vendor}
          onChange={handleVendorChange}
          aria-label="模型厂商"
        >
          <option value="" disabled>
            请选择厂商
          </option>
          {!isKnownVendor && config.vendor !== '' && (
            <option value={config.vendor}>{config.vendor}</option>
          )}
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
        {modelOptions.length === 0 ? (
          // 厂商为空或不在静态映射中：降级为只读输入框，既不崩溃又能看到已存的 model 值。
          <input
            className="input"
            type="text"
            aria-label="模型"
            value={config.model ?? ''}
            placeholder="请先选择厂商"
            readOnly
            disabled
          />
        ) : (
          <select
            className="select"
            value={config.model}
            onChange={(e) => patch({ model: e.target.value })}
            aria-label="模型"
          >
            {modelOptions.map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))}
          </select>
        )}
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
            placeholder={
              config.apiKeyMasked
                ? '已配置密钥，留空保持不变'
                : config.vendor
                  ? `请输入 ${config.vendor} API Key`
                  : '请输入 API Key'
            }
            onChange={(e) => patch({ apiKey: e.target.value, apiKeyMasked: false })}
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
          <AlertCircle size={14} /> {testErrorMsg || '请先填写 API Key 再进行连接测试'}
        </div>
      )}
    </div>
  )
}

/** 将 API 返回的配置项转为本地 ModelConfig。 */
export function itemToConfig(item: LlmConfigItem): ModelConfig {
  // GET 接口对已有密钥返回脱敏占位符 "••••••••"，不应把它当作真值填入可编辑输入框，
  // 否则保存时会把占位符回写、覆盖真实密钥。识别到占位符则清空并在保存时省略该字段。
  const masked = item.apiKey === '••••••••'
  return {
    vendor: item.vendor,
    model: item.model,
    apiKey: masked ? '' : (item.apiKey ?? ''),
    apiKeyMasked: masked,
    apiBaseUrl: item.apiBaseUrl,
    enabled: item.enabled,
  }
}

/** 将本地 ModelConfig 转为 API 更新请求体。 */
export function configToUpdate(config: ModelConfig): LlmConfigUpdate {
  const update: LlmConfigUpdate = {
    vendor: config.vendor,
    model: config.model,
    apiBaseUrl: config.apiBaseUrl,
    enabled: config.enabled,
  }
  // 若密钥未被修改（仍是从服务端带下来的脱敏态），则不携带 apiKey 字段，
  // 由后端保留原存密钥。仅当用户实际输入了新密钥时才上传。
  if (!config.apiKeyMasked) {
    update.apiKey = config.apiKey
  }
  return update
}

export default function LlmConfigPage() {
  const [primary, setPrimary] = useState<ModelConfig>({
    vendor: '',
    model: '',
    apiKey: '',
    apiKeyMasked: false,
    apiBaseUrl: '',
    enabled: false,
  })
  const [secondary, setSecondary] = useState<ModelConfig>({
    vendor: '',
    model: '',
    apiKey: '',
    apiKeyMasked: false,
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
        configId="primary"
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
        configId="secondary"
        onChange={setSecondary}
        onSave={handleSaveSecondary}
        saving={savingSecondary}
      />
    </div>
  )
}

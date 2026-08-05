/**
 * 「LLM 密钥脱敏值被当真值回写」回归测试。
 *
 * 背景：GET 接口对已有密钥返回脱敏占位符 "••••••••"。历史上前端把该占位符
 * 原样塞入输入框并随保存回传，后端又无条件 UPDATE api_key，导致真实密钥被
 * 占位符覆盖、真实 LLM 永远调不通。
 *
 * 本文件校验前端侧的双向防御：
 * 1. itemToConfig：GET 返回的占位符 → 本地 apiKey 清空 + apiKeyMasked=true
 *    （不把占位符当作可编辑真值）；
 * 2. configToUpdate：apiKeyMasked=true（未改动）时请求体省略 apiKey，
 *    后端据此保留原存密钥；
 * 3. configToUpdate：用户实际输入新密钥时正常携带。
 */
import { describe, it, expect } from 'vitest'
import { itemToConfig, configToUpdate } from '../LlmConfig'

const MASK = '••••••••'

describe('LLM 密钥脱敏值不污染编辑态', () => {
  it('GET 返回的脱敏占位符 → 本地清空且标记为已掩码', () => {
    const cfg = itemToConfig({
      id: 'primary',
      vendor: 'OpenAI',
      model: 'GPT-4o',
      apiKey: MASK,
      apiBaseUrl: 'https://api.openai.com/v1',
      enabled: true,
      updatedAt: '',
    })
    expect(cfg.apiKey).toBe('')
    expect(cfg.apiKeyMasked).toBe(true)
  })

  it('无密钥（apiKey 为空串）时 apiKeyMasked=false', () => {
    const cfg = itemToConfig({
      id: 'primary',
      vendor: 'OpenAI',
      model: 'GPT-4o',
      apiKey: '',
      apiBaseUrl: '',
      enabled: false,
      updatedAt: '',
    })
    expect(cfg.apiKeyMasked).toBe(false)
  })

  it('未改动密钥（apiKeyMasked=true）时，PUT 请求体省略 apiKey', () => {
    const upd = configToUpdate({
      vendor: 'OpenAI',
      model: 'GPT-4o',
      apiKey: '',
      apiKeyMasked: true,
      apiBaseUrl: 'https://api.openai.com/v1',
      enabled: true,
    })
    expect(upd.apiKey).toBeUndefined()
  })

  it('用户重新输入真实密钥时正常携带', () => {
    const upd = configToUpdate({
      vendor: 'OpenAI',
      model: 'GPT-4o',
      apiKey: 'sk-real-123',
      apiKeyMasked: false,
      apiBaseUrl: 'https://api.openai.com/v1',
      enabled: true,
    })
    expect(upd.apiKey).toBe('sk-real-123')
  })

  it("用户清空密钥（apiKeyMasked=false 且 apiKey=''）时携带空串允许清除", () => {
    const upd = configToUpdate({
      vendor: 'OpenAI',
      model: 'GPT-4o',
      apiKey: '',
      apiKeyMasked: false,
      apiBaseUrl: 'https://api.openai.com/v1',
      enabled: true,
    })
    expect(upd.apiKey).toBe('')
  })
})

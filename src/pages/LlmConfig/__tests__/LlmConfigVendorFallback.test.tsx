/**
 * 「LLM 配置页白屏」回归测试。
 *
 * 背景：后端 GET /api/llm-config 返回的 primary.vendor 为空串时，
 * ModelCard 直接执行 `VENDOR_MODELS[config.vendor].map(...)`，
 * 命中 undefined → TypeError → React 渲染中断 → 整页白屏。
 *
 * 本文件覆盖：
 * 1. vendor 为空串时页面正常渲染，模型框降级为只读输入框（不崩溃）；
 * 2. vendor 为空但已存 model 值时，该值仍然可见（不丢数据）；
 * 3. vendor 是静态映射外的未知厂商（如「智谱」）时同样不崩溃；
 * 4. vendor 正常（Anthropic）时保持原有下拉框行为不回归。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import '@testing-library/jest-dom'
import LlmConfigPage from '../LlmConfig'
import { llmConfigApi } from '../../../api/client'
import type { LlmConfigItem } from '../../../api/client'

vi.mock('../../../api/client')

const getAllMock = vi.mocked(llmConfigApi).getAll

function makeItem(overrides: Partial<LlmConfigItem> = {}): LlmConfigItem {
  return {
    id: 'primary',
    vendor: 'Anthropic',
    model: 'Claude 3.5 Sonnet',
    apiKey: 'sk-test',
    apiBaseUrl: '',
    enabled: true,
    updatedAt: '2025-01-01 00:00:00',
    ...overrides,
  }
}

/** 渲染页面并等待 loading 结束。 */
async function renderPage(
  primary: LlmConfigItem,
  secondary: LlmConfigItem = makeItem({ id: 'secondary' })
) {
  getAllMock.mockResolvedValue({ primary, secondary })
  render(<LlmConfigPage />)
  await waitFor(() =>
    expect(screen.queryByText('加载 LLM 配置中…')).not.toBeInTheDocument()
  )
}

describe('LLM 配置页：vendor 异常值渲染防御', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('vendor 为空串时页面不崩溃，仍渲染出主/副模型卡片', async () => {
    await renderPage(makeItem({ id: 'primary', vendor: '', model: '' }))

    expect(screen.getByText('LLM 配置')).toBeInTheDocument()
    expect(screen.getByText('主模型')).toBeInTheDocument()
    expect(screen.getByText('副模型（备用）')).toBeInTheDocument()
  })

  it('vendor 为空串时模型框降级为禁用的只读输入框并显示占位提示', async () => {
    await renderPage(makeItem({ id: 'primary', vendor: '', model: '' }))

    const fallback = screen.getByPlaceholderText('请先选择厂商') as HTMLInputElement
    expect(fallback).toBeInTheDocument()
    expect(fallback.tagName).toBe('INPUT')
    expect(fallback).toBeDisabled()
    expect(fallback.readOnly).toBe(true)
  })

  it('vendor 为空但已存 model 值时，该值仍然可见（不丢数据）', async () => {
    await renderPage(
      makeItem({ id: 'primary', vendor: '', model: 'some-legacy-model' })
    )

    const fallback = screen.getByPlaceholderText('请先选择厂商') as HTMLInputElement
    expect(fallback.value).toBe('some-legacy-model')
  })

  it('vendor 为静态映射外的未知厂商时不崩溃，且厂商值保留可见', async () => {
    await renderPage(makeItem({ id: 'primary', vendor: '智谱', model: 'GLM-4' }))

    expect(screen.getByText('主模型')).toBeInTheDocument()
    const vendorSelects = screen.getAllByLabelText('模型厂商') as HTMLSelectElement[]
    expect(vendorSelects[0].value).toBe('智谱')
    // 未知厂商无候选模型 → 走只读输入框分支，保留原 model 值
    const fallback = screen.getByPlaceholderText('请先选择厂商') as HTMLInputElement
    expect(fallback.value).toBe('GLM-4')
  })

  it('vendor 正常时保持原有下拉框行为（无回归）', async () => {
    await renderPage(
      makeItem({ id: 'primary', vendor: 'Anthropic', model: 'Claude 3 Opus' })
    )

    const modelFields = screen.getAllByLabelText('模型') as HTMLSelectElement[]
    expect(modelFields).toHaveLength(2)
    expect(modelFields[0].tagName).toBe('SELECT')
    expect(modelFields[0].value).toBe('Claude 3 Opus')
    expect(screen.queryByPlaceholderText('请先选择厂商')).not.toBeInTheDocument()
  })

  it('厂商下拉框包含 value="" 的禁用占位项', async () => {
    await renderPage(makeItem({ id: 'primary', vendor: '', model: '' }))

    const vendorSelects = screen.getAllByLabelText('模型厂商') as HTMLSelectElement[]
    const placeholder = Array.from(vendorSelects[0].options).find(
      (o) => o.value === ''
    )
    expect(placeholder).toBeDefined()
    expect(placeholder?.textContent).toContain('请选择厂商')
    expect(placeholder?.disabled).toBe(true)
  })
})

/**
 * ScheduleForm 组件验收测试。
 *
 * 覆盖：
 * - 5 种频率模式渲染
 * - 模式切换
 * - 时间 grid 选择/取消
 * - 周天 chip 选择
 * - 每月日期 chip 选择
 * - Cron 表达式输入
 * - AI Modal 交互
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import '@testing-library/jest-dom'
import ScheduleForm from '../components/ScheduleForm'
import type { ScheduleConfig } from '../../../types/operations'

// Mock API
vi.mock('../../../api/operations', () => ({
  operationsTasksApi: {
    list: vi.fn().mockResolvedValue([]),
    create: vi.fn(),
    get: vi.fn(),
    update: vi.fn(),
    toggleEnabled: vi.fn(),
    delete: vi.fn(),
    listTargets: vi.fn().mockResolvedValue([]),
    setTargets: vi.fn(),
    listSessions: vi.fn().mockResolvedValue([]),
    listTargetSessionsV2: vi.fn().mockResolvedValue({ items: [], total: 0, page: 1, page_size: 20, has_more: false }),
    listHostingAccounts: vi.fn().mockResolvedValue([]),
    listHostingBots: vi.fn().mockResolvedValue([]),
    listTags: vi.fn().mockResolvedValue([]),
    listTagGroups: vi.fn().mockResolvedValue([]),
    aiCron: vi.fn().mockResolvedValue({ cron: '0 9 * * 1-5', explanation: '每周一到周五早上9点' }),
  },
}))

const defaultOnChange = vi.fn()

function renderForm(config: ScheduleConfig = { type: 'once', runTime: '' }) {
  return render(<ScheduleForm value={config} onChange={defaultOnChange} />)
}

describe('ScheduleForm - 频率模式切换', () => {
  beforeEach(() => {
    defaultOnChange.mockClear()
  })

  it('渲染 5 种频率 radio 选项', () => {
    renderForm()
    expect(screen.getByText('单次运行')).toBeInTheDocument()
    expect(screen.getByText('每天')).toBeInTheDocument()
    expect(screen.getByText('每周')).toBeInTheDocument()
    expect(screen.getByText('每月')).toBeInTheDocument()
    expect(screen.getByText('Cron表达式')).toBeInTheDocument()
  })

  it('默认显示单次运行模式（datetime-local input）', () => {
    renderForm()
    const inputs = screen.getAllByDisplayValue('')
    const dtInput = inputs.find((el) => (el as HTMLInputElement).type === 'datetime-local')
    expect(dtInput).toBeInTheDocument()
  })

  it('切换到「每天」模式显示时间 grid 和日期范围', () => {
    renderForm({ type: 'daily', runTimes: [], effectiveStart: '', effectiveEnd: '' })
    // 时间 grid 应该存在
    expect(screen.getByText('00:00')).toBeInTheDocument()
    expect(screen.getByText('23:00')).toBeInTheDocument()
    // 日期范围
    expect(screen.getByLabelText('生效开始日期')).toBeInTheDocument()
    expect(screen.getByLabelText('生效结束日期')).toBeInTheDocument()
  })

  it('切换到「每周」模式显示周天 chips 和时间 grid', () => {
    renderForm({ type: 'weekly', weekdays: [], runTimes: [], effectiveStart: '', effectiveEnd: '' })
    expect(screen.getByText('周一')).toBeInTheDocument()
    expect(screen.getByText('周日')).toBeInTheDocument()
    expect(screen.getByText('00:00')).toBeInTheDocument()
  })

  it('切换到「每月」模式显示日期选项和 tabs', () => {
    renderForm({ type: 'monthly', days: [], lastDays: [], runTimes: [], effectiveStart: '', effectiveEnd: '' })
    expect(screen.getByText('指定日期')).toBeInTheDocument()
    expect(screen.getByText('当月倒数第几天')).toBeInTheDocument()
    expect(screen.getByText('全选')).toBeInTheDocument()
  })

  it('切换到「Cron表达式」模式显示 cron 输入和 AI 按钮', () => {
    renderForm({ type: 'cron', cron: '' })
    expect(screen.getByPlaceholderText('请输入 Cron 表达式，如：0 8 * * 1-5')).toBeInTheDocument()
    expect(screen.getByText('AI 生成表达式')).toBeInTheDocument()
    // 错误提示
    expect(screen.getByText('请输入 Cron 表达式')).toBeInTheDocument()
  })
})

describe('ScheduleForm - 时间 grid 交互', () => {
  beforeEach(() => {
    defaultOnChange.mockClear()
  })

  it('点击时间 chip 将其选中', () => {
    renderForm({ type: 'daily', runTimes: [], effectiveStart: '', effectiveEnd: '' })
    const chip = screen.getByText('08:00')
    fireEvent.click(chip)
    expect(defaultOnChange).toHaveBeenCalledWith(
      expect.objectContaining({ type: 'daily', runTimes: ['08:00'] })
    )
  })

  it('再次点击已选时间 chip 取消选中', () => {
    renderForm({ type: 'daily', runTimes: ['08:00'], effectiveStart: '', effectiveEnd: '' })
    // 找到 grid 中已激活的 08:00 按钮（aria-pressed="true"）
    const activeChip = screen.getByRole('button', { name: '08:00', pressed: true })
    fireEvent.click(activeChip)
    expect(defaultOnChange).toHaveBeenCalledWith(
      expect.objectContaining({ type: 'daily', runTimes: [] })
    )
  })

  it('选中的时间以 chip 方式显示并可删除', () => {
    renderForm({ type: 'daily', runTimes: ['08:00', '12:00'], effectiveStart: '', effectiveEnd: '' })
    // chips 显示 — 使用 getAllByText 因为 grid 中也有同名 button
    const chips08 = screen.getAllByText('08:00')
    const chips12 = screen.getAllByText('12:00')
    expect(chips08.length).toBeGreaterThanOrEqual(1)
    expect(chips12.length).toBeGreaterThanOrEqual(1)
    // 移除按钮
    const removeButtons = screen.getAllByLabelText(/移除/)
    expect(removeButtons.length).toBe(2)
  })
})

describe('ScheduleForm - 周天与月份选择', () => {
  beforeEach(() => {
    defaultOnChange.mockClear()
  })

  it('点击周天 chip 切换选中', () => {
    renderForm({ type: 'weekly', weekdays: [], runTimes: [], effectiveStart: '', effectiveEnd: '' })
    const mon = screen.getByText('周一')
    fireEvent.click(mon)
    expect(defaultOnChange).toHaveBeenCalledWith(
      expect.objectContaining({ type: 'weekly', weekdays: [1] })
    )
  })

  it('点击月份日期 chip 切换选中', () => {
    renderForm({ type: 'monthly', days: [], lastDays: [], runTimes: [], effectiveStart: '', effectiveEnd: '' })
    const day1 = screen.getByText('1日')
    fireEvent.click(day1)
    expect(defaultOnChange).toHaveBeenCalledWith(
      expect.objectContaining({ type: 'monthly', days: [1] })
    )
  })

  it('全选按钮切换所有日期', () => {
    renderForm({ type: 'monthly', days: [], lastDays: [], runTimes: [], effectiveStart: '', effectiveEnd: '' })
    const selectAll = screen.getByText('全选')
    fireEvent.click(selectAll)
    expect(defaultOnChange).toHaveBeenCalledWith(
      expect.objectContaining({ type: 'monthly', days: expect.any(Array) })
    )
    const callArg = defaultOnChange.mock.calls[0][0] as ScheduleConfig
    if (callArg.type === 'monthly') {
      expect(callArg.days.length).toBe(31)
    }
  })

  it('切换到「当月倒数第几天」tab 显示第1-5天 chips', () => {
    renderForm({ type: 'monthly', days: [], lastDays: [], runTimes: [], effectiveStart: '', effectiveEnd: '' })
    const lastDayTab = screen.getByText('当月倒数第几天')
    fireEvent.click(lastDayTab)
    expect(screen.getByText('第1天')).toBeInTheDocument()
    expect(screen.getByText('第5天')).toBeInTheDocument()
  })
})

describe('ScheduleForm - Cron 模式与 AI Modal', () => {
  beforeEach(() => {
    defaultOnChange.mockClear()
  })

  it('输入 cron 表达式触发 onChange', () => {
    renderForm({ type: 'cron', cron: '' })
    const input = screen.getByPlaceholderText('请输入 Cron 表达式，如：0 8 * * 1-5')
    fireEvent.change(input, { target: { value: '0 8 * * *' } })
    expect(defaultOnChange).toHaveBeenCalledWith(
      expect.objectContaining({ type: 'cron', cron: '0 8 * * *' })
    )
  })

  it('点击 AI 生成表达式按钮打开 Modal', () => {
    renderForm({ type: 'cron', cron: '' })
    const aiBtn = screen.getByText('AI 生成表达式')
    fireEvent.click(aiBtn)
    expect(screen.getByText('AI 生成 Cron 表达式')).toBeInTheDocument()
    expect(screen.getByText('描述你的调度需求')).toBeInTheDocument()
  })

  it('AI Modal 包含 textarea 和生成按钮', () => {
    renderForm({ type: 'cron', cron: '' })
    fireEvent.click(screen.getByText('AI 生成表达式'))
    expect(screen.getByPlaceholderText('例如：每周一到周五早上9点执行')).toBeInTheDocument()
    expect(screen.getByText('生成')).toBeInTheDocument()
  })

  it('空 cron 表达式显示错误提示', () => {
    renderForm({ type: 'cron', cron: '' })
    expect(screen.getByText('请输入 Cron 表达式')).toBeInTheDocument()
  })

  it('有 cron 表达式时不显示错误提示', () => {
    renderForm({ type: 'cron', cron: '0 8 * * *' })
    expect(screen.queryByText('请输入 Cron 表达式')).not.toBeInTheDocument()
  })
})

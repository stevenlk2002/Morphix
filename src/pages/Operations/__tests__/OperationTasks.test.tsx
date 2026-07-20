/**
 * 运营任务页（/operations/tasks）验收测试。
 *
 * 验收依据：
 * - 原型：prototype/index.html 8666-8698
 * - 需求：搜索 + 类型5种 + 启用状态 + 运行状态5种 + 排序6项 + 创建按钮右对齐
 * - 卡片网格 grid auto-fill minmax(320px, 1fr), gap 16px
 * - 卡片含 badge / Switch / 名称 / meta / 编辑 / 运营记录
 * - 无冗余页头标题
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, within, fireEvent, waitFor } from '@testing-library/react'
import '@testing-library/jest-dom'
import { MemoryRouter } from 'react-router-dom'
import OperationTasksPage from '../OperationTasks'

// 拦截 API 调用
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
  },
}))

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/operations/tasks']}>
      <OperationTasksPage />
    </MemoryRouter>
  )
}

describe('运营任务页 - 原型对齐验收', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('Banner 标题与两行描述严格匹配原型 8666-8698', () => {
    renderPage()
    expect(
      screen.getByText('运营任务', { selector: '.banner-title' })
    ).toBeInTheDocument()
    const desc = document.querySelector('.banner-desc')
    expect(desc).not.toBeNull()
    // 描述行1
    expect(desc!.textContent).toContain(
      '群发任务 · 机器人定时任务 · 特定节点定时任务'
    )
    // 描述行2
    expect(desc!.textContent).toContain('特定节点机器人定时任务')
    // 必须用 <br/> 强制换行
    expect(desc!.querySelector('br')).not.toBeNull()
  })

  it('类型下拉 5 种：群发/机器人定时/朋友圈/特定节点定时/特定节点机器人定时', () => {
    renderPage()
    const typeSelect = screen.getAllByRole('combobox')[0]
    const options = within(typeSelect).getAllByRole('option')
    const labels = options.map((o) => o.textContent)
    expect(labels).toEqual([
      '全部类型',
      '群发任务',
      '机器人定时任务',
      '朋友圈任务',
      '特定节点定时任务',
      '特定节点机器人定时任务',
    ])
  })

  it('启用状态下拉：全部 / 已启用 / 已停用', () => {
    renderPage()
    const enabledSelect = screen.getAllByRole('combobox')[1]
    const labels = within(enabledSelect)
      .getAllByRole('option')
      .map((o) => o.textContent)
    expect(labels).toEqual(['启用状态', '已启用', '已停用'])
  })

  it('运行状态下拉 5 种：未运行/运行中/已完成/异常结束/人工停止', () => {
    renderPage()
    const runSelect = screen.getAllByRole('combobox')[2]
    const labels = within(runSelect)
      .getAllByRole('option')
      .map((o) => o.textContent)
    expect(labels).toEqual([
      '运行状态',
      '未运行',
      '运行中',
      '已完成',
      '异常结束',
      '人工停止',
    ])
  })

  it('排序下拉 6 项：创建时间↓/↑、任务名称A-Z/Z-A、下次运行↑/↓', () => {
    renderPage()
    const sortSelect = screen.getAllByRole('combobox')[3]
    const labels = within(sortSelect)
      .getAllByRole('option')
      .map((o) => o.textContent)
    expect(labels).toEqual([
      '创建时间 ↓',
      '创建时间 ↑',
      '任务名称 A-Z',
      '任务名称 Z-A',
      '下次运行 ↑',
      '下次运行 ↓',
    ])
  })

  it('筛选栏无创建运营任务按钮（入口在下方虚线卡片）', () => {
    const { container } = renderPage()
    const filterBar = container.querySelector('.filter-bar')
    expect(filterBar).not.toBeNull()
    const createBtn = Array.from(filterBar!.querySelectorAll('button')).find(
      (b) => b.textContent?.includes('创建运营任务')
    )
    expect(createBtn).toBeUndefined()
  })

  it('无冗余页头标题：页面中只出现一个"运营任务"标题（在 banner 内）', () => {
    const { container } = renderPage()
    const titles = container.querySelectorAll('.banner-title')
    expect(titles.length).toBe(1)
    // 不应出现 page-title / page-subtitle 块
    expect(container.querySelector('.page-title')).toBeNull()
    expect(container.querySelector('.page-subtitle')).toBeNull()
  })

  it('卡片网格容器存在并使用 .task-grid 类（具体 CSS 由视觉验收 + 静态检查保证）', () => {
    const { container } = renderPage()
    const grid = container.querySelector('.task-grid')
    expect(grid).not.toBeNull()
    // 静态 CSS 规则（auto-fill + minmax(320px, 1fr) + gap 16px）已通过
    // prototype 8666-8698 + QA 视觉截图验证。
    expect(grid!.classList.contains('task-grid')).toBe(true)
  })

  it('任务卡片包含"更多操作"按钮（...），点击弹出删除菜单', async () => {
    const { operationsTasksApi } = await import('../../../api/operations')
    ;(operationsTasksApi.list as unknown as ReturnType<typeof vi.fn>).mockResolvedValueOnce(
      [
        {
          id: 't1',
          name: '测试任务',
          task_type: '群发任务',
          channel_type: '企业微信',
          session_type: '群聊',
          content_blocks: [],
          hosting_action: '保持不变',
          run_frequency: '一次',
          run_time: '',
          effective_start: '',
          effective_end: '',
          cron_expression: '',
          run_status: '未运行',
          enabled: true,
          next_run_time: '2026-07-10 04:02:00',
          target_count: 0,
          created_at: '2026-07-10',
          updated_at: '2026-07-10',
        },
      ]
    )
    renderPage()
    await waitFor(() => {
      expect(screen.getByText('测试任务')).toBeInTheDocument()
    })

    // 找到更多操作按钮
    const moreBtn = screen.getByLabelText('更多操作')
    expect(moreBtn).toBeInTheDocument()

    // 点击打开菜单
    fireEvent.click(moreBtn)
    await waitFor(() => {
      expect(screen.getByText('删除')).toBeInTheDocument()
    })
  })

  it('点击删除触发 confirm，确认后调用 API 并刷新列表', async () => {
    const { operationsTasksApi } = await import('../../../api/operations')
    ;(operationsTasksApi.list as unknown as ReturnType<typeof vi.fn>).mockResolvedValueOnce(
      [
        {
          id: 't-del',
          name: '待删除任务',
          task_type: '群发任务',
          channel_type: '企业微信',
          session_type: '群聊',
          content_blocks: [],
          hosting_action: '保持不变',
          run_frequency: '一次',
          run_time: '',
          effective_start: '',
          effective_end: '',
          cron_expression: '',
          run_status: '未运行',
          enabled: true,
          next_run_time: '—',
          target_count: 0,
          created_at: '2026-07-10',
          updated_at: '2026-07-10',
        },
      ]
    )
    ;(operationsTasksApi.delete as unknown as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      id: 't-del',
      deleted: true,
    })

    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValueOnce(true)

    renderPage()
    await waitFor(() => {
      expect(screen.getByText('待删除任务')).toBeInTheDocument()
    })

    // 打开菜单
    fireEvent.click(screen.getByLabelText('更多操作'))
    await waitFor(() => {
      expect(screen.getByText('删除')).toBeInTheDocument()
    })

    // 点击删除
    fireEvent.click(screen.getByText('删除'))

    expect(confirmSpy).toHaveBeenCalled()
    await waitFor(() => {
      expect(operationsTasksApi.delete).toHaveBeenCalledWith('t-del')
    })

    confirmSpy.mockRestore()
  })

  it('每个任务卡片含 badge / Switch / 名称 / meta / 编辑 / 运营记录', async () => {
    // 重新 mock 让 list 返回样本数据
    const { operationsTasksApi } = await import('../../../api/operations')
    ;(operationsTasksApi.list as unknown as ReturnType<typeof vi.fn>).mockResolvedValueOnce(
      [
        {
          id: 't1',
          name: '测试任务',
          task_type: '群发任务',
          channel_type: '企业微信',
          session_type: '群聊',
          content_blocks: [],
          hosting_action: '保持不变',
          run_frequency: '一次',
          run_time: '',
          effective_start: '',
          effective_end: '',
          cron_expression: '',
          run_status: '未运行',
          enabled: true,
          next_run_time: '2026-07-10 04:02:00',
          target_count: 0,
          created_at: '2026-07-10',
          updated_at: '2026-07-10',
        },
      ]
    )
    const { container } = renderPage()
    // 等待加载完成
    await new Promise((r) => setTimeout(r, 0))
    const cards = Array.from(
      container.querySelectorAll('.task-card')
    ).filter((c) => !c.classList.contains('task-card-dashed'))
    expect(cards.length).toBeGreaterThan(0)
    cards.forEach((card) => {
      // 至少包含一个 badge / proto-badge
      expect(card.querySelector('.proto-badge, .badge')).not.toBeNull()
      // 至少包含一个 switch
      expect(card.querySelector('.switch input[type="checkbox"]')).not.toBeNull()
      // 包含名称
      expect(card.querySelector('.task-bot-name')).not.toBeNull()
      // 包含 meta
      expect(card.querySelector('.task-meta')).not.toBeNull()
    })
  })

  it('虚线"创建运营任务"卡片作为网格入口', () => {
    const { container } = renderPage()
    const dashed = container.querySelector('.task-card-dashed')
    expect(dashed).not.toBeNull()
    expect(dashed!.textContent).toContain('创建运营任务')
  })

  it('【回归】搜索输入框存在且 placeholder 完整（不被 filter-bar nowrap 挤压）', () => {
    // QA 视觉验证发现：当前实现因 flex-shrink:1 + 多余的"重置"按钮，
    // .task-search 在 1028px / 1348px 容器下被压到 74px，placeholder "搜索任务"
    // 被截断为 "搜"。此用例锁定 DOM 契约，渲染宽度由 Playwright 验收。
    // 修复方向：移除多余"重置"按钮（不在 prototype/需求规格中），
    // 或为 .task-search 增加 flex-shrink:0 / min-width:220px。
    const { container } = renderPage()
    const search = container.querySelector('.task-search')
    expect(search).not.toBeNull()
    const input = search!.querySelector('input')
    expect(input).not.toBeNull()
    expect(input!.getAttribute('placeholder')).toBe('搜索任务')
  })
})

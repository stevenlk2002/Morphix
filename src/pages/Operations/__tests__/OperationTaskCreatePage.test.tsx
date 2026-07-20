/**
 * OperationTaskCreatePage 验收测试 — 聚焦 GroupTab 修复验证。
 *
 * 验证项：
 * 1. Step 3 中切换到「通过客户分组选择」Tab 后，勾选分组可使「下一步」按钮由 disabled → enabled
 * 2. canNext() 在 step=3 时依赖 selectedSessionIds.length || selectedGroupIds.length
 * 3. 勾选分组后进入 step 4 → 可创建成功
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import '@testing-library/jest-dom'
import { MemoryRouter } from 'react-router-dom'
import OperationTaskCreatePage from '../OperationTaskCreatePage'

// Mock API
vi.mock('../../../api/operations', () => ({
  operationsTasksApi: {
    list: vi.fn().mockResolvedValue([]),
    create: vi.fn().mockResolvedValue({ id: 'new-task-1', name: '测试任务' }),
    get: vi.fn(),
    update: vi.fn(),
    toggleEnabled: vi.fn(),
    delete: vi.fn(),
    listTargets: vi.fn().mockResolvedValue([]),
    setTargets: vi.fn(),
    listSessions: vi.fn().mockResolvedValue([]),
    listTargetSessionsV2: vi.fn().mockResolvedValue({
      items: [],
      total: 0,
      page: 1,
      page_size: 20,
      has_more: false,
    }),
    listHostingAccounts: vi.fn().mockResolvedValue([]),
    listHostingBots: vi.fn().mockResolvedValue([]),
    listTags: vi.fn().mockResolvedValue([]),
    listTagGroups: vi.fn().mockResolvedValue([]),
  },
}))

vi.mock('../../../api/client', () => ({
  customerGroupsApi: {
    list: vi.fn().mockResolvedValue([]),
  },
}))

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/operations/tasks/create']}>
      <OperationTaskCreatePage />
    </MemoryRouter>
  )
}

describe('OperationTaskCreatePage — GroupTab 修复验证', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('Step 导航与基础渲染', () => {
    it('默认显示 Step 1（选择任务类型）', () => {
      renderPage()
      expect(screen.getByText('选择任务类型')).toBeInTheDocument()
      // Stepper 中 step 1 应高亮
      const stepLabels = screen.getAllByText(/选择任务类型/)
      expect(stepLabels.length).toBeGreaterThanOrEqual(1)
    })

    it('Step 1 选中任务类型后「下一步」按钮可用', () => {
      renderPage()
      const nextBtn = screen.getByText('下一步')
      // 初始 disabled（taskType 已默认 '群发任务'，所以应该可用）
      // 检查 canNext: step=1, taskType='群发任务' → true
      expect(nextBtn.closest('button')!).not.toBeDisabled()
    })

    it('可以逐步导航到 Step 3', async () => {
      renderPage()
      // Step 1 → Step 2
      fireEvent.click(screen.getByText('下一步'))
      await waitFor(() => {
        expect(screen.getByPlaceholderText('请输入任务名称')).toBeInTheDocument()
      })

      // 填入名称
      const nameInput = screen.getByPlaceholderText('请输入任务名称')
      fireEvent.change(nameInput, { target: { value: '测试运营任务' } })

      // Step 2 → Step 3
      fireEvent.click(screen.getByText('下一步'))
      await waitFor(() => {
        // Step 3 应显示 TargetSelector（含 tabs）
        expect(screen.getByText('静态选择')).toBeInTheDocument()
      })
    })
  })

  describe('Step 3: GroupTab → canNext → 下一步按钮可用', () => {
    it('Step 3 初始状态下「下一步」按钮 disabled（无任何选择）', async () => {
      renderPage()

      // Navigate to Step 3
      fireEvent.click(screen.getByText('下一步')) // step 1→2
      const nameInput = screen.getByPlaceholderText('请输入任务名称')
      fireEvent.change(nameInput, { target: { value: '测试' } })
      fireEvent.click(screen.getByText('下一步')) // step 2→3

      await waitFor(() => {
        expect(screen.getByText('静态选择')).toBeInTheDocument()
      })

      // 「下一步」按钮应该 disabled（无选择）
      const nextBtn = screen.getByText('下一步').closest('button')!
      expect(nextBtn).toBeDisabled()
    })

    it('切换到「通过客户分组选择」Tab 后，勾选分组 → 「下一步」按钮变为可用', async () => {
      const { customerGroupsApi } = await import('../../../api/client')
      ;(customerGroupsApi.list as ReturnType<typeof vi.fn>).mockResolvedValueOnce([
        {
          id: 'g1',
          name: '高意向客户',
          type: 'custom',
          count: 42,
          createdAt: '2026-01-01',
          updatedAt: '2026-06-01',
          editor: '张三',
        },
      ])

      renderPage()

      // Navigate to Step 3
      fireEvent.click(screen.getByText('下一步')) // step 1→2
      const nameInput = screen.getByPlaceholderText('请输入任务名称')
      fireEvent.change(nameInput, { target: { value: '测试' } })
      fireEvent.click(screen.getByText('下一步')) // step 2→3

      await waitFor(() => {
        expect(screen.getByText('静态选择')).toBeInTheDocument()
      })

      // 切换到 GroupTab
      fireEvent.click(screen.getByText('通过客户分组选择'))

      await waitFor(() => {
        expect(screen.getByText('高意向客户')).toBeInTheDocument()
      })

      // 「下一步」按钮此时仍应 disabled（尚无一勾选）
      const nextBtnBefore = screen.getByText('下一步').closest('button')!
      expect(nextBtnBefore).toBeDisabled()

      // 勾选分组 checkbox
      const checkboxes = document.querySelectorAll('.target-data-table tbody input[type="checkbox"]')
      expect(checkboxes.length).toBeGreaterThan(0)
      fireEvent.click(checkboxes[0])

      // 「下一步」按钮现在应变为可用（因为 selectedGroupIds.length > 0）
      await waitFor(() => {
        const nextBtnAfter = screen.getByText('下一步').closest('button')!
        expect(nextBtnAfter).not.toBeDisabled()
      })
    })

    it('勾选分组后进入 Step 4，可看到运行时间表单', async () => {
      const { customerGroupsApi } = await import('../../../api/client')
      ;(customerGroupsApi.list as ReturnType<typeof vi.fn>).mockResolvedValueOnce([
        {
          id: 'g1',
          name: 'VIP客户分组',
          type: 'system',
          count: 100,
          createdAt: '2026-01-01',
          updatedAt: '2026-06-01',
          editor: '李四',
        },
      ])

      renderPage()

      // Navigate Step 1→2
      fireEvent.click(screen.getByText('下一步'))
      const nameInput = screen.getByPlaceholderText('请输入任务名称')
      fireEvent.change(nameInput, { target: { value: '测试运营' } })

      // Navigate Step 2→3
      fireEvent.click(screen.getByText('下一步'))

      await waitFor(() => {
        expect(screen.getByText('静态选择')).toBeInTheDocument()
      })

      // Switch to GroupTab, check a group
      fireEvent.click(screen.getByText('通过客户分组选择'))

      await waitFor(() => {
        expect(screen.getByText('VIP客户分组')).toBeInTheDocument()
      })

      const checkboxes = document.querySelectorAll('.target-data-table tbody input[type="checkbox"]')
      fireEvent.click(checkboxes[0])

      // 「下一步」应可用 → 点击进入 Step 4
      await waitFor(() => {
        const nextBtn = screen.getByText('下一步').closest('button')!
        expect(nextBtn).not.toBeDisabled()
      })

      fireEvent.click(screen.getByText('下一步'))

      // Step 4 应显示「创建任务」按钮（而非「下一步」）
      await waitFor(() => {
        expect(screen.getByText('创建任务')).toBeInTheDocument()
      })
    })

    it('Step 4 填写运行时间后点击「创建任务」调用 API 创建', async () => {
      const { operationsTasksApi } = await import('../../../api/operations')
      const { customerGroupsApi } = await import('../../../api/client')

      ;(customerGroupsApi.list as ReturnType<typeof vi.fn>).mockResolvedValueOnce([
        {
          id: 'g1',
          name: '高意向客户',
          type: 'custom',
          count: 42,
          createdAt: '2026-01-01',
          updatedAt: '2026-06-01',
          editor: '张三',
        },
      ])

      renderPage()

      // Step 1→2→3→4 with group selection
      fireEvent.click(screen.getByText('下一步')) // 1→2
      const nameInput = screen.getByPlaceholderText('请输入任务名称')
      fireEvent.change(nameInput, { target: { value: '运营测试任务' } })
      fireEvent.click(screen.getByText('下一步')) // 2→3

      await waitFor(() => {
        expect(screen.getByText('通过客户分组选择')).toBeInTheDocument()
      })

      fireEvent.click(screen.getByText('通过客户分组选择'))

      await waitFor(() => {
        expect(screen.getByText('高意向客户')).toBeInTheDocument()
      })

      // Check the group
      const checkboxes = document.querySelectorAll('.target-data-table tbody input[type="checkbox"]')
      fireEvent.click(checkboxes[0])

      // Go to Step 4
      await waitFor(() => {
        const nextBtn = screen.getByText('下一步').closest('button')!
        expect(nextBtn).not.toBeDisabled()
      })
      fireEvent.click(screen.getByText('下一步'))

      await waitFor(() => {
        expect(screen.getByText('创建任务')).toBeInTheDocument()
      })

      // Fill in run time (use a datetime-local input or text input)
      const timeInputs = document.querySelectorAll('input[type="datetime-local"], input[type="text"]')
      // Find a time-related input and fill it
      for (const inp of timeInputs) {
        if (
          inp instanceof HTMLInputElement &&
          (inp.type === 'datetime-local' || inp.placeholder?.includes('时间'))
        ) {
          fireEvent.change(inp, { target: { value: '2026-07-15T10:00' } })
          break
        }
      }

      // Click create
      const createBtn = screen.getByText('创建任务').closest('button')!
      // 等待按钮不再 disabled（canNext 为 true）
      await waitFor(() => {
        expect(createBtn).not.toBeDisabled()
      })

      fireEvent.click(createBtn)

      await waitFor(() => {
        expect(operationsTasksApi.create).toHaveBeenCalled()
      })

      // 验证 targets 中包含 group_id
      const createCallArg = (operationsTasksApi.create as ReturnType<typeof vi.fn>).mock.calls[0][0]
      expect(createCallArg.targets).toEqual(
        expect.arrayContaining([
          expect.objectContaining({
            group_id: 'g1',
            target_type: 'group',
          }),
        ])
      )
    })
  })

  describe('上一步按钮', () => {
    it('Step 3 点击「上一步」回到 Step 2', async () => {
      renderPage()
      fireEvent.click(screen.getByText('下一步')) // 1→2
      fireEvent.change(screen.getByPlaceholderText('请输入任务名称'), {
        target: { value: '测试' },
      })
      fireEvent.click(screen.getByText('下一步')) // 2→3

      await waitFor(() => {
        expect(screen.getByText('静态选择')).toBeInTheDocument()
      })

      fireEvent.click(screen.getByText('上一步'))

      await waitFor(() => {
        expect(screen.getByPlaceholderText('请输入任务名称')).toBeInTheDocument()
      })
    })
  })
})

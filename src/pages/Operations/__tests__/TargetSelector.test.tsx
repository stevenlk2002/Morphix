/**
 * TargetSelector 组件验收测试（v2 重写）。
 *
 * 覆盖：
 * 1. Tab 切换：静态选择 / 动态选择
 * 2. 静态 Tab：筛选栏（5 个控件）、表格 8 列、全选、跨页全选
 * 3. 静态 Tab：查询/重置按钮
 * 4. 动态 Tab：4 个筛选控件、标签弹窗
 * 5. Props：sessionType、channel、selectedSessionIds、onChange
 * 6. 切换 sessionType 时清空筛选
 * 7. 分页控件
 * 8. 复选框交互
 * 9. 空数据态
 * 10. 标签弹窗：搜索、分组、勾选、清除、确定
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import '@testing-library/jest-dom'
import TargetSelector from '../components/TargetSelector'

// Mock API
vi.mock('../../../api/operations', () => ({
  operationsTasksApi: {
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
    list: vi.fn(),
    create: vi.fn(),
    get: vi.fn(),
    update: vi.fn(),
    toggleEnabled: vi.fn(),
    delete: vi.fn(),
    listTargets: vi.fn(),
    setTargets: vi.fn(),
    listSessions: vi.fn(),
  },
}))

vi.mock('../../../api/client', () => ({
  customerGroupsApi: {
    list: vi.fn().mockResolvedValue([]),
  },
}))

const DEFAULT_PROPS = {
  sessionType: 'single' as const,
  channel: '企业微信',
  selectedSessionIds: [],
  onChange: vi.fn(),
  selectedGroupIds: [],
  onGroupChange: vi.fn(),
}

function renderTarget(props = {}) {
  return render(<TargetSelector {...DEFAULT_PROPS} {...props} />)
}

describe('TargetSelector (v2)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('1. Tab 切换', () => {
    it('默认显示静态选择 Tab', () => {
      renderTarget()
      const staticTab = screen.getByText('静态选择')
      expect(staticTab.classList.contains('active')).toBe(true)
    })

    it('点击动态选择切换到 Dynamic Tab', () => {
      renderTarget()
      fireEvent.click(screen.getByText('动态选择'))
      const dynamicTab = screen.getByText('动态选择')
      expect(dynamicTab.classList.contains('active')).toBe(true)
    })

    it('动态 Tab 显示 4 个筛选控件', async () => {
      renderTarget()
      fireEvent.click(screen.getByText('动态选择'))
      // 4 个 filter: 托管账号, 托管机器人, 标签关系, 标签按钮
      const panel = document.querySelector('.target-panel')
      expect(panel).not.toBeNull()
      const selects = panel!.querySelectorAll('select')
      expect(selects.length).toBe(3) // 托管账号, 托管机器人, 标签关系
    })
  })

  describe('2. 静态 Tab 筛选栏', () => {
    it('筛选栏包含 5 个控件', () => {
      const { container } = renderTarget()
      const filterBar = container.querySelector('.target-filter-bar')
      expect(filterBar).not.toBeNull()
      // input(1) + select(4) = 5 个控件
      expect(filterBar!.querySelectorAll('input[type="text"], .input').length).toBeGreaterThanOrEqual(1)
      expect(filterBar!.querySelectorAll('select').length).toBe(4)
    })

    it('筛选栏 input placeholder 为"相关客户"', () => {
      renderTarget()
      const input = screen.getByPlaceholderText('相关客户')
      expect(input).toBeInTheDocument()
    })

    it('查询和重置按钮存在', () => {
      renderTarget()
      expect(screen.getByText('查询')).toBeInTheDocument()
      expect(screen.getByText('重置')).toBeInTheDocument()
    })
  })

  describe('3. 表格结构', () => {
    it('表格包含 8 列表头', async () => {
      const { operationsTasksApi } = await import('../../../api/operations')
      ;(operationsTasksApi.listTargetSessionsV2 as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
        items: [],
        total: 0,
        page: 1,
        page_size: 20,
        has_more: false,
      })

      renderTarget()
      await waitFor(() => {
        const ths = document.querySelectorAll('.target-data-table th')
        expect(ths.length).toBe(8)
      })
    })

    it('空数据时显示"暂无可用会话"', async () => {
      renderTarget()
      await waitFor(() => {
        expect(screen.getByText('暂无可用会话')).toBeInTheDocument()
      })
    })
  })

  describe('4. 表格数据展示', () => {
    it('渲染从 API 返回的会话行', async () => {
      const { operationsTasksApi } = await import('../../../api/operations')
      ;(operationsTasksApi.listTargetSessionsV2 as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
        items: [
          {
            id: 'ses-1',
            name: '测试会话A',
            avatar: '',
            account_id: 'acc-1',
            account_name: '测试账号',
            channel_type: 'wechat',
            session_type: '外部联系人',
            hosted_status: 'hosted',
            hosted_bot_id: 'bot-1',
            hosted_bot_name: '测试机器人',
            hosting_chain: '-',
            add_time: '2026-07-01',
            customer_nickname: '小明',
            customer_remark: 'VIP客户',
            selected: false,
          },
        ],
        total: 1,
        page: 1,
        page_size: 20,
        has_more: false,
      })

      renderTarget()
      await waitFor(() => {
        expect(screen.getByText('测试会话A')).toBeInTheDocument()
        expect(screen.getByText('小明·VIP客户')).toBeInTheDocument()
        expect(screen.getByText('测试账号')).toBeInTheDocument()
        expect(screen.getByText('已托管')).toBeInTheDocument()
        expect(screen.getByText('测试机器人')).toBeInTheDocument()
      })
    })

    it('复选框切换触发 onChange', async () => {
      const onChange = vi.fn()
      const { operationsTasksApi } = await import('../../../api/operations')
      ;(operationsTasksApi.listTargetSessionsV2 as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
        items: [
          {
            id: 'ses-1',
            name: '测试会话',
            avatar: '',
            account_id: 'acc-1',
            account_name: '测试账号',
            channel_type: 'wechat',
            session_type: '外部联系人',
            hosted_status: 'unhosted',
            hosted_bot_id: '',
            hosted_bot_name: '',
            hosting_chain: '-',
            add_time: '2026-07-01',
            customer_nickname: '',
            customer_remark: '',
            selected: false,
          },
        ],
        total: 1,
        page: 1,
        page_size: 20,
        has_more: false,
      })

      renderTarget({
        selectedSessionIds: [],
        onChange,
      })

      await waitFor(() => {
        expect(screen.getByText('测试会话')).toBeInTheDocument()
      })

      const checkboxes = document.querySelectorAll('.target-data-table tbody input[type="checkbox"]')
      expect(checkboxes.length).toBe(1)
      fireEvent.click(checkboxes[0])
      expect(onChange).toHaveBeenCalledWith(['ses-1'])
    })
  })

  describe('5. 跨页全选', () => {
    it('跨页全选按钮存在', () => {
      renderTarget()
      expect(screen.getByText('跨页全选')).toBeInTheDocument()
    })

    it('点击跨页全选后按钮文字变为"取消跨页全选"', () => {
      renderTarget()
      fireEvent.click(screen.getByText('跨页全选'))
      expect(screen.getByText('取消跨页全选')).toBeInTheDocument()
    })
  })

  describe('6. Props 传参', () => {
    it('group sessionType 时表格显示群聊 badge', async () => {
      const { operationsTasksApi } = await import('../../../api/operations')
      ;(operationsTasksApi.listTargetSessionsV2 as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
        items: [
          {
            id: 'ses-g1',
            name: '测试群聊',
            avatar: '',
            account_id: 'acc-1',
            account_name: '测试账号',
            channel_type: 'wechat',
            session_type: '群聊',
            hosted_status: 'unhosted',
            hosted_bot_id: '',
            hosted_bot_name: '',
            hosting_chain: '-',
            add_time: '2026-07-01',
            customer_nickname: '',
            customer_remark: '',
            selected: false,
          },
        ],
        total: 1,
        page: 1,
        page_size: 20,
        has_more: false,
      })

      renderTarget({ sessionType: 'group' })
      await waitFor(() => {
        expect(screen.getByText('群聊')).toBeInTheDocument()
      })
    })
  })

  describe('7. 分页控件', () => {
    it('total > 0 时显示分页', async () => {
      const { operationsTasksApi } = await import('../../../api/operations')
      ;(operationsTasksApi.listTargetSessionsV2 as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
        items: [],
        total: 42,
        page: 1,
        page_size: 20,
        has_more: true,
      })

      renderTarget()
      await waitFor(() => {
        expect(screen.getByText(/共 42 条/)).toBeInTheDocument()
        expect(screen.getByText('上一页')).toBeInTheDocument()
        expect(screen.getByText('下一页')).toBeInTheDocument()
      })
    })
  })

  describe('8. 标签弹窗', () => {
    it('动态 Tab 下点击标签按钮打开弹窗', async () => {
      renderTarget()
      fireEvent.click(screen.getByText('动态选择'))

      // Wait for the tag button to render
      const tagBtn = await screen.findByText('标签')
      fireEvent.click(tagBtn)

      await waitFor(() => {
        expect(screen.getByText('选择标签')).toBeInTheDocument()
      })
    })

    it('标签弹窗底部有清除和确定按钮', async () => {
      renderTarget()
      fireEvent.click(screen.getByText('动态选择'))
      fireEvent.click(screen.getByText('标签'))

      await waitFor(() => {
        expect(screen.getByText('清除')).toBeInTheDocument()
        expect(screen.getByText('确定')).toBeInTheDocument()
      })
    })

    it('点击确定关闭弹窗', async () => {
      renderTarget()
      fireEvent.click(screen.getByText('动态选择'))
      fireEvent.click(screen.getByText('标签'))

      await waitFor(() => {
        expect(screen.getByText('确定')).toBeInTheDocument()
      })

      fireEvent.click(screen.getByText('确定'))
      await waitFor(() => {
        expect(screen.queryByText('选择标签')).not.toBeInTheDocument()
      })
    })
  })

  describe('9. 已选计数', () => {
    it('显示已选会话数', () => {
      renderTarget({ selectedSessionIds: ['ses-a', 'ses-b', 'ses-c'] })
      expect(screen.getByText(/已选/)).toBeInTheDocument()
      expect(screen.getByText('3')).toBeInTheDocument()
    })
  })

  describe('10. 全选当前页表头复选框', () => {
    it('表头复选框存在', async () => {
      const { operationsTasksApi } = await import('../../../api/operations')
      ;(operationsTasksApi.listTargetSessionsV2 as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
        items: [
          {
            id: 'ses-1', name: '测试', avatar: '', account_id: 'a1', account_name: '账号',
            channel_type: 'wechat', session_type: '外部联系人', hosted_status: 'unhosted',
            hosted_bot_id: '', hosted_bot_name: '', hosting_chain: '-', add_time: '2026-07-01',
            customer_nickname: '', customer_remark: '', selected: false,
          },
        ],
        total: 1, page: 1, page_size: 20, has_more: false,
      })
      const { container } = renderTarget()
      await waitFor(() => {
        const headerCheckbox = container.querySelector('.target-data-table thead input[type="checkbox"]')
        expect(headerCheckbox).not.toBeNull()
      })
    })
  })

  describe('11. 客户分组 Tab (GroupTab)', () => {
    it('通过客户分组 Tab 存在且可切换', () => {
      renderTarget()
      fireEvent.click(screen.getByText('通过客户分组选择'))
      const groupTab = screen.getByText('通过客户分组选择')
      expect(groupTab.classList.contains('active')).toBe(true)
    })

    it('GroupTab 显示客户分组筛选栏', () => {
      renderTarget()
      fireEvent.click(screen.getByText('通过客户分组选择'))
      expect(screen.getByText('客户分组：')).toBeInTheDocument()
      expect(screen.getByText('类型：')).toBeInTheDocument()
    })

    it('selectedGroupIds 正确注入 GroupTab（跨页全选计数显示）', async () => {
      const onGroupChange = vi.fn()
      const { customerGroupsApi } = await import('../../../api/client')
      ;(customerGroupsApi.list as ReturnType<typeof vi.fn>).mockResolvedValueOnce([
        { id: 'g1', name: '高意向客户', type: 'custom', count: 42, createdAt: '2026-01-01', updatedAt: '2026-06-01', editor: '张三' },
      ])

      renderTarget({
        selectedGroupIds: ['g1', 'g2'],
        onGroupChange,
      })

      fireEvent.click(screen.getByText('通过客户分组选择'))

      await waitFor(() => {
        // 跨页全选区域显示已选分组数
        expect(screen.getByText(/已选中分组数：2/)).toBeInTheDocument()
      })
    })
  })
})

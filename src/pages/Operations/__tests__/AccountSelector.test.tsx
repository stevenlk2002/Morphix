/**
 * AccountSelector 组件验收测试。
 *
 * 覆盖：
 * 1. 渲染表格列（☐ | 账号名称 | 渠道类型 | 在线状态 | 备注）
 * 2. 在线账号可勾选，离线账号 checkbox disabled
 * 3. 表头全选仅全选在线账号
 * 4. 已选中 N 个账号计数
 * 5. 空态："该渠道暂无可用账号"
 * 6. channel 变化时重新加载
 * 7. 离线账号 hover 提示
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import '@testing-library/jest-dom'
import AccountSelector from '../components/AccountSelector'

const { mockListChannelAccounts } = vi.hoisted(() => ({
  mockListChannelAccounts: vi.fn(),
}))

vi.mock('../../../api/operations', () => ({
  operationsTasksApi: {
    listChannelAccounts: mockListChannelAccounts,
  },
}))

const MOCK_ACCOUNTS = [
  { id: 'acc-zhulu', account_name: '竹绿-健康', channel_type: 'wecom', status: 'online', display_name: 'wecom / 竹绿-健康' },
  { id: 'acc-hengkang', account_name: '恒康倍力', channel_type: 'wecom', status: 'online', display_name: 'wecom / 恒康倍力' },
  { id: 'acc-fushou', account_name: '福寿康', channel_type: 'wechat', status: 'offline', display_name: 'wechat / 福寿康' },
]

mockListChannelAccounts.mockResolvedValue(MOCK_ACCOUNTS)

const DEFAULT_PROPS = {
  channel: '企业微信',
  selectedIds: [] as string[],
  onChange: vi.fn(),
}

function renderComponent(props = {}) {
  return render(<AccountSelector {...DEFAULT_PROPS} {...props} />)
}

describe('AccountSelector', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('1. 表格结构', () => {
    it('渲染 5 列表头：☐ / 账号名称 / 渠道类型 / 在线状态 / 备注', async () => {
      renderComponent()
      await waitFor(() => {
        expect(screen.getByText('账号名称')).toBeInTheDocument()
        expect(screen.getByText('渠道类型')).toBeInTheDocument()
        expect(screen.getByText('在线状态')).toBeInTheDocument()
        expect(screen.getByText('备注')).toBeInTheDocument()
      })
    })

    it('渲染所有账号行', async () => {
      renderComponent()
      await waitFor(() => {
        expect(screen.getByText('竹绿-健康')).toBeInTheDocument()
        expect(screen.getByText('恒康倍力')).toBeInTheDocument()
        expect(screen.getByText('福寿康')).toBeInTheDocument()
      })
    })
  })

  describe('2. 在线/离线状态交互', () => {
    it('在线账号复选框可勾选', async () => {
      const onChange = vi.fn()
      renderComponent({ selectedIds: [], onChange })

      await waitFor(() => {
        expect(screen.getByText('竹绿-健康')).toBeInTheDocument()
      })

      const checkboxes = document.querySelectorAll('.target-data-table tbody input[type="checkbox"]')
      // 两个在线 + 一个离线
      expect(checkboxes.length).toBe(3)

      // 在线账号可点击
      const onlineCb = checkboxes[0] as HTMLInputElement
      expect(onlineCb.disabled).toBe(false)
      fireEvent.click(onlineCb)
      expect(onChange).toHaveBeenCalledWith(['acc-zhulu'])
    })

    it('离线账号复选框 disabled 且不可点击', async () => {
      const onChange = vi.fn()
      renderComponent({ selectedIds: [], onChange })

      await waitFor(() => {
        expect(screen.getByText('福寿康')).toBeInTheDocument()
      })

      const checkboxes = document.querySelectorAll('.target-data-table tbody input[type="checkbox"]')
      const offlineCb = checkboxes[2] as HTMLInputElement
      expect(offlineCb.disabled).toBe(true)
    })

    it('离线账号 hover 提示"该账号离线，无法发送朋友圈"', async () => {
      renderComponent()

      await waitFor(() => {
        expect(screen.getByText('福寿康')).toBeInTheDocument()
      })

      const checkboxes = document.querySelectorAll('.target-data-table tbody input[type="checkbox"]')
      const offlineCb = checkboxes[2] as HTMLInputElement
      expect(offlineCb.title).toBe('该账号离线，无法发送朋友圈')
    })

    it('离线账号行文字为灰色', async () => {
      renderComponent()

      await waitFor(() => {
        expect(screen.getByText('福寿康')).toBeInTheDocument()
      })

      // 离线行应有 text-tertiary 样式
      const rows = document.querySelectorAll('.target-data-table tbody tr')
      const offlineRow = rows[2] as HTMLElement
      expect(offlineRow.style.color).toBe('var(--text-tertiary)')
    })
  })

  describe('3. 表头全选', () => {
    it('表头全选仅全选在线账号，跳过离线', async () => {
      const onChange = vi.fn()
      renderComponent({ selectedIds: [], onChange })

      await waitFor(() => {
        expect(screen.getByText('竹绿-健康')).toBeInTheDocument()
      })

      const headerCb = document.querySelector('.target-data-table thead input[type="checkbox"]') as HTMLInputElement
      expect(headerCb).not.toBeNull()
      fireEvent.click(headerCb)

      // 应只选中 2 个在线账号
      expect(onChange).toHaveBeenCalledWith(['acc-zhulu', 'acc-hengkang'])
    })

    it('全选后再点击表头，取消所有在线账号勾选', async () => {
      const onChange = vi.fn()
      renderComponent({ selectedIds: ['acc-zhulu', 'acc-hengkang'], onChange })

      await waitFor(() => {
        expect(screen.getByText('竹绿-健康')).toBeInTheDocument()
      })

      const headerCb = document.querySelector('.target-data-table thead input[type="checkbox"]') as HTMLInputElement
      fireEvent.click(headerCb)
      expect(onChange).toHaveBeenCalledWith([])
    })
  })

  describe('4. 已选计数', () => {
    it('显示已选中 N 个账号', async () => {
      renderComponent({ selectedIds: ['acc-zhulu'] })

      await waitFor(() => {
        expect(screen.getByText(/已选中/)).toBeInTheDocument()
        expect(screen.getByText('1')).toBeInTheDocument()
      })
    })

    it('未选中时显示 0', async () => {
      renderComponent()

      await waitFor(() => {
        expect(screen.getByText(/已选中/)).toBeInTheDocument()
        expect(screen.getByText('0')).toBeInTheDocument()
      })
    })
  })

  describe('5. 空态', () => {
    it('无账号时显示"该渠道暂无可用账号"', async () => {
      mockListChannelAccounts.mockResolvedValueOnce([])

      renderComponent()
      await waitFor(() => {
        expect(screen.getByText('该渠道暂无可用账号')).toBeInTheDocument()
      })
    })
  })

  describe('6. channel 变化', () => {
    it('channel 变化时重新请求 API', async () => {
      const { rerender } = render(<AccountSelector channel="企业微信" selectedIds={[]} onChange={vi.fn()} />)

      await waitFor(() => {
        expect(mockListChannelAccounts).toHaveBeenCalledWith('wecom')
      })

      mockListChannelAccounts.mockClear()
      rerender(<AccountSelector channel="微信" selectedIds={[]} onChange={vi.fn()} />)

      await waitFor(() => {
        expect(mockListChannelAccounts).toHaveBeenCalledWith('wechat')
      })
    })
  })

  describe('7. 取消勾选', () => {
    it('已勾选账号点击取消勾选', async () => {
      const onChange = vi.fn()
      renderComponent({ selectedIds: ['acc-zhulu'], onChange })

      await waitFor(() => {
        expect(screen.getByText('竹绿-健康')).toBeInTheDocument()
      })

      const checkboxes = document.querySelectorAll('.target-data-table tbody input[type="checkbox"]')
      const cb = checkboxes[0] as HTMLInputElement
      expect(cb.checked).toBe(true)
      fireEvent.click(cb)
      expect(onChange).toHaveBeenCalledWith([])
    })
  })
})

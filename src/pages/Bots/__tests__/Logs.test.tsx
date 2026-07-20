import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react'
import '@testing-library/jest-dom'
import BotLogsPage from '../Logs'
import { messageLogApi } from '../../../api/client'

// 自动 mock：messageLogApi.list / getDetail 变为 vi.fn
// 注意：本测试文件位于 src/pages/Bots/__tests__/，向上三级才是 src/
vi.mock('../../../utils/toast', () => ({ toast: vi.fn() }))
vi.mock('../../../api/client')

const listMock = vi.mocked(messageLogApi).list
const detailMock = vi.mocked(messageLogApi).getDetail

const makeItems = (n: number) =>
  Array.from({ length: n }, (_, i) => ({
    id: `AI${i}`,
    content: { text: 't', type: 'text' },
    question: '',
    account: '竹绿-健康',
    session: 'Dr.Jack',
    robot: '',
    channel: '企业微信',
    time: '2026-07-09 18:00:00',
    status: '成功' as const,
  }))

const detailData = {
  id: 'AI0',
  content: { text: 't', type: 'text' },
  question: '',
  account: '竹绿-健康',
  session: 'Dr.Jack',
  robot: '',
  channel: '企业微信',
  time: '2026-07-09 18:00:00',
  status: '成功' as const,
  nodes: [
    {
      name: '用户输入',
      icon: 'user',
      runtime: '0.1s',
      input: { a: 1 },
      output: { b: 2 },
      code: 'print(1)',
    },
  ],
}

beforeEach(() => {
  listMock.mockReset()
  detailMock.mockReset()
  listMock.mockResolvedValue({ items: makeItems(20), total: 45, page: 1, pageSize: 20, hasMore: true })
  detailMock.mockResolvedValue(detailData)
})

describe('托管消息日志页 - 头部与筛选区对齐原型', () => {
  it('头部：标题 + 三个无文字图标按钮，副标题已移除', async () => {
    render(<BotLogsPage />)
    expect(screen.getByText('托管消息日志')).toBeInTheDocument()
    expect(screen.queryByText(/查看 AI 托管期间/)).toBeNull()

    const refresh = screen.getByTitle('刷新')
    const filter = screen.getByTitle('筛选')
    const settings = screen.getByTitle('列设置')
    // 无文字：按钮内仅含图标 svg
    expect(refresh.textContent).toBe('')
    expect(filter.textContent).toBe('')
    expect(settings.textContent).toBe('')
  })

  it('筛选区：4 列 × 2 排网格，占位符与下拉选项对齐原型', async () => {
    const { container } = render(<BotLogsPage />)
    const fields = container.querySelectorAll('.message-logs-filters > .filter-field')
    expect(fields).toHaveLength(8)

    expect(screen.getAllByPlaceholderText('请输入')).toHaveLength(2)
    expect(screen.getByPlaceholderText('2026-07-04')).toBeInTheDocument()
    expect(screen.getByPlaceholderText('2026-07-10')).toBeInTheDocument()

    const selects = container.querySelectorAll('select')
    // 顺序：所属会话 / 所属机器人 / AI回复状态 / 每页条数
    expect(selects).toHaveLength(4)
    expect(selects[0].options[0].textContent).toBe('请输入会话名称搜索')
    const robotLabels = Array.from(selects[1].options).map((o) => o.textContent)
    expect(robotLabels).toEqual(
      expect.arrayContaining(['野风秋大健康机器人', '梵芙尼美妆销售机器人'])
    )
    const statusLabels = Array.from(selects[2].options).map((o) => o.textContent)
    expect(statusLabels).toEqual(expect.arrayContaining(['成功', '失败', '处理中']))

    const queryBtn = screen.getByText('查询')
    const resetBtn = screen.getByText('重置')
    expect(queryBtn).toHaveClass('logs-btn-query')
    expect(resetBtn).toHaveClass('logs-btn-reset')
  })

  it('查询按钮为金棕色主按钮、重置为白底边框次要按钮（样式类）', () => {
    render(<BotLogsPage />)
    const queryBtn = screen.getByText('查询')
    const resetBtn = screen.getByText('重置')
    expect(queryBtn.className).toContain('logs-btn-query')
    expect(resetBtn.className).toContain('logs-btn-reset')
  })
})

describe('托管消息日志页 - 业务逻辑未回退', () => {
  it('挂载即按默认作用域与日期范围调用 messageLogApi.list', async () => {
    render(<BotLogsPage />)
    await waitFor(() => expect(listMock).toHaveBeenCalled())
    const [botId, params] = listMock.mock.calls[0] as [string, Record<string, unknown>]
    // 默认未选机器人 → yefengqiu 作用域
    expect(botId).toBe('yefengqiu')
    expect(params).toMatchObject({
      start: '2026-07-04',
      end: '2026-07-10',
      page: 1,
      pageSize: 20,
    })
    expect(params.aiReplyId).toBeUndefined()
    expect(await screen.findByText('AI0')).toBeInTheDocument()
  })

  it('筛选输入会流入接口参数（AI回复id）', async () => {
    render(<BotLogsPage />)
    await waitFor(() => expect(listMock).toHaveBeenCalled())
    fireEvent.change(screen.getAllByPlaceholderText('请输入')[0], {
      target: { value: 'AI123' },
    })
    await waitFor(() => {
      const last = listMock.mock.calls[listMock.mock.calls.length - 1] as [string, Record<string, unknown>]
      expect(last[1].aiReplyId).toBe('AI123')
    })
  })

  it('分页：下一页触发 page=2 的拉取', async () => {
    render(<BotLogsPage />)
    await waitFor(() => expect(listMock).toHaveBeenCalled())
    const next = screen.getByText('下一页')
    expect(next).not.toBeDisabled()
    fireEvent.click(next)
    await waitFor(() => {
      const last = listMock.mock.calls[listMock.mock.calls.length - 1] as [string, Record<string, unknown>]
      expect(last[1].page).toBe(2)
    })
  })

  it('列设置：勾选框可切换可见列', async () => {
    render(<BotLogsPage />)
    fireEvent.click(screen.getByTitle('列设置'))
    const menu = await screen.findByRole('menu')
    const boxes = within(menu).getAllByRole('checkbox')
    expect(boxes).toHaveLength(9)
    expect(boxes[0]).toBeChecked()
    fireEvent.click(boxes[0])
    const boxes2 = within(screen.getByRole('menu')).getAllByRole('checkbox')
    expect(boxes2[0]).not.toBeChecked()
  })

  it('详情弹窗：点击查看回复详情调用 getDetail 并渲染节点追踪', async () => {
    render(<BotLogsPage />)
    const links = await screen.findAllByText('查看回复详情')
    fireEvent.click(links[0])
    await waitFor(() =>
      expect(detailMock).toHaveBeenCalledWith('yefengqiu', expect.any(String))
    )
    expect(await screen.findByText('回复详情')).toBeInTheDocument()
    expect(screen.getByText('模块输入值')).toBeInTheDocument()
    expect(screen.getByText('模块输出值')).toBeInTheDocument()
    expect(screen.getByText('源码片段')).toBeInTheDocument()
  })

  it('重置：清空筛选条件并重新拉取', async () => {
    render(<BotLogsPage />)
    await waitFor(() => expect(listMock).toHaveBeenCalled())
    fireEvent.change(screen.getAllByPlaceholderText('请输入')[0], {
      target: { value: 'XYZ' },
    })
    await waitFor(() => {
      const last = listMock.mock.calls[listMock.mock.calls.length - 1] as [string, Record<string, unknown>]
      expect(last[1].aiReplyId).toBe('XYZ')
    })
    fireEvent.click(screen.getByText('重置'))
    await waitFor(() => {
      const last = listMock.mock.calls[listMock.mock.calls.length - 1] as [string, Record<string, unknown>]
      expect(last[1].aiReplyId).toBeUndefined()
      expect(last[1].start).toBeUndefined()
      expect(last[0]).toBe('yefengqiu')
    })
    expect((screen.getAllByPlaceholderText('请输入')[0] as HTMLInputElement).value).toBe('')
  })
})

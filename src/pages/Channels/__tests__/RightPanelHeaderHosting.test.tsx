/**
 * 「托管开关前置校验」前端行为验证（QA 补充）。
 *
 * 工程师侧仅补充了后端用例，本文件补齐前端这一半：
 * 1. 未选机器人时打开开关 → warning toast + 不发请求；
 * 2. 已选机器人时打开开关 → 正常发请求；
 * 3. 关闭托管不做机器人校验；
 * 4. 校验拦截时开关保持关闭（受控回弹）。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import '@testing-library/jest-dom'
import { MemoryRouter } from 'react-router-dom'
import RightPanelHeader from '../sessions/RightPanelHeader'
import { channelsApi } from '../../../api/client'
import { toast } from '../../../utils/toast'
import type { AccountDTO, HostingBotDTO, SessionDTO } from '../../../types/channels'

vi.mock('../../../api/client')
vi.mock('../../../utils/toast', async () => {
  const actual = await vi.importActual<typeof import('../../../utils/toast')>(
    '../../../utils/toast'
  )
  return { ...actual, toast: vi.fn() }
})

const setHostingMock = vi.mocked(channelsApi).setSessionHosting
const toastMock = vi.mocked(toast)

const BOTS: HostingBotDTO[] = [
  { id: 'yefengqiu', name: '野风秋大健康机器人', avatar: '🤖' },
  { id: 'zhulu', name: '竹绿健康助手', avatar: '🤖' },
]

const ACCOUNT: AccountDTO = {
  id: 'acc-1',
  name: '竹绿-健康',
  channel: '企业微信',
  status: 'online',
} as unknown as AccountDTO

function makeSession(overrides: Partial<SessionDTO> = {}): SessionDTO {
  return {
    id: 'acc-1:ses-1',
    accountId: 'acc-1',
    contactId: null,
    remoteSessionId: 'u-1',
    name: '张三',
    channel: '企业微信',
    channelType: 'wecom',
    lastMessage: '',
    lastTime: '',
    unreadCount: 0,
    readStatus: 'read',
    hostedStatus: 'unhosted',
    hostedBotId: null,
    owner: '',
    onlineStatus: 'online',
    sessionType: '单聊',
    externalTag: '外部',
    addTime: '',
    hostingChain: '',
    ...overrides,
  }
}

function renderHeader(session: SessionDTO, onHostingChange = vi.fn()) {
  render(
    <MemoryRouter>
      <RightPanelHeader
        session={session}
        bots={BOTS}
        account={ACCOUNT}
        onHostingChange={onHostingChange}
      />
    </MemoryRouter>
  )
  return { onHostingChange }
}

const getToggle = () => screen.getByRole('checkbox') as HTMLInputElement

describe('托管开关前置校验（前端）', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('未选机器人时打开开关：提示 warning 且不发起请求', async () => {
    renderHeader(makeSession({ hostedBotId: null, hostedStatus: 'unhosted' }))

    fireEvent.click(getToggle())

    await waitFor(() => expect(toastMock).toHaveBeenCalledTimes(1))
    expect(toastMock).toHaveBeenCalledWith(
      '请先选择机器人',
      expect.objectContaining({ level: 'warning' })
    )
    // 关键：被拦截时绝不能打到后端
    expect(setHostingMock).not.toHaveBeenCalled()
  })

  it('未选机器人被拦截后：开关保持关闭（受控回弹）', async () => {
    renderHeader(makeSession({ hostedBotId: null, hostedStatus: 'unhosted' }))

    fireEvent.click(getToggle())

    await waitFor(() => expect(toastMock).toHaveBeenCalled())
    expect(getToggle().checked).toBe(false)
  })

  it('botId 为空串时同样被拦截', async () => {
    renderHeader(makeSession({ hostedBotId: '', hostedStatus: 'unhosted' }))

    fireEvent.click(getToggle())

    await waitFor(() => expect(toastMock).toHaveBeenCalled())
    expect(setHostingMock).not.toHaveBeenCalled()
  })

  it('已选机器人时打开开关：正常发起请求并回传结果', async () => {
    const session = makeSession({ hostedBotId: 'zhulu', hostedStatus: 'unhosted' })
    const next = makeSession({ hostedBotId: 'zhulu', hostedStatus: 'hosted' })
    setHostingMock.mockResolvedValue(next)
    const { onHostingChange } = renderHeader(session)

    fireEvent.click(getToggle())

    await waitFor(() => expect(setHostingMock).toHaveBeenCalledTimes(1))
    expect(setHostingMock).toHaveBeenCalledWith('acc-1:ses-1', {
      hosted: true,
      botId: 'zhulu',
    })
    expect(toastMock).not.toHaveBeenCalled()
    await waitFor(() => expect(onHostingChange).toHaveBeenCalledWith(next))
  })

  it('关闭托管：不做机器人校验，直接发请求', async () => {
    const session = makeSession({ hostedBotId: 'zhulu', hostedStatus: 'hosted' })
    setHostingMock.mockResolvedValue(
      makeSession({ hostedBotId: 'zhulu', hostedStatus: 'unhosted' })
    )
    renderHeader(session)

    expect(getToggle().checked).toBe(true)
    fireEvent.click(getToggle())

    await waitFor(() => expect(setHostingMock).toHaveBeenCalledTimes(1))
    expect(setHostingMock).toHaveBeenCalledWith('acc-1:ses-1', {
      hosted: false,
      botId: 'zhulu',
    })
    expect(toastMock).not.toHaveBeenCalled()
  })

  it('请求失败时提示错误（拦截路径不应走到这里）', async () => {
    setHostingMock.mockRejectedValue(new Error('请先选择机器人'))
    renderHeader(makeSession({ hostedBotId: 'zhulu', hostedStatus: 'unhosted' }))

    fireEvent.click(getToggle())

    await waitFor(() => expect(toastMock).toHaveBeenCalled())
    expect(String(toastMock.mock.calls[0][0])).toContain('托管切换失败')
  })
})

/**
 * `shared/sessionKind` 单测 —— 会话实体语义判定的单一事实来源。
 *
 * 这两个函数被会话列表（ChannelSessions）、右侧头部（RightPanelHeader）、
 * 聊天面板（SessionChatPanel）三处共同消费，判定一旦漂移就会出现
 * 「列表不显示徽标、但输入框被禁用」这类跨组件不一致，故单独钉死。
 */
import { describe, it, expect } from 'vitest'

import { isAppSession, appBadgeText } from '../sessionKind'
import type { SessionDTO } from '../../../../types/channels'

/** 构造最小可用的 SessionDTO，只覆盖被测字段。 */
function makeSession(over: Partial<SessionDTO> = {}): SessionDTO {
  return {
    id: 'acc-1:s1',
    accountId: 'acc-1',
    name: '张三',
    channel: '企业微信',
    ...over,
  } as SessionDTO
}

describe('isAppSession', () => {
  it('entityKind 为 app 时判定为应用', () => {
    expect(isAppSession(makeSession({ entityKind: 'app' }))).toBe(true)
  })

  it('entityKind 为 service（开放平台 msg_type=6）不判定为应用', () => {
    // 对拍结论：msg_type=6 实测有真实 outbound，必须可发送，不能置灰输入框。
    expect(isAppSession(makeSession({ entityKind: 'service' }))).toBe(false)
  })

  it('entityKind 为 person 不判定为应用', () => {
    expect(isAppSession(makeSession({ entityKind: 'person' }))).toBe(false)
  })

  it('entityKind 为 group 不判定为应用', () => {
    expect(isAppSession(makeSession({ entityKind: 'group' }))).toBe(false)
  })

  it('会话为 null / undefined 时返回 false', () => {
    expect(isAppSession(null)).toBe(false)
    expect(isAppSession(undefined)).toBe(false)
  })

  // --- 边界：语义字段冲突时以 entityKind 为准 --------------------------------
  it('readonly=true 但 entityKind=person 时不视为应用', () => {
    // 后端不变式是 readonly ⟺ entityKind==='app'，两者冲突只可能是数据被污染
    // （如 list_sessions 空串 JOIN 把应用行冒名到真人会话）。此时信任 entityKind，
    // 否则真人会话会被连带禁掉输入框。
    expect(isAppSession(makeSession({ entityKind: 'person', readonly: true }))).toBe(false)
  })

  it('sessionType=应用 但 entityKind=person 时不视为应用', () => {
    expect(
      isAppSession(makeSession({ entityKind: 'person', sessionType: '应用' })),
    ).toBe(false)
  })

  it('entityKind=app 时即使 readonly=false 仍视为应用', () => {
    expect(isAppSession(makeSession({ entityKind: 'app', readonly: false }))).toBe(true)
  })

  // --- 旧版后端兼容兜底：不下发 entityKind 时回落 readonly / sessionType ------
  it('缺省 entityKind 时 readonly=true 仍判定为应用（旧后端兜底）', () => {
    expect(isAppSession(makeSession({ readonly: true }))).toBe(true)
  })

  it('缺省 entityKind 时 sessionType=应用 仍判定为应用（旧后端兜底）', () => {
    expect(isAppSession(makeSession({ sessionType: '应用' }))).toBe(true)
  })

  it('三个字段都缺省时返回 false', () => {
    expect(isAppSession(makeSession())).toBe(false)
  })
})

describe('appBadgeText', () => {
  it('appType=2 显示「小程序」', () => {
    expect(appBadgeText(makeSession({ entityKind: 'app', appType: 2 }))).toBe('小程序')
  })

  it('appType=0（普通应用）显示「应用」', () => {
    expect(appBadgeText(makeSession({ entityKind: 'app', appType: 0 }))).toBe('应用')
  })

  it('appType 为其他未知值显示「应用」', () => {
    expect(appBadgeText(makeSession({ entityKind: 'app', appType: 99 }))).toBe('应用')
  })

  it('缺省 appType 显示「应用」', () => {
    expect(appBadgeText(makeSession({ entityKind: 'app' }))).toBe('应用')
  })

  it('会话为 null / undefined 时降级显示「应用」', () => {
    expect(appBadgeText(null)).toBe('应用')
    expect(appBadgeText(undefined)).toBe('应用')
  })
})

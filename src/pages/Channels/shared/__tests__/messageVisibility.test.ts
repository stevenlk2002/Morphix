/**
 * 消息可见性判定单测（回归：聊天框成片「只有时间戳的空蓝气泡」）。
 *
 * 覆盖：
 * 1. 控制/回执类 msgType（2001/2118/2131）一律不渲染；
 * 2. 正文为空 / 纯空白 / 纯控制字符（protobuf 裸字节）不渲染；
 * 3. 携带 mediaUrl 的消息即使正文为空也要渲染（不误伤图片/表情）；
 * 4. 正常文本、系统提示、微信文字表情正常渲染；
 * 5. filterVisibleMessages 保持原顺序、不改变原数组。
 */

import { describe, it, expect } from 'vitest'
import type { MessageExtDTO } from '../../../../types/channels'
import {
  CONTROL_MSG_TYPES,
  cleanMessageText,
  filterVisibleMessages,
  isVisibleMessage,
} from '../messageVisibility'

function msg(over: Partial<MessageExtDTO> = {}): MessageExtDTO {
  return {
    id: 'm1',
    conversationId: 'acc-1:7881302555913738',
    senderType: 'user',
    content: '你好',
    createdAt: '2026-03-25T13:35:00',
    serverId: '7130717',
    msgType: 2,
    senderId: '7881302555913738',
    senderAvatar: '',
    direction: 'inbound',
    contentType: 'text',
    mediaUrl: '',
    mediaMeta: null,
    isRead: false,
    channelAccountId: 'acc-1',
    ...over,
  }
}

describe('CONTROL_MSG_TYPES', () => {
  it('与后端 ipad_sync.CONTROL_EVENT_MSG_TYPES 对齐', () => {
    expect([...CONTROL_MSG_TYPES].sort((a, b) => a - b)).toEqual([2001, 2118, 2131])
  })
})

describe('cleanMessageText', () => {
  it('剔除控制字符并去空白', () => {
    expect(cleanMessageText('\n\x06\x08\x00\x12\x02\n\x00')).toBe('')
    expect(cleanMessageText('   ')).toBe('')
    expect(cleanMessageText(null)).toBe('')
    expect(cleanMessageText(undefined)).toBe('')
    expect(cleanMessageText(' 你好 ')).toBe('你好')
  })

  it('保留正常换行与表情文本', () => {
    expect(cleanMessageText('第一行\n第二行')).toBe('第一行\n第二行')
    expect(cleanMessageText('[强][微笑]')).toBe('[强][微笑]')
  })
})

describe('isVisibleMessage', () => {
  it('控制/回执类事件不渲染', () => {
    expect(isVisibleMessage(msg({ msgType: 2001, content: '' }))).toBe(false)
    expect(isVisibleMessage(msg({ msgType: 2118, content: '' }))).toBe(false)
    expect(isVisibleMessage(msg({ msgType: 2131, content: '' }))).toBe(false)
  })

  it('控制类事件即使带历史脏正文也不渲染', () => {
    // 历史实现把 2001 误判为表情，库里遗留了一批 content='[表情]' 的脏数据
    expect(isVisibleMessage(msg({ msgType: 2001, content: '[表情]' }))).toBe(false)
  })

  it('控制类事件若携带真实媒体 URL 仍渲染（不误伤动画表情）', () => {
    expect(
      isVisibleMessage(
        msg({ msgType: 2001, content: '', contentType: 'image', mediaUrl: 'https://x/a.gif' })
      )
    ).toBe(true)
  })

  it('空正文 / 纯空白 / protobuf 裸字节不渲染', () => {
    expect(isVisibleMessage(msg({ content: '' }))).toBe(false)
    expect(isVisibleMessage(msg({ content: '   ' }))).toBe(false)
    expect(isVisibleMessage(msg({ msgType: 1002, content: '' }))).toBe(false)
    expect(isVisibleMessage(msg({ msgType: 99999, content: '\x00\x01\x02' }))).toBe(false)
  })

  it('正常文本 / 系统提示 / 文字表情正常渲染', () => {
    expect(isVisibleMessage(msg({ content: '你好' }))).toBe(true)
    expect(isVisibleMessage(msg({ msgType: 0, content: '你还好' }))).toBe(true)
    expect(isVisibleMessage(msg({ msgType: 1011, content: '已提醒成员填写汇报' }))).toBe(true)
    expect(isVisibleMessage(msg({ msgType: 1022, content: '加入了群聊' }))).toBe(true)
    expect(isVisibleMessage(msg({ msgType: 0, content: '[强][强]' }))).toBe(true)
  })

  it('图片/文件消息正文为空但有媒体 → 渲染', () => {
    expect(
      isVisibleMessage(msg({ msgType: 101, content: '', contentType: 'image', mediaUrl: 'https://x/a.png' }))
    ).toBe(true)
    expect(
      isVisibleMessage(msg({ msgType: 102, content: '', contentType: 'file', mediaUrl: 'https://x/a.pdf' }))
    ).toBe(true)
  })

  it('msgType 缺省（乐观追加的本地消息）按正文判定', () => {
    const local = { ...msg({ content: '本地发送' }) } as MessageExtDTO
    delete (local as Partial<MessageExtDTO>).msgType
    expect(isVisibleMessage(local)).toBe(true)
  })
})

describe('filterVisibleMessages', () => {
  it('剔除空气泡并保持原顺序、不改动入参', () => {
    const input: MessageExtDTO[] = [
      msg({ id: 'a', msgType: 2001, content: '' }),
      msg({ id: 'b', content: '你还好' }),
      msg({ id: 'c', msgType: 2131, content: '' }),
      msg({ id: 'd', msgType: 2118, content: '\n\x06\x08\x00' }),
      msg({ id: 'e', content: '你好' }),
    ]
    const out = filterVisibleMessages(input)
    expect(out.map((m) => m.id)).toEqual(['b', 'e'])
    expect(input).toHaveLength(5)
  })

  it('全为控制事件时返回空数组（由调用方展示「暂无聊天记录」）', () => {
    const out = filterVisibleMessages([
      msg({ id: 'a', msgType: 2001, content: '' }),
      msg({ id: 'b', msgType: 2001, content: '' }),
    ])
    expect(out).toEqual([])
  })
})

/**
 * `shared/wecomEmoji` 单测 —— 表情码渲染层的单一事实来源。
 *
 * 钉死两条不变式：
 * 1. 表情码（`[强]`/`[微笑]`）必须替换成 Unicode emoji；
 * 2. 后端结构占位（`[表情]`/`[图片]`/`[文件]`…）必须原样保留，
 *    否则会把「一条图片消息」误渲染成一个 emoji，产生语义错误。
 */
import { describe, it, expect } from 'vitest'

import {
  renderWecomContent,
  renderWecomEmoji,
  emotionPlaceholder,
  WECOM_EMOJI_MAP,
  STRUCTURAL_PLACEHOLDERS,
} from '../wecomEmoji'

describe('renderWecomContent', () => {
  it('连续表情码逐个替换：[强][强] → 👍👍', () => {
    expect(renderWecomContent('[强][强]')).toBe('👍👍')
  })

  it('线上真实样本：[强][强][强][强] → 👍👍👍👍', () => {
    expect(renderWecomContent('[强][强][强][强]')).toBe('👍👍👍👍')
  })

  it('表情码混排在正文中：这个AI发的[微笑] → 这个AI发的😊', () => {
    expect(renderWecomContent('这个AI发的[微笑]')).toBe('这个AI发的😊')
  })

  it('多个不同表情码同时替换', () => {
    expect(renderWecomContent('[握手]辛苦了[玫瑰]')).toBe('🤝辛苦了🌹')
  })

  it('英文表情码 [OK] 可替换', () => {
    expect(renderWecomContent('[OK] 收到')).toBe('🆗 收到')
  })

  // --- 结构占位保护：这是最容易回归的一类 Bug ------------------------------
  it('[表情] 是后端结构占位，不替换', () => {
    expect(renderWecomContent('[表情]')).toBe('[表情]')
  })

  it('[动画表情] 是后端结构占位，不替换', () => {
    expect(renderWecomContent('[动画表情]')).toBe('[动画表情]')
  })

  it('[图片] / [文件] / [位置] 等结构占位一律不替换', () => {
    expect(renderWecomContent('[图片]')).toBe('[图片]')
    expect(renderWecomContent('[文件] report.pdf')).toBe('[文件] report.pdf')
    expect(renderWecomContent('[位置] 深圳市南山区')).toBe('[位置] 深圳市南山区')
    expect(renderWecomContent('[链接] Morphix 发布说明')).toBe('[链接] Morphix 发布说明')
  })

  // --- 边界 ----------------------------------------------------------------
  it('未收录的表情码原样保留，不丢字', () => {
    expect(renderWecomContent('[某个没收录的码]')).toBe('[某个没收录的码]')
    expect(renderWecomContent('[强][未知码]')).toBe('👍[未知码]')
  })

  it('无表情码的纯文本原样返回', () => {
    expect(renderWecomContent('今天下午三点开会')).toBe('今天下午三点开会')
  })

  it('空串 / 空值安全', () => {
    expect(renderWecomContent('')).toBe('')
    expect(renderWecomContent(undefined as unknown as string)).toBe('')
  })

  it('方括号包裹的超长文本不被当作表情码吞掉', () => {
    const long = '[这是一段超过十二个字符的普通方括号文本内容]'
    expect(renderWecomContent(long)).toBe(long)
  })

  it('renderWecomEmoji 是 renderWecomContent 的别名', () => {
    expect(renderWecomEmoji).toBe(renderWecomContent)
  })
})

describe('emotionPlaceholder', () => {
  it('纯 [表情] 命中徽标降级', () => {
    expect(emotionPlaceholder('[表情]')).toEqual({ icon: '💬', label: '表情' })
  })

  it('纯 [动画表情] 命中徽标降级', () => {
    expect(emotionPlaceholder('[动画表情]')).toEqual({ icon: '🎭', label: '动画表情' })
  })

  it('首尾空白不影响命中', () => {
    expect(emotionPlaceholder('  [表情]  ')).toEqual({ icon: '💬', label: '表情' })
  })

  it('混在正文中的占位不降级（避免吞掉上下文）', () => {
    expect(emotionPlaceholder('他回了个[表情]')).toBeNull()
  })

  it('普通文本 / 空值返回 null', () => {
    expect(emotionPlaceholder('你好')).toBeNull()
    expect(emotionPlaceholder('')).toBeNull()
  })
})

describe('映射表自身约束', () => {
  it('结构占位不得出现在表情码映射表中（否则会被替换）', () => {
    for (const name of STRUCTURAL_PLACEHOLDERS) {
      expect(WECOM_EMOJI_MAP[name]).toBeUndefined()
    }
  })

  it('映射表覆盖常用表情码且值非空', () => {
    const required = ['微笑', '强', '弱', '握手', 'OK', '抱拳', '玫瑰', '爱心', '大哭', '呲牙']
    for (const key of required) {
      expect(WECOM_EMOJI_MAP[key], `缺失表情码 [${key}]`).toBeTruthy()
    }
    expect(Object.keys(WECOM_EMOJI_MAP).length).toBeGreaterThanOrEqual(40)
  })
})

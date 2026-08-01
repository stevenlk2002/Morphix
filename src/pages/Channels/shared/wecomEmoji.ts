/**
 * 企业微信 / 微信「方括号表情码」→ Unicode emoji 的渲染层转换。
 *
 * 背景（Bug：表情消息在聊天框显示成 `[强][强]` / `[表情]`）：
 * 协议侧对「文字表情」只下发编码文本（`这个AI发的[微笑]`），对 GIF/动画表情
 * 在无图片 URL 时由后端 `_render_message_content` 兜底成 `[表情]`/`[动画表情]`。
 * 后端**不做**替换（保证落库数据保真、可反查原始协议编码），替换只发生在
 * 前端渲染期，这里是该转换的单一事实来源。
 *
 * 两类方括号 token 必须区分对待：
 * 1. **表情码**（`[强]`/`[微笑]`）——协议原文，替换成对应 emoji；
 * 2. **结构占位**（`[表情]`/`[图片]`/`[文件]`…）——后端为非文本消息生成的
 *    可读摘要，不是表情码，替换会产生语义错误，必须原样保留。
 */

/**
 * 常见微信 / 企业微信表情码映射表。
 *
 * 键为方括号内的原文（不含中括号），值为语义最接近的 Unicode emoji。
 * 未收录的表情码在渲染时**保持原样**，不做任何猜测替换。
 */
export const WECOM_EMOJI_MAP: Record<string, string> = {
  // --- 手势 / 动作 ---
  强: '👍',
  弱: '👎',
  握手: '🤝',
  OK: '🆗',
  ok: '🆗',
  抱拳: '🙏',
  勾引: '💁',
  拳头: '✊',
  胜利: '✌️',
  再见: '👋',
  差劲: '👎',
  爱你: '🤟',
  NO: '🙅',
  no: '🙅',
  鼓掌: '👏',
  合十: '🙏',
  加油: '💪',
  拥抱: '🤗',

  // --- 表情 / 情绪 ---
  微笑: '😊',
  笑脸: '😄',
  撇嘴: '😖',
  色: '😍',
  发呆: '😳',
  得意: '😎',
  流泪: '😭',
  害羞: '😊',
  闭嘴: '🤐',
  睡: '😴',
  大哭: '😢',
  尴尬: '😅',
  发怒: '😡',
  调皮: '😜',
  呲牙: '😁',
  惊讶: '😲',
  难过: '🙁',
  酷: '🆒',
  冷汗: '😓',
  抓狂: '😫',
  吐: '🤮',
  偷笑: '😏',
  愉快: '😊',
  白眼: '🙄',
  傲慢: '😤',
  困: '😪',
  惊恐: '😱',
  流汗: '😓',
  憨笑: '😄',
  悠闲: '😌',
  奋斗: '💪',
  咒骂: '🤬',
  疑问: '❓',
  嘘: '🤫',
  晕: '😵',
  衰: '😔',
  骷髅: '💀',
  敲打: '🔨',
  擦汗: '😅',
  抠鼻: '🤥',
  坏笑: '😏',
  左哼哼: '😤',
  右哼哼: '😤',
  哈欠: '🥱',
  鄙视: '😒',
  委屈: '🥺',
  快哭了: '😢',
  阴险: '😏',
  亲亲: '😘',
  飞吻: '😘',
  可怜: '🥺',
  发抖: '🥶',
  转圈: '🔄',
  跳跳: '🕺',
  嘿哈: '😄',
  捂脸: '🤦',
  奸笑: '😏',
  机智: '🤓',
  皱眉: '😟',
  耶: '✌️',
  吃瓜: '🍉',
  加油加油: '💪',
  汗: '😓',
  天啊: '😱',
  社会社会: '😎',
  旺柴: '🐶',
  好的: '👌',
  哇: '😮',
  打脸: '🤕',
  破涕为笑: '🥲',
  苦涩: '😖',
  裂开: '🤯',

  // --- 物品 / 自然 ---
  咖啡: '☕',
  啤酒: '🍺',
  蛋糕: '🎂',
  爱心: '❤️',
  心碎: '💔',
  太阳: '☀️',
  月亮: '🌙',
  玫瑰: '🌹',
  凋谢: '🥀',
  西瓜: '🍉',
  饭: '🍚',
  猪头: '🐷',
  礼物: '🎁',
  红包: '🧧',
  钱: '💰',
  灯泡: '💡',
  篮球: '🏀',
  乒乓: '🏓',
  足球: '⚽',
  麦克风: '🎤',
  音乐: '🎵',
  药: '💊',
  菜刀: '🔪',
  刀: '🔪',
  香蕉: '🍌',
  飞机: '✈️',
  汽车: '🚗',
  时钟: '🕐',
  房子: '🏠',
  便便: '💩',
  雨: '☔',
  多云: '⛅',
  雪人: '⛄',
  闪电: '⚡',
  炸弹: '💣',
  烟花: '🎆',
  鞭炮: '🧨',
  庆祝: '🎉',
  烛光: '🕯️',
}

/**
 * 后端 `_render_message_content` 生成的**结构占位**（非表情码），禁止替换。
 *
 * 与 `project/backend/app/ipad_sync.py::_render_message_content` 的返回值一一对应；
 * 后端新增占位形态时需同步补充，否则会被误当成表情码。
 */
export const STRUCTURAL_PLACEHOLDERS: ReadonlySet<string> = new Set<string>([
  '表情',
  '动画表情',
  '图片',
  '文件',
  '位置',
  '名片',
  '链接',
  '小程序',
  '视频号',
  '语音',
  '视频',
  '通话',
  '接龙',
  '红包消息',
  '系统消息',
  '撤回了一条消息',
])

/** 方括号 token 匹配：不跨行、不嵌套、长度上限 12（避免误吞长文本）。 */
const EMOJI_TOKEN_RE = /\[([^[\]\n]{1,12})\]/g

/**
 * 把文本中的微信表情码替换为 Unicode emoji。
 *
 * 规则：
 * - 命中 `STRUCTURAL_PLACEHOLDERS` 的 token 原样保留（后端结构占位）；
 * - 命中 `WECOM_EMOJI_MAP` 的 token 替换为对应 emoji；
 * - 其余未知 token 原样保留（不猜测、不丢字）。
 *
 * @param content 原始消息文本（可为空）
 * @returns 替换后的可读文本；入参为空时返回空串
 */
export function renderWecomContent(content: string): string {
  if (!content) return ''
  return content.replace(EMOJI_TOKEN_RE, (raw: string, name: string): string => {
    if (STRUCTURAL_PLACEHOLDERS.has(name)) return raw
    return WECOM_EMOJI_MAP[name] ?? raw
  })
}

/** `renderWecomContent` 的别名（后端注释以此名引用该渲染层）。 */
export const renderWecomEmoji = renderWecomContent

/** 表情结构占位的展示信息（图标 + 文案）。 */
export interface EmotionPlaceholder {
  /** 徽标图标（emoji 字符）。 */
  icon: string
  /** 徽标文案。 */
  label: string
}

/** 「孤立结构占位 → 徽标」映射：仅表情类占位需要降级成友好徽标。 */
const EMOTION_BADGES: Record<string, EmotionPlaceholder> = {
  '[表情]': { icon: '💬', label: '表情' },
  '[动画表情]': { icon: '🎭', label: '动画表情' },
}

/**
 * 判定消息文本是否为「孤立的表情结构占位」（协议未给图片 URL 的兜底文案）。
 *
 * 仅当整条内容就是 `[表情]` / `[动画表情]`（允许首尾空白）时命中；
 * 混在正文里的同名 token（极少见）不降级，避免吞掉上下文。
 *
 * @param content 消息文本
 * @returns 命中时返回徽标信息，否则返回 null
 */
export function emotionPlaceholder(content: string): EmotionPlaceholder | null {
  if (!content) return null
  return EMOTION_BADGES[content.trim()] ?? null
}

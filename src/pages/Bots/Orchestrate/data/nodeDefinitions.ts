import type { NodeSchema } from '../types/orchestrate';

/**
 * NODE_SCHEMAS — 节点参数协议（依据《Morphix 无代码编排手册 V2.0》）
 *
 * MVP 范围：13 个可配置节点 + 1 个占位节点（strongReminder）。
 * 每个节点：inputs（输入点：mode=connect仅连线 / input仅直接输入 / both两者皆可）
 *           outputs（输出点，只读）
 *           config（执行配置，可编辑字段）
 */
export const NODE_SCHEMAS: Record<string, NodeSchema> = {
  // ===== 获取内容类 =====
  globalVar: {
    inputs: [{ key: 'value', name: '输入值', varName: 'varValue', dataType: 'any', required: false, mode: 'both' }],
    outputs: [{ name: '全局变量值', varName: '{变量名}', dataType: 'any' }],
    config: [
      { key: 'varName', label: '变量名', fieldType: 'text', required: true, placeholder: '如 studentId（英文/驼峰）' },
      { key: 'dataType', label: '数据类型', fieldType: 'select', required: true, options: ['string', 'number', 'boolean', 'chatHistory', 'knowledgeRef', 'any', 'property'], default: 'string' },
      { key: 'inputMode', label: '输入方式', fieldType: 'select', required: true, options: ['连接传值', '直接输入', '连接或直接输入'], default: '连接或直接输入' },
    ],
  },
  userInput: {
    inputs: [],
    outputs: [
      { name: '消息原始内容', varName: 'userChatInput', dataType: 'any' },
      { name: 'AI识别内容', varName: 'AIAnalyzeChatInput', dataType: 'string' },
      { name: '消息类型', varName: 'msgType', dataType: 'string' },
    ],
    config: [
      { key: 'note', label: '说明', fieldType: 'note', required: false, placeholder: '流程起始节点：用户在企业微信发送消息后触发，无输入点' },
    ],
  },
  chatHistory: {
    inputs: [],
    outputs: [{ name: '对话记录', varName: 'chatHistory', dataType: 'chatHistory' }],
    config: [
      { key: 'count', label: '获取条数(N)', fieldType: 'number', required: true, default: 6, placeholder: '最近 N 条聊天记录（不含最新一条）' },
    ],
  },

  // ===== 输出类 =====
  msgOutput: {
    inputs: [{ key: 'message', name: '消息', varName: 'message', dataType: 'any', required: true, mode: 'both' }],
    outputs: [],
    config: [
      { key: 'splitMode', label: '消息分段方式', fieldType: 'select', required: true, options: ['不切分', '按换行符切分', '自定义切分字符'], default: '不切分' },
      { key: 'splitChar', label: '自定义切分字符', fieldType: 'text', required: false, placeholder: '分段输出时的分隔符（2~3秒间隔）' },
    ],
  },
  imageOutput: {
    inputs: [{ key: 'image', name: '图片', varName: 'image', dataType: 'any', required: true, mode: 'both' }],
    outputs: [],
    config: [
      { key: 'source', label: '图片来源', fieldType: 'select', required: true, options: ['素材库', '图片链接'], default: '素材库' },
      { key: 'url', label: '图片链接(URL)', fieldType: 'text', required: false, placeholder: '当来源为"图片链接"时填写' },
    ],
  },

  // ===== 工具类 =====
  setCustomerAttr: {
    inputs: [{ key: 'value', name: '属性值', varName: 'value', dataType: 'property', required: true, mode: 'both' }],
    outputs: [{ name: '属性值', varName: 'customerProp', dataType: 'property' }],
    config: [
      { key: 'attrName', label: '属性名', fieldType: 'text', required: true, placeholder: '客户属性变量名（跨轮持久）' },
    ],
  },

  // ===== 流程控制类 =====
  multiJudge: {
    inputs: [{ key: 'cond', name: '判断内容', varName: 'cond', dataType: 'any', required: true, mode: 'both' }],
    outputs: [{ name: '判断结果(True)', varName: 'result', dataType: 'boolean' }],
    config: [
      { key: 'mode', label: '判断模式', fieldType: 'select', required: true, options: ['文本匹配', '数值判断'], default: '文本匹配' },
      { key: 'matchText', label: '匹配内容', fieldType: 'text', required: false, placeholder: '文本匹配：支持模糊匹配（如 AAA）' },
      { key: 'op', label: '数值运算符', fieldType: 'select', required: false, options: ['==', '>', '<', '>=', '<=', '!='], default: '==' },
      { key: 'compareValue', label: '比较值', fieldType: 'number', required: false, placeholder: '数值判断时的比较值' },
    ],
  },
  timeControl: {
    inputs: [{ key: 'trigger', name: '触发', varName: 'trigger', dataType: 'any', required: false, mode: 'connect' }],
    outputs: [{ name: '完成(True)', varName: 'done', dataType: 'boolean' }],
    config: [
      { key: 'seconds', label: '延迟时间(秒)', fieldType: 'number', required: true, default: 5, placeholder: '等待指定秒数后继续往下运行' },
    ],
  },

  // ===== 逻辑处理类 =====
  regexExtract: {
    inputs: [{ key: 'content', name: '输入内容', varName: 'content', dataType: 'any', required: true, mode: 'both' }],
    outputs: [
      { name: '提取内容', varName: 'extract', dataType: 'any' },
      { name: '字段提取缺失(True)', varName: 'missing', dataType: 'boolean' },
    ],
    config: [
      { key: 'rules', label: '正则规则', fieldType: 'textarea', required: true, placeholder: '每行一条：变量名=正则表达式，如 name=(\\w+)' },
      { key: 'note', label: '说明', fieldType: 'note', required: false, placeholder: '支持多个正则同时提取；提取的变量供后续节点使用' },
    ],
  },
  jsonExtract: {
    inputs: [{ key: 'content', name: '输入内容', varName: 'content', dataType: 'any', required: true, mode: 'both' }],
    outputs: [
      { name: '字段值', varName: 'fieldValue', dataType: 'any' },
      { name: '字段提取缺失(True)', varName: 'missing', dataType: 'boolean' },
    ],
    config: [
      { key: 'keys', label: '提取字段(Key)', fieldType: 'textarea', required: true, placeholder: '每行一个 key；输入须为合法 JSON 字符串' },
    ],
  },
  aiChat: {
    inputs: [
      { key: 'question', name: '用户问题', varName: 'userChatInput', dataType: 'any', required: true, mode: 'both' },
      { key: 'history', name: '聊天记录', varName: 'chatHistory', dataType: 'chatHistory', required: false, mode: 'both' },
      { key: 'knowledge', name: '知识库引用', varName: 'knowledges', dataType: 'knowledgeRef', required: false, mode: 'both' },
    ],
    outputs: [{ name: 'AI回复内容', varName: 'aiReply', dataType: 'any' }],
    config: [
      { key: 'model', label: '大模型', fieldType: 'select', required: true, options: ['DeepSeek', 'GPT-4', 'Claude', '通义千问', '文心一言', '本地模型'], default: 'DeepSeek' },
      { key: 'prompt', label: '提示词', fieldType: 'textarea', required: true, placeholder: '用 {userChatInput} {chatHistory} {knowledges} 引用输入点变量' },
    ],
  },
  kbSearch: {
    inputs: [{ key: 'query', name: '用户问题', varName: 'query', dataType: 'any', required: true, mode: 'both' }],
    outputs: [{ name: '搜索结果', varName: 'knowledges', dataType: 'knowledgeRef' }],
    config: [
      { key: 'kb', label: '知识库', fieldType: 'text', required: true, placeholder: '选择/填写知识库（可多个）' },
      { key: 'searchMode', label: '搜索模式', fieldType: 'select', required: true, options: ['语义搜索', '混合搜索', '全文搜索'], default: '混合搜索' },
      { key: 'topK', label: '返回数量', fieldType: 'number', required: false, default: 5, placeholder: '返回知识条数' },
    ],
  },

  // ===== 复合类 =====
  agentEmbed: {
    inputs: [{ key: 'question', name: '用户问题', varName: 'userChatInput', dataType: 'any', required: true, mode: 'both' }],
    outputs: [{ name: 'AI回复内容', varName: 'aiReply', dataType: 'any' }],
    config: [
      { key: 'bot', label: '选择机器人', fieldType: 'text', required: true, placeholder: '需已发布的机器人' },
    ],
  },
  strongReminder: {
    inputs: [{ key: 'trigger', name: '触发内容', varName: 'trigger', dataType: 'any', required: false, mode: 'both' }],
    outputs: [{ name: '结果', varName: 'result', dataType: 'any' }],
    config: [
      { key: 'way', label: '提醒方式', fieldType: 'select', required: true, options: ['企微消息', '短信', '电话'], default: '企微消息' },
      { key: 'content', label: '提醒内容', fieldType: 'textarea', required: true, placeholder: '强提醒内容' },
    ],
  },

  // ===== 输出类（P1 补充） =====
  fileOutput: {
    inputs: [{ key: 'file', name: '文件', varName: 'file', dataType: 'any', required: true, mode: 'both' }],
    outputs: [],
    config: [
      { key: 'fileName', label: '文件名', fieldType: 'text', required: false, placeholder: '输出文件名（可选）' },
    ],
  },
  videoOutput: {
    inputs: [{ key: 'video', name: '视频', varName: 'video', dataType: 'any', required: true, mode: 'both' }],
    outputs: [],
    config: [
      { key: 'source', label: '视频来源', fieldType: 'select', required: true, options: ['素材库', '视频链接'], default: '素材库' },
      { key: 'url', label: '视频链接(URL)', fieldType: 'text', required: false, placeholder: '当来源为"视频链接"时填写' },
    ],
  },
  voiceOutput: {
    inputs: [{ key: 'audio', name: '音频', varName: 'audio', dataType: 'any', required: true, mode: 'both' }],
    outputs: [],
    config: [
      { key: 'source', label: '音频来源', fieldType: 'select', required: true, options: ['素材库', '音频链接'], default: '素材库' },
      { key: 'url', label: '音频链接(URL)', fieldType: 'text', required: false, placeholder: '当来源为"音频链接"时填写' },
    ],
  },
  linkCardOutput: {
    inputs: [{ key: 'content', name: '输入内容', varName: 'content', dataType: 'string', required: false, mode: 'both' }],
    outputs: [],
    config: [
      { key: 'cover', label: '封面图URL', fieldType: 'text', required: false, placeholder: '链接卡片封面图片地址' },
      { key: 'title', label: '标题', fieldType: 'text', required: true, placeholder: '链接卡片标题' },
      { key: 'desc', label: '描述', fieldType: 'textarea', required: false, placeholder: '链接卡片描述文字' },
      { key: 'url', label: '链接URL', fieldType: 'text', required: true, placeholder: '点击后跳转的链接地址' },
    ],
  },
  markdownOutput: {
    inputs: [{ key: 'content', name: '输入内容', varName: 'content', dataType: 'string', required: true, mode: 'both' }],
    outputs: [],
    config: [
      { key: 'note', label: '说明', fieldType: 'note', required: false, placeholder: '以 Markdown 格式输出消息，支持标题、列表、代码块、表格等格式' },
    ],
  },
  emailOutput: {
    inputs: [{ key: 'content', name: '输入内容', varName: 'content', dataType: 'string', required: true, mode: 'both' }],
    outputs: [],
    config: [
      { key: 'to', label: '收件人', fieldType: 'text', required: true, placeholder: '收件人邮箱地址' },
      { key: 'subject', label: '邮件主题', fieldType: 'text', required: true, placeholder: '邮件主题' },
    ],
  },
  miniAppOutput: {
    inputs: [{ key: 'content', name: '输入内容', varName: 'content', dataType: 'string', required: false, mode: 'both' }],
    outputs: [],
    config: [
      { key: 'appId', label: '小程序AppID', fieldType: 'text', required: true, placeholder: '小程序 AppID' },
      { key: 'path', label: '页面路径', fieldType: 'text', required: false, placeholder: '小程序页面路径（如 pages/index/index）' },
      { key: 'title', label: '卡片标题', fieldType: 'text', required: true, placeholder: '小程序卡片标题' },
    ],
  },

  // ===== 复合类：子流程调用（预置子流程模板） =====

  /** 子流程调用节点（用户自定义） */
  subflowCall: {
    inputs: [
      // 动态生成，模板为空数组；实际端口根据子流程 interface.inputs 在渲染时注入
    ],
    outputs: [
      // 动态生成，模板为空数组；实际端口根据子流程 interface.outputs 在渲染时注入
    ],
    config: [
      { key: 'note', label: '说明', fieldType: 'note', required: false,
        placeholder: '子流程调用节点。端口由子流程定义动态生成。点击下方按钮查看内部结构。' },
    ],
  },

  // ──── 预置子流程模板 ────

  replyCountControl: {
    inputs: [{ key: 'trigger', name: '触发', varName: 'trigger', dataType: 'any', required: false, mode: 'connect' }],
    outputs: [{ name: '是否超限(True)', varName: 'over', dataType: 'boolean' }],
    config: [
      { key: 'window', label: '时间窗口(分钟)', fieldType: 'number', required: true, default: 5 },
      { key: 'max', label: '最大回复次数', fieldType: 'number', required: true, default: 3 },
    ],
  },
  multimodalReplace: {
    inputs: [{ key: 'content', name: '多模态内容', varName: 'content', dataType: 'any', required: true, mode: 'both' }],
    outputs: [{ name: '替换后文本', varName: 'replaced', dataType: 'string' }],
    config: [
      { key: 'tpl', label: '替换模板', fieldType: 'textarea', required: true, placeholder: '用 {text} 引用输入内容' },
    ],
  },
  termSearchFlow: {
    inputs: [{ key: 'query', name: '用户问题', varName: 'query', dataType: 'any', required: true, mode: 'both' }],
    outputs: [{ name: '检索结果', varName: 'knowledges', dataType: 'knowledgeRef' }],
    config: [
      { key: 'kb', label: '知识库', fieldType: 'text', required: true },
      { key: 'tokenizer', label: '分词方式', fieldType: 'select', required: true, options: ['循环分词条', '单条'], default: '循环分词条' },
    ],
  },
  lineBreakAnswer: {
    inputs: [{ key: 'content', name: '内容', varName: 'content', dataType: 'any', required: true, mode: 'both' }],
    outputs: [{ name: '处理后文本', varName: 'out', dataType: 'string' }],
    config: [
      { key: 'sep', label: '分隔方式', fieldType: 'select', required: true, options: ['空行分隔', '换行分隔'], default: '空行分隔' },
    ],
  },
  clearContext: {
    inputs: [],
    outputs: [{ name: '完成', varName: 'done', dataType: 'boolean' }],
    config: [
      { key: 'note', label: '说明', fieldType: 'note', required: false, placeholder: '清空当前聊天上下文' },
    ],
  },
  vipTone: {
    inputs: [{ key: 'content', name: '内容', varName: 'content', dataType: 'any', required: true, mode: 'both' }],
    outputs: [{ name: '调整后文本', varName: 'out', dataType: 'string' }],
    config: [
      { key: 'tone', label: '语气风格', fieldType: 'select', required: true, options: ['尊贵', '热情', '专业', '亲切'], default: '尊贵' },
    ],
  },
  interruptBefore: {
    inputs: [{ key: 'trigger', name: '触发', varName: 'trigger', dataType: 'any', required: false, mode: 'connect' }],
    outputs: [{ name: '放行(True)', varName: 'pass', dataType: 'boolean' }],
    config: [
      { key: 'wait', label: '等待秒数', fieldType: 'number', required: true, default: 170, placeholder: '开头介入判断，默认等待 170 秒' },
    ],
  },
  multimodalInputAdjust: {
    inputs: [{ key: 'content', name: '多模态内容', varName: 'content', dataType: 'any', required: true, mode: 'both' }],
    outputs: [{ name: '调整后文本', varName: 'out', dataType: 'string' }],
    config: [
      { key: 'strategy', label: '调整策略', fieldType: 'select', required: true, options: ['识别结果替换', '原文保留', '摘要'], default: '识别结果替换' },
    ],
  },
  interruptAfter: {
    inputs: [{ key: 'trigger', name: '触发', varName: 'trigger', dataType: 'any', required: false, mode: 'connect' }],
    outputs: [{ name: '放行(True)', varName: 'pass', dataType: 'boolean' }],
    config: [
      { key: 'wait', label: '等待秒数', fieldType: 'number', required: true, default: 170 },
    ],
  },
  policySearch: {
    inputs: [{ key: 'query', name: '用户问题', varName: 'query', dataType: 'any', required: true, mode: 'both' }],
    outputs: [{ name: '检索结果', varName: 'knowledges', dataType: 'knowledgeRef' }],
    config: [
      { key: 'kb', label: '保单知识库', fieldType: 'text', required: true, placeholder: '仅限蜗牛客户' },
    ],
  },
  wordSplitNoKB: {
    inputs: [{ key: 'query', name: '用户问题', varName: 'query', dataType: 'any', required: true, mode: 'both' }],
    outputs: [{ name: '分词结果', varName: 'terms', dataType: 'property' }],
    config: [
      { key: 'tokenizer', label: '分词方式', fieldType: 'select', required: true, options: ['循环分词', '单条'], default: '循环分词' },
    ],
  },

  // ===== 特殊渠道：企业微信 =====

  getWeComTag: {
    inputs: [],
    outputs: [{ name: '企业微信标签', varName: 'wecomTags', dataType: 'property' }],
    config: [
      { key: 'note', label: '说明', fieldType: 'note', required: false, placeholder: '返回当前用户的企业微信标签列表（需代开发授权）' },
    ],
  },
  setWeComTag: {
    inputs: [{ key: 'tags', name: '标签', varName: 'wecomTags', dataType: 'property', required: true, mode: 'both' }],
    outputs: [{ name: '完成', varName: 'done', dataType: 'boolean' }],
    config: [
      { key: 'tagNames', label: '标签名', fieldType: 'text', required: true, placeholder: '可设置多个，逗号分隔（需提前在企业配置）' },
    ],
  },
  weComCreateGroup: {
    inputs: [{ key: 'customer', name: '客户', varName: 'customer', dataType: 'any', required: false, mode: 'connect' }],
    outputs: [{ name: '群', varName: 'group', dataType: 'any' }],
    config: [
      { key: 'mode', label: '拉群方式', fieldType: 'select', required: true, options: ['新建群', '拉入已有群'], default: '新建群' },
      { key: 'groupName', label: '群名', fieldType: 'text', required: false, placeholder: '新建群时必填' },
      { key: 'members', label: '其他成员', fieldType: 'text', required: false, placeholder: '除当前客户外需拉入的成员' },
      { key: 'targetGroup', label: '目标群名', fieldType: 'text', required: false, placeholder: '拉入已有群时填写' },
    ],
  },
  weComRenameGroup: {
    inputs: [{ key: 'group', name: '群', varName: 'group', dataType: 'any', required: false, mode: 'connect' }],
    outputs: [{ name: '完成', varName: 'done', dataType: 'boolean' }],
    config: [
      { key: 'newName', label: '新群名', fieldType: 'text', required: true, placeholder: '修改企业微信群名称' },
    ],
  },
  weComGroupNotice: {
    inputs: [{ key: 'group', name: '群', varName: 'group', dataType: 'any', required: false, mode: 'connect' }],
    outputs: [{ name: '完成', varName: 'done', dataType: 'boolean' }],
    config: [
      { key: 'notice', label: '群公告', fieldType: 'textarea', required: true, placeholder: '修改企业微信群公告内容' },
    ],
  },

  // ===== 特殊渠道：Morphix =====

  getMorphixTag: {
    inputs: [],
    outputs: [{ name: 'Morphix标签', varName: 'morphixTags', dataType: 'property' }],
    config: [
      { key: 'note', label: '说明', fieldType: 'note', required: false, placeholder: '返回用户在 Morphix 上的标签列表（仅托管时可用）' },
    ],
  },
  setMorphixTag: {
    inputs: [{ key: 'tags', name: '标签', varName: 'morphixTags', dataType: 'property', required: true, mode: 'both' }],
    outputs: [{ name: '完成', varName: 'done', dataType: 'boolean' }],
    config: [
      { key: 'tagNames', label: '标签名', fieldType: 'text', required: true, placeholder: '需标签组中已存在' },
    ],
  },
  deleteMorphixTag: {
    inputs: [],
    outputs: [{ name: '完成', varName: 'done', dataType: 'boolean' }],
    config: [
      { key: 'tagNames', label: '标签名', fieldType: 'text', required: true, placeholder: '要删除的 Morphix 标签' },
    ],
  },
  getMorphixGroupTag: {
    inputs: [],
    outputs: [{ name: 'Morphix群标签', varName: 'morphixGroupTags', dataType: 'property' }],
    config: [
      { key: 'note', label: '说明', fieldType: 'note', required: false, placeholder: '返回 Morphix 上该群的标签列表' },
    ],
  },
  setMorphixGroupTag: {
    inputs: [{ key: 'tags', name: '群标签', varName: 'morphixGroupTags', dataType: 'property', required: true, mode: 'both' }],
    outputs: [{ name: '完成', varName: 'done', dataType: 'boolean' }],
    config: [
      { key: 'tagNames', label: '群标签名', fieldType: 'text', required: true, placeholder: '需标签组中已存在' },
    ],
  },
  deleteMorphixGroupTag: {
    inputs: [],
    outputs: [{ name: '完成', varName: 'done', dataType: 'boolean' }],
    config: [
      { key: 'tagNames', label: '群标签名', fieldType: 'text', required: true, placeholder: '要删除的 Morphix 群标签' },
    ],
  },
};

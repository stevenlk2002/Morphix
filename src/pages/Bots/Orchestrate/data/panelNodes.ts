import type { PanelTabs } from '../types/orchestrate';

/**
 * ORCHESTRATE_NODES — 面板节点 3 Tab 分类（MVP 范围）。
 *
 * 节点与原型 ORCHESTRATE_NODES 保持一致的分类和元数据。
 * MVP 之外的特殊渠道节点暂不展示。
 * 复合 Tab "子流程调用" 分类为动态注入预留（运行时从 localStorage 读取已保存子流程）。
 */
export const ORCHESTRATE_NODES: PanelTabs = {
  basic: [
    {
      category: '获取内容',
      nodes: [
        { id: 'userInput', title: '用户输入', desc: '当用户发送一个内容后，流程将会从这个模块开始', color: '#c9a87c', icon: 'text' },
        { id: 'globalVar', title: '全局变量', desc: '设置一个在全流程中保持一致的全局变量', color: '#c9a87c', icon: 'variable' },
        { id: 'chatHistory', title: '对话记录获取', desc: '获取用户最新一条输入内容前数条的对话内容', color: '#c9a87c', icon: 'message-circle' },
      ],
    },
    {
      category: '输出',
      nodes: [
        { id: 'msgOutput', title: '消息输出', desc: '输出消息到对应的位置，可向用户输出消息', color: '#5fb5a6', icon: 'send' },
        { id: 'imageOutput', title: '图片输出', desc: '输出图片消息，可向用户发送图片', color: '#5fb5a6', icon: 'image' },
        { id: 'fileOutput', title: '文件输出', desc: '输出文件，可向用户发送文件', color: '#5fb5a6', icon: 'file' },
        { id: 'videoOutput', title: '视频输出', desc: '输出视频消息，可向用户发送视频', color: '#5fb5a6', icon: 'video' },
        { id: 'voiceOutput', title: '语音输出', desc: '输出语音消息，可向用户发送语音', color: '#5fb5a6', icon: 'mic' },
        { id: 'linkCardOutput', title: '链接卡片输出', desc: '输出链接卡片，可向用户发送图文链接', color: '#5fb5a6', icon: 'link' },
        { id: 'markdownOutput', title: 'Markdown输出', desc: '以 Markdown 格式输出消息，支持标题、列表、代码块等', color: '#5fb5a6', icon: 'file-text' },
        { id: 'emailOutput', title: '邮件输出', desc: '发送邮件到指定收件人', color: '#5fb5a6', icon: 'mail' },
        { id: 'miniAppOutput', title: '小程序输出', desc: '输出小程序卡片，引导用户打开小程序', color: '#5fb5a6', icon: 'smartphone' },
      ],
    },
    {
      category: '工具',
      nodes: [
        { id: 'setCustomerAttr', title: '设置客户属性', desc: '设置该聊天客户的某个属性', color: '#6a9bcc', icon: 'user' },
      ],
    },
    {
      category: '流程控制',
      nodes: [
        { id: 'multiJudge', title: '多重判断器', desc: '根据传入的内容进行判断条件匹配，当内容满足条件时执行对应分支', color: '#a88bd8', icon: 'git-branch' },
        { id: 'timeControl', title: '时间控制', desc: '在指定时间后，开始执行后续流程', color: '#a88bd8', icon: 'clock' },
      ],
    },
    {
      category: '逻辑处理',
      nodes: [
        { id: 'aiChat', title: 'AI对话', desc: '通过AI对输入的内容进行回复', color: '#e49a6d', icon: 'bot' },
        { id: 'kbSearch', title: '知识库搜索', desc: '根据输入内容，从知识库中搜索相关知识', color: '#e49a6d', icon: 'database' },
        { id: 'regexExtract', title: '正则提取', desc: '通过正则表达式从输入的文本中提取内容', color: '#e49a6d', icon: 'regex' },
        { id: 'jsonExtract', title: 'JSON提取', desc: '从输入的json文本中提取字段的值', color: '#e49a6d', icon: 'braces' },
      ],
    },
  ],
  composite: [
    {
      category: 'AI机器人嵌入',
      nodes: [
        { id: 'agentEmbed', title: '智能体嵌入', desc: '嵌入一个现有的智能体', color: '#a88bd8', icon: 'bot' },
      ],
    },
    {
      category: '子流程调用',
      nodes: [
        { id: 'strongReminder', title: '强提醒子流程', desc: '通过企微消息/短信/电话进行强提醒通知', color: '#5fb5a6', icon: 'subflow' },
        { id: 'replyCountControl', title: 'N分钟内AI回复次数控制', desc: '限制AI在指定时间内最大回复次数', color: '#5fb5a6', icon: 'subflow' },
        { id: 'multimodalReplace', title: '当前对话多模态文本替换', desc: '把多模态识别结果替换为自定义模板文本', color: '#5fb5a6', icon: 'subflow' },
        { id: 'termSearchFlow', title: '循环分词条检索知识流程', desc: '分词后逐个从知识库搜索', color: '#5fb5a6', icon: 'subflow' },
        { id: 'lineBreakAnswer', title: '空行分隔回答', desc: '将输入按空行或换行分隔为多条回答', color: '#5fb5a6', icon: 'subflow' },
        { id: 'clearContext', title: '清空聊天上下文', desc: '清空当前聊天上下文记忆', color: '#5fb5a6', icon: 'subflow' },
        { id: 'vipTone', title: 'VIP语气调整', desc: '将机器人回复调整为VIP专属语气', color: '#5fb5a6', icon: 'subflow' },
        { id: 'interruptBefore', title: '打断控制-前控制', desc: '流程开头的介入判断，等待指定秒数', color: '#5fb5a6', icon: 'subflow' },
        { id: 'multimodalInputAdjust', title: '多模态用户输入调整', desc: '对用户发送多模态内容识别结果做调整', color: '#5fb5a6', icon: 'subflow' },
        { id: 'interruptAfter', title: '打断控制-后控制', desc: '流程末尾的打断控制判断', color: '#5fb5a6', icon: 'subflow' },
        { id: 'policySearch', title: '保单检索子流程', desc: '在保单知识库中检索', color: '#5fb5a6', icon: 'subflow' },
        { id: 'wordSplitNoKB', title: '循环分词-不含知识库', desc: '分词处理，不依赖知识库', color: '#5fb5a6', icon: 'subflow' },
      ],
    },
  ],
  special: [
    {
      category: '企业微信',
      nodes: [
        { id: 'getWeComTag', title: '获取企业微信标签', desc: '获取该用户的企微标签列表', color: '#6a9bcc', icon: 'tag' },
        { id: 'setWeComTag', title: '设置企业微信标签', desc: '给该用户设置企微标签', color: '#6a9bcc', icon: 'tag' },
        { id: 'weComCreateGroup', title: '企微拉群', desc: '新建群或拉成员进入已有群', color: '#6a9bcc', icon: 'group' },
        { id: 'weComRenameGroup', title: '修改企微群名', desc: '修改当前群的名称', color: '#6a9bcc', icon: 'edit' },
        { id: 'weComGroupNotice', title: '修改企微群公告', desc: '修改当前群的公告内容', color: '#6a9bcc', icon: 'notice' },
      ],
    },
    {
      category: 'Morphix',
      nodes: [
        { id: 'getMorphixTag', title: '获取Morphix标签', desc: '获取Morphix上该用户的标签', color: '#c9a87c', icon: 'tag' },
        { id: 'setMorphixTag', title: '设置Morphix标签', desc: '设置Morphix上该用户的标签', color: '#c9a87c', icon: 'tag' },
        { id: 'deleteMorphixTag', title: '删除Morphix标签', desc: '删除Morphix上该用户的标签', color: '#c9a87c', icon: 'tag' },
        { id: 'getMorphixGroupTag', title: '获取Morphix群标签', desc: '获取Morphix上该群的标签', color: '#c9a87c', icon: 'tag' },
        { id: 'setMorphixGroupTag', title: '设置Morphix群标签', desc: '设置Morphix上该群的标签', color: '#c9a87c', icon: 'tag' },
        { id: 'deleteMorphixGroupTag', title: '删除Morphix群标签', desc: '删除Morphix上该群的标签', color: '#c9a87c', icon: 'tag' },
      ],
    },
  ],
};

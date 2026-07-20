import type { SubflowPersisted } from '../types/orchestrate';

/** Mock 执行上下文（在执行过程中累积） */
export interface ExecutionContext {
  userChatInput: string;
  [nodeIdOrVar: string]: unknown;
}

/** Mock 函数签名 */
export type MockFunction = (
  context: ExecutionContext,
  config: Record<string, unknown>,
  inputs: Record<string, unknown>,
) => Record<string, unknown>;

/** 递归执行子流程的函数类型（由 useMockExecution 注入） */
export type SubflowExecutor = (
  subflow: SubflowPersisted,
  externalInputs: Record<string, unknown>,
) => Record<string, unknown>;

// ══════════════ Mock 策略实现 ══════════════

/** 用户输入节点 */
function mockUserInput(
  context: ExecutionContext,
  _config: Record<string, unknown>,
  _inputs: Record<string, unknown>,
): Record<string, unknown> {
  return {
    userChatInput: context.userChatInput,
    AIAnalyzeChatInput: `[Mock] ${context.userChatInput}`,
    msgType: 'text',
  };
}

/** AI 对话节点 */
function mockAiChat(
  _context: ExecutionContext,
  _config: Record<string, unknown>,
  inputs: Record<string, unknown>,
): Record<string, unknown> {
  const userInput = inputs.userChatInput ?? inputs.question ?? '';
  return {
    aiReply: `[Mock] 这是 AI 对话节点的模拟回复。输入: ${JSON.stringify(userInput)}`,
  };
}

/** 知识库搜索节点 */
function mockKbSearch(
  _context: ExecutionContext,
  _config: Record<string, unknown>,
  _inputs: Record<string, unknown>,
): Record<string, unknown> {
  return {
    knowledges: [
      { content: '[Mock] 知识库搜索结果', score: 0.95, kbId: 'mock-kb-1' },
    ],
  };
}

/** 多重判断器节点 — 真实执行文本/数值匹配 */
function mockMultiJudge(
  _context: ExecutionContext,
  config: Record<string, unknown>,
  inputs: Record<string, unknown>,
): Record<string, unknown> {
  const mode = (config.mode as string) ?? '文本匹配';
  const condValue = String(inputs.cond ?? '');

  if (mode === '文本匹配') {
    const matchText = (config.matchText as string) ?? '';
    const result = condValue.includes(matchText);
    return { result };
  }

  if (mode === '数值判断') {
    const op = (config.op as string) ?? '==';
    const compareValue = Number(config.compareValue ?? 0);
    const numValue = Number(condValue);

    if (isNaN(numValue)) return { result: false };

    let result = false;
    switch (op) {
      case '==': result = numValue === compareValue; break;
      case '>': result = numValue > compareValue; break;
      case '<': result = numValue < compareValue; break;
      case '>=': result = numValue >= compareValue; break;
      case '<=': result = numValue <= compareValue; break;
      case '!=': result = numValue !== compareValue; break;
      default: result = false;
    }
    return { result };
  }

  return { result: false };
}

/** 正则提取节点 — 对上游值真实执行正则 */
function mockRegexExtract(
  _context: ExecutionContext,
  config: Record<string, unknown>,
  inputs: Record<string, unknown>,
): Record<string, unknown> {
  const content = String(inputs.content ?? '');
  const rulesStr = (config.rules as string) ?? '';
  const rules = rulesStr
    .split('\n')
    .map((line) => line.trim())
    .filter((line) => line.includes('='));

  for (const rule of rules) {
    const eqIdx = rule.indexOf('=');
    const varName = rule.substring(0, eqIdx).trim();
    const regexStr = rule.substring(eqIdx + 1).trim();
    try {
      const regex = new RegExp(regexStr);
      const match = content.match(regex);
      if (match && match[1] !== undefined) {
        return { extract: match[1], missing: false, [varName]: match[1] };
      }
    } catch {
      // 正则无效，跳过
    }
  }

  return { extract: 'mock_extracted', missing: false };
}

/** JSON 提取节点 — 对上游值真实执行 JSON.parse */
function mockJsonExtract(
  _context: ExecutionContext,
  config: Record<string, unknown>,
  inputs: Record<string, unknown>,
): Record<string, unknown> {
  const content = String(inputs.content ?? '');
  const keysStr = (config.keys as string) ?? '';
  const keys = keysStr
    .split('\n')
    .map((k) => k.trim())
    .filter(Boolean);

  try {
    const parsed: Record<string, unknown> = JSON.parse(content);
    const result: Record<string, unknown> = { missing: false };

    for (const key of keys) {
      if (key in parsed) {
        result[key] = parsed[key];
      }
    }
    result.fieldValue = result[keys[0]] ?? 'mock_value';
    return result;
  } catch {
    return { fieldValue: 'mock_value', missing: false };
  }
}

/** 消息输出节点 — 空输出，标记 sent */
function mockMsgOutput(
  _context: ExecutionContext,
  _config: Record<string, unknown>,
  _inputs: Record<string, unknown>,
): Record<string, unknown> {
  return {};
}

/** 全局变量节点 */
function mockGlobalVar(
  _context: ExecutionContext,
  config: Record<string, unknown>,
  inputs: Record<string, unknown>,
): Record<string, unknown> {
  const varName = (config.varName as string) ?? 'var';
  const value = inputs.value ?? config.default ?? '';
  return { [varName]: value };
}

/** 对话记录获取节点 */
function mockChatHistory(
  _context: ExecutionContext,
  _config: Record<string, unknown>,
  _inputs: Record<string, unknown>,
): Record<string, unknown> {
  return {
    chatHistory: [
      { role: 'user', content: 'mock history 1' },
      { role: 'assistant', content: 'mock reply 1' },
    ],
  };
}

/** 时间控制节点 — 跳过等待 */
function mockTimeControl(
  _context: ExecutionContext,
  _config: Record<string, unknown>,
  _inputs: Record<string, unknown>,
): Record<string, unknown> {
  return { done: true };
}

/** 设置客户属性节点 */
function mockSetCustomerAttr(
  _context: ExecutionContext,
  config: Record<string, unknown>,
  inputs: Record<string, unknown>,
): Record<string, unknown> {
  const value = inputs.value ?? config.default ?? '';
  return { customerProp: value };
}

/** 智能体嵌入节点 */
function mockAgentEmbed(
  _context: ExecutionContext,
  _config: Record<string, unknown>,
  _inputs: Record<string, unknown>,
): Record<string, unknown> {
  return { aiReply: '[Mock] 智能体嵌入节点模拟输出' };
}

/** 透传节点（其他输出类节点） */
function mockPassthrough(
  _context: ExecutionContext,
  _config: Record<string, unknown>,
  _inputs: Record<string, unknown>,
): Record<string, unknown> {
  return {};
}

/** 通用兜底 — 返回任意输入值作为输出（用于自定义/未知节点） */
function mockGenericFallback(
  _context: ExecutionContext,
  _config: Record<string, unknown>,
  inputs: Record<string, unknown>,
): Record<string, unknown> {
  // 透传所有输入值
  if (Object.keys(inputs).length > 0) return { ...inputs, _unimplemented: true };
  return { done: true, _unimplemented: true };
}

/** 子流程类节点 — 透传输入 */
function mockSubflowPass(
  _context: ExecutionContext,
  _config: Record<string, unknown>,
  inputs: Record<string, unknown>,
): Record<string, unknown> {
  if (Object.keys(inputs).length > 0) return { ...inputs };
  return { done: true };
}

/**
 * Mock 执行器注册表。
 * 所有节点类型的 mock 函数 + 兜底函数。
 */
export const mockExecutors: Record<string, MockFunction> = {
  userInput: mockUserInput,
  aiChat: mockAiChat,
  kbSearch: mockKbSearch,
  multiJudge: mockMultiJudge,
  regexExtract: mockRegexExtract,
  jsonExtract: mockJsonExtract,
  msgOutput: mockMsgOutput,
  globalVar: mockGlobalVar,
  chatHistory: mockChatHistory,
  timeControl: mockTimeControl,
  setCustomerAttr: mockSetCustomerAttr,
  agentEmbed: mockAgentEmbed,
  // 输出类节点 — 透传
  imageOutput: mockPassthrough,
  fileOutput: mockPassthrough,
  videoOutput: mockPassthrough,
  voiceOutput: mockPassthrough,
  linkCardOutput: mockPassthrough,
  markdownOutput: mockPassthrough,
  emailOutput: mockPassthrough,
  miniAppOutput: mockPassthrough,
  // 预置子流程节点
  strongReminder: mockSubflowPass,
  replyCountControl: mockGenericFallback,
  multimodalReplace: mockGenericFallback,
  termSearchFlow: mockGenericFallback,
  lineBreakAnswer: mockGenericFallback,
  clearContext: mockGenericFallback,
  vipTone: mockGenericFallback,
  interruptBefore: mockGenericFallback,
  multimodalInputAdjust: mockGenericFallback,
  interruptAfter: mockGenericFallback,
  policySearch: mockGenericFallback,
  wordSplitNoKB: mockGenericFallback,
  // 特殊渠道：企业微信
  getWeComTag: mockGenericFallback,
  setWeComTag: mockGenericFallback,
  weComCreateGroup: mockGenericFallback,
  weComRenameGroup: mockGenericFallback,
  weComGroupNotice: mockGenericFallback,
  // 特殊渠道：Morphix
  getMorphixTag: mockGenericFallback,
  setMorphixTag: mockGenericFallback,
  deleteMorphixTag: mockGenericFallback,
  getMorphixGroupTag: mockGenericFallback,
  setMorphixGroupTag: mockGenericFallback,
  deleteMorphixGroupTag: mockGenericFallback,
};

/**
 * 通用兜底 mock 函数：对于未知节点类型，返回任意输入值作为输出。
 * 也处理 custom: 前缀的自定义节点。
 */
export const defaultMockExecutor: MockFunction = mockGenericFallback;

/** 输出类节点列表（mock 执行后标记 mockNote） */
export const OUTPUT_NODE_TYPES = new Set([
  'msgOutput', 'imageOutput', 'fileOutput', 'videoOutput',
  'voiceOutput', 'linkCardOutput', 'markdownOutput',
  'emailOutput', 'miniAppOutput',
]);

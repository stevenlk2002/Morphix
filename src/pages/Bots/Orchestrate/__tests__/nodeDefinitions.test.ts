import { describe, it, expect } from 'vitest';
import { NODE_SCHEMAS } from '../data/nodeDefinitions';

describe('aiChat 节点使用配置中心模型引用', () => {
  it('aiChat.config 含 model_select 字段（引用 LLM 配置中心，不存 Key）', () => {
    const aiChat = NODE_SCHEMAS.aiChat;
    expect(aiChat).toBeDefined();

    const modelField = aiChat.config.find((f) => f.key === 'modelId');
    expect(modelField).toBeDefined();
    expect(modelField?.fieldType).toBe('model_select');
    expect(modelField?.required).toBe(true);

    // 旧的写死 select（DeepSeek/GPT-4…）应已移除
    const legacy = aiChat.config.find((f) => f.key === 'model');
    expect(legacy).toBeUndefined();

    // prompt 字段保留
    expect(aiChat.config.some((f) => f.key === 'prompt')).toBe(true);
  });
});

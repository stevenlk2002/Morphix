import { describe, it, expect } from 'vitest';
import { createDefaultWorkflow } from '../data/defaultWorkflow';

describe('createDefaultWorkflow', () => {
  const botId = 'test-bot-123';
  const workflow = createDefaultWorkflow(botId);

  it('botId 正确设置', () => {
    expect(workflow.botId).toBe(botId);
  });

  it('包含 2 个节点', () => {
    expect(workflow.nodes).toHaveLength(2);
  });

  it('包含 1 条边', () => {
    expect(workflow.edges).toHaveLength(1);
    expect(workflow.edges[0].source).toBe('node-1');
    expect(workflow.edges[0].target).toBe('node-2');
  });

  it('version 为 1', () => {
    expect(workflow.version).toBe(1);
  });

  it('包含 lastEdited 时间戳', () => {
    expect(workflow.lastEdited).toBeDefined();
    expect(typeof workflow.lastEdited).toBe('string');
    // 应为 ISO 8601 格式
    expect(() => new Date(workflow.lastEdited)).not.toThrow();
    expect(new Date(workflow.lastEdited).toISOString()).toBe(workflow.lastEdited);
  });

  describe('节点1 (node-1) — 用户输入', () => {
    it('id 为 node-1', () => {
      expect(workflow.nodes[0].id).toBe('node-1');
    });

    it('type 为 customNode', () => {
      expect(workflow.nodes[0].type).toBe('customNode');
    });

    it('nodeType 为 userInput（用户输入）', () => {
      expect(workflow.nodes[0].data.nodeType).toBe('userInput');
    });

    it('position 为 { x: 60, y: 80 }', () => {
      expect(workflow.nodes[0].position).toEqual({ x: 60, y: 80 });
    });

    it('inputs 为空对象', () => {
      expect(workflow.nodes[0].data.inputs).toEqual({});
    });
  });

  describe('节点2 (node-2) — 智能体嵌入', () => {
    it('id 为 node-2', () => {
      expect(workflow.nodes[1].id).toBe('node-2');
    });

    it('nodeType 为 agentEmbed', () => {
      expect(workflow.nodes[1].data.nodeType).toBe('agentEmbed');
    });

    it('position 为 { x: 320, y: 80 }', () => {
      expect(workflow.nodes[1].position).toEqual({ x: 320, y: 80 });
    });

    it('config 包含 bot 字段', () => {
      expect(workflow.nodes[1].data.config.bot).toBe('杨奇成健康机器人');
    });
  });


  it('不同 botId 产生不同的 WorkflowPersisted', () => {
    const wf1 = createDefaultWorkflow('bot-a');
    const wf2 = createDefaultWorkflow('bot-b');
    expect(wf1.botId).toBe('bot-a');
    expect(wf2.botId).toBe('bot-b');
  });

  it('每次调用返回独立对象（无引用共享）', () => {
    const wf1 = createDefaultWorkflow('bot-x');
    const wf2 = createDefaultWorkflow('bot-x');

    // 修改 wf1 不影响 wf2（bot 字段在 node-2 即 agentEmbed 节点上）
    wf1.nodes[1].data.config.bot = 'Modified';
    expect(wf2.nodes[1].data.config.bot).toBe('杨奇成健康机器人');
  });
});

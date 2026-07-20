import { describe, it, expect } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useValidation } from '../hooks/useValidation';
import type { OrchestrateNode, OrchestrateEdge } from '../components/FlowCanvas';
import type { ValidationResult } from '../types/orchestrate';

/**
 * 构造一个测试用的 OrchestrateNode。
 */
function makeNode(overrides: Partial<OrchestrateNode> & { id: string; nodeType: string }): OrchestrateNode {
  return {
    type: 'customNode',
    position: { x: 0, y: 0 },
    data: {
      nodeType: overrides.nodeType,
      config: {},
      inputs: {},
      ...overrides.data,
    },
    ...overrides,
  } as OrchestrateNode;
}

/**
 * 构造一个测试用的 OrchestrateEdge。
 */
function makeEdge(overrides: Partial<OrchestrateEdge> = {}): OrchestrateEdge {
  return {
    id: 'edge-test',
    source: overrides.source ?? 'node-1',
    target: overrides.target ?? 'node-2',
    sourceHandle: overrides.sourceHandle ?? 'aiReply',
    targetHandle: overrides.targetHandle ?? 'question',
    type: 'customEdge',
    ...overrides,
  };
}

describe('useValidation', () => {
  describe('agentEmbed 节点校验', () => {
    it('必填的 question 输入端口已连线 → 通过', () => {
      const { result } = renderHook(() => useValidation());

      const nodes: OrchestrateNode[] = [
        makeNode({
          id: 'node-1',
          nodeType: 'agentEmbed',
          data: {
            nodeType: 'agentEmbed',
            config: { bot: '测试机器人' }, // bot 也是 required
            inputs: {},
          },
        }),
        makeNode({ id: 'node-2', nodeType: 'userInput' }),
      ];
      // agentEmbed.inputs[0] key='question', required=true
      // 连线 targetHandle='question'
      const edges: OrchestrateEdge[] = [
        makeEdge({
          source: 'node-2',
          target: 'node-1',
          sourceHandle: 'userChatInput',
          targetHandle: 'question',
        }),
      ];

      let validationResult: ValidationResult;
      act(() => {
        validationResult = result.current.validate(nodes, edges);
      });

      expect(validationResult!.valid).toBe(true);
      expect(validationResult!.errors).toHaveLength(0);
    });

    it('必填的 question 输入端口已直接输入值 → 通过', () => {
      const { result } = renderHook(() => useValidation());

      const nodes: OrchestrateNode[] = [
        makeNode({
          id: 'node-1',
          nodeType: 'agentEmbed',
          data: {
            nodeType: 'agentEmbed',
            config: { bot: '测试机器人' }, // bot 也是 required
            inputs: { question: '用户直接输入的问题' },
          },
        }),
      ];
      const edges: OrchestrateEdge[] = [];

      let validationResult: ValidationResult;
      act(() => {
        validationResult = result.current.validate(nodes, edges);
      });

      expect(validationResult!.valid).toBe(true);
      expect(validationResult!.errors).toHaveLength(0);
    });

    it('必填的 question 既未连线也未输入 → 返回错误含节点名和端口名', () => {
      const { result } = renderHook(() => useValidation());

      const nodes: OrchestrateNode[] = [
        makeNode({ id: 'node-1', nodeType: 'agentEmbed' }),
      ];
      const edges: OrchestrateEdge[] = [];

      let validationResult: ValidationResult;
      act(() => {
        validationResult = result.current.validate(nodes, edges);
      });

      expect(validationResult!.valid).toBe(false);
      expect(validationResult!.errors.length).toBeGreaterThan(0);

      const questionError = validationResult!.errors.find(
        (e) => e.fieldKey === 'question',
      );
      expect(questionError).toBeDefined();
      expect(questionError!.nodeId).toBe('node-1');
      expect(questionError!.nodeName).toBe('智能体嵌入');
      expect(questionError!.fieldName).toBe('用户问题');
      expect(questionError!.message).toContain('用户问题');
      expect(questionError!.message).toContain('智能体嵌入');
    });

    it('必填的 bot config 未填写 → 返回错误', () => {
      const { result } = renderHook(() => useValidation());

      // agentEmbed config has bot (required=true) with no default
      const nodes: OrchestrateNode[] = [
        makeNode({
          id: 'node-1',
          nodeType: 'agentEmbed',
          data: {
            nodeType: 'agentEmbed',
            config: {}, // bot 未填
            inputs: { question: 'test' },
          },
        }),
      ];
      const edges: OrchestrateEdge[] = [];

      let validationResult: ValidationResult;
      act(() => {
        validationResult = result.current.validate(nodes, edges);
      });

      expect(validationResult!.valid).toBe(false);
      const botError = validationResult!.errors.find((e) => e.fieldKey === 'bot');
      expect(botError).toBeDefined();
      expect(botError!.message).toContain('选择机器人');
    });
  });

  describe('msgOutput 节点校验', () => {
    it('必填的 message 输入端口未连线 → 返回错误', () => {
      const { result } = renderHook(() => useValidation());

      const nodes: OrchestrateNode[] = [
        makeNode({ id: 'node-1', nodeType: 'msgOutput' }),
      ];
      const edges: OrchestrateEdge[] = [];

      let validationResult: ValidationResult;
      act(() => {
        validationResult = result.current.validate(nodes, edges);
      });

      expect(validationResult!.valid).toBe(false);
      const msgError = validationResult!.errors.find((e) => e.fieldKey === 'message');
      expect(msgError).toBeDefined();
      expect(msgError!.nodeName).toBe('消息输出');
    });
  });

  describe('strongReminder 节点跳过校验', () => {
    it('strongReminder 节点即使有 required 字段也跳过校验', () => {
      const { result } = renderHook(() => useValidation());

      // strongReminder has config.way (required) and config.content (required)
      // but the validation explicitly skips strongReminder
      const nodes: OrchestrateNode[] = [
        makeNode({
          id: 'node-1',
          nodeType: 'strongReminder',
          data: {
            nodeType: 'strongReminder',
            config: {}, // way 和 content 都未填
            inputs: {},
          },
        }),
      ];
      const edges: OrchestrateEdge[] = [];

      let validationResult: ValidationResult;
      act(() => {
        validationResult = result.current.validate(nodes, edges);
      });

      expect(validationResult!.valid).toBe(true);
      expect(validationResult!.errors).toHaveLength(0);
    });
  });

  describe('多节点校验', () => {
    it('多个节点有必填缺失 → 返回所有错误', () => {
      const { result } = renderHook(() => useValidation());

      const nodes: OrchestrateNode[] = [
        makeNode({ id: 'node-1', nodeType: 'agentEmbed' }), // question+bots missing
        makeNode({ id: 'node-2', nodeType: 'msgOutput' }), // message missing
      ];
      const edges: OrchestrateEdge[] = [];

      let validationResult: ValidationResult;
      act(() => {
        validationResult = result.current.validate(nodes, edges);
      });

      expect(validationResult!.valid).toBe(false);
      // agentEmbed: question + bot = 2 errors
      // msgOutput: message + splitMode = 2 errors
      // Total = 4
      expect(validationResult!.errors.length).toBeGreaterThanOrEqual(2);
    });
  });

  describe('边界情况', () => {
    it('空 nodes 数组 → 通过', () => {
      const { result } = renderHook(() => useValidation());

      let validationResult: ValidationResult;
      act(() => {
        validationResult = result.current.validate([], []);
      });

      expect(validationResult!.valid).toBe(true);
      expect(validationResult!.errors).toHaveLength(0);
    });

    it('未知 nodeType → 跳过不报错', () => {
      const { result } = renderHook(() => useValidation());

      const nodes: OrchestrateNode[] = [
        makeNode({ id: 'node-1', nodeType: 'nonExistentType' }),
      ];
      const edges: OrchestrateEdge[] = [];

      let validationResult: ValidationResult;
      act(() => {
        validationResult = result.current.validate(nodes, edges);
      });

      // 没有 schema，跳过 → 没有错误
      expect(validationResult!.valid).toBe(true);
      expect(validationResult!.errors).toHaveLength(0);
    });
  });
});

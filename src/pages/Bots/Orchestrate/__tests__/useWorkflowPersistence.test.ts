import { describe, it, expect, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useWorkflowPersistence } from '../hooks/useWorkflowPersistence';
import { useOrchestrateStore } from '../store/orchestrateStore';
import type { OrchestrateNode, OrchestrateEdge } from '../components/FlowCanvas';

/**
 * 构造测试用 OrchestrateNode。
 */
function makeNode(id: string, nodeType: string): OrchestrateNode {
  return {
    id,
    type: 'customNode',
    position: { x: 0, y: 0 },
    data: {
      nodeType,
      config: { bot: 'test-bot' },
      inputs: { question: 'hello' },
    },
  } as OrchestrateNode;
}

/**
 * 构造测试用 OrchestrateEdge。
 */
function makeEdge(id: string, source: string, target: string): OrchestrateEdge {
  return {
    id,
    source,
    target,
    sourceHandle: 'aiReply',
    targetHandle: 'question',
    type: 'customEdge',
  };
}

describe('useWorkflowPersistence', () => {
  beforeEach(() => {
    localStorage.clear();
    // 重置 zustand store 状态
    useOrchestrateStore.setState({
      botId: '',
      botName: '',
      lastEdited: '',
    });
  });

  describe('saveWorkflow → loadWorkflow 往返', () => {
    it('save 后 load 能完整恢复节点数据', async () => {
      const { result } = renderHook(() => useWorkflowPersistence());
      const botId = 'bot-save-load-1';

      const nodes: OrchestrateNode[] = [
        makeNode('node-1', 'agentEmbed'),
        makeNode('node-2', 'msgOutput'),
      ];
      const edges: OrchestrateEdge[] = [
        makeEdge('edge-1', 'node-1', 'node-2'),
      ];

      // Save
      let saved: boolean = false;
      await act(async () => {
        saved = await result.current.saveWorkflow(botId, nodes, edges);
      });
      expect(saved).toBe(true);

      // Load
      let loaded: Awaited<ReturnType<typeof result.current.loadWorkflow>> = null;
      await act(async () => {
        loaded = await result.current.loadWorkflow(botId);
      });

      expect(loaded).not.toBeNull();
      expect(loaded!.botId).toBe(botId);
      expect(loaded!.nodes).toHaveLength(2);
      expect(loaded!.edges).toHaveLength(1);
      expect(loaded!.nodes[0].data.nodeType).toBe('agentEmbed');
      expect(loaded!.nodes[0].data.config.bot).toBe('test-bot');
      expect(loaded!.nodes[0].data.inputs.question).toBe('hello');
      expect(loaded!.edges[0].source).toBe('node-1');
      expect(loaded!.edges[0].target).toBe('node-2');
    });

    it('save 后 load 能恢复 version 和 lastEdited', async () => {
      const { result } = renderHook(() => useWorkflowPersistence());
      const botId = 'bot-version-test';

      await act(async () => {
        await result.current.saveWorkflow(botId, [], []);
      });

      let loaded: Awaited<ReturnType<typeof result.current.loadWorkflow>> = null;
      await act(async () => {
        loaded = await result.current.loadWorkflow(botId);
      });

      expect(loaded!.version).toBe(1);
      expect(loaded!.lastEdited).toBeDefined();
      expect(typeof loaded!.lastEdited).toBe('string');
    });

    it('无保存数据时 load 返回 null', async () => {
      const { result } = renderHook(() => useWorkflowPersistence());

      let loaded: Awaited<ReturnType<typeof result.current.loadWorkflow>> = null;
      await act(async () => {
        loaded = await result.current.loadWorkflow('non-existent-bot');
      });

      expect(loaded).toBeNull();
    });
  });

  describe('storageKey 格式', () => {
    it('key 格式为 morphix_workflow_{botId}', async () => {
      const { result } = renderHook(() => useWorkflowPersistence());
      const botId = 'test-bot-key-format';

      await act(async () => {
        await result.current.saveWorkflow(botId, [], []);
      });

      // 验证 localStorage 中的 key 格式
      const expectedKey = `morphix_workflow_${botId}`;
      const raw = localStorage.getItem(expectedKey);
      expect(raw).not.toBeNull();

      const parsed = JSON.parse(raw!);
      expect(parsed.botId).toBe(botId);
    });

    it('不同 botId 使用不同的 localStorage key', async () => {
      const { result } = renderHook(() => useWorkflowPersistence());

      await act(async () => {
        await result.current.saveWorkflow('bot-a', [makeNode('n1', 'agentEmbed')], []);
      });
      await act(async () => {
        await result.current.saveWorkflow('bot-b', [makeNode('n1', 'msgOutput')], []);
      });

      const dataA = JSON.parse(localStorage.getItem('morphix_workflow_bot-a')!);
      const dataB = JSON.parse(localStorage.getItem('morphix_workflow_bot-b')!);

      expect(dataA.nodes[0].data.nodeType).toBe('agentEmbed');
      expect(dataB.nodes[0].data.nodeType).toBe('msgOutput');
    });
  });

  describe('getDefaultWorkflow', () => {
    it('返回包含正确 botId 的默认工作流', () => {
      const { result } = renderHook(() => useWorkflowPersistence());

      let defaultWf: ReturnType<typeof result.current.getDefaultWorkflow>;
      act(() => {
        defaultWf = result.current.getDefaultWorkflow('my-bot');
      });

      expect(defaultWf!.botId).toBe('my-bot');
      expect(defaultWf!.nodes).toHaveLength(2);
      expect(defaultWf!.edges).toHaveLength(1);
    });
  });

  describe('save 覆盖旧数据', () => {
    it('第二次 save 覆盖第一次的数据', async () => {
      const { result } = renderHook(() => useWorkflowPersistence());
      const botId = 'bot-overwrite';

      // 第一次保存
      await act(async () => {
        await result.current.saveWorkflow(botId, [makeNode('node-1', 'agentEmbed')], []);
      });

      // 第二次保存（覆盖）
      await act(async () => {
        await result.current.saveWorkflow(botId, [makeNode('node-1', 'msgOutput')], []);
      });

      let loaded: Awaited<ReturnType<typeof result.current.loadWorkflow>> = null;
      await act(async () => {
        loaded = await result.current.loadWorkflow(botId);
      });

      expect(loaded!.nodes).toHaveLength(1);
      expect(loaded!.nodes[0].data.nodeType).toBe('msgOutput');
    });
  });

  describe('损坏数据容错', () => {
    it('localStorage 中数据格式损坏 → load 返回 null', async () => {
      localStorage.setItem('morphix_workflow_corrupt', '{invalid json!!!');

      const { result } = renderHook(() => useWorkflowPersistence());

      let loaded: Awaited<ReturnType<typeof result.current.loadWorkflow>> = null;
      await act(async () => {
        loaded = await result.current.loadWorkflow('corrupt');
      });

      expect(loaded).toBeNull();
    });

    it('localStorage 中缺少 nodes 字段 → load 返回 null', async () => {
      localStorage.setItem(
        'morphix_workflow_incomplete',
        JSON.stringify({ botId: 'test' }),
      );

      const { result } = renderHook(() => useWorkflowPersistence());

      let loaded: Awaited<ReturnType<typeof result.current.loadWorkflow>> = null;
      await act(async () => {
        loaded = await result.current.loadWorkflow('incomplete');
      });

      expect(loaded).toBeNull();
    });
  });
});

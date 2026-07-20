import { describe, it, expect, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useMockExecution } from '../hooks/useMockExecution';
import { useSubflowStorage } from '../hooks/useSubflowStorage';
import type { OrchestrateNode, OrchestrateEdge } from '../components/FlowCanvas';
import type { SubflowPersisted } from '../types/orchestrate';

/** 构造测试用 OrchestrateNode */
function makeNode(
  id: string,
  nodeType: string,
  overrides: Partial<OrchestrateNode['data']> = {},
): OrchestrateNode {
  return {
    id,
    type: 'customNode',
    position: { x: 0, y: 0 },
    data: {
      nodeType,
      config: {},
      inputs: {},
      ...overrides,
    },
  } as OrchestrateNode;
}

/** 构造测试用 OrchestrateEdge */
function makeEdge(
  id: string,
  source: string,
  target: string,
  sourceHandle?: string,
  targetHandle?: string,
): OrchestrateEdge {
  return {
    id,
    source,
    target,
    sourceHandle: sourceHandle ?? '',
    targetHandle: targetHandle ?? '',
  } as OrchestrateEdge;
}

describe('useMockExecution', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  // ──── Kahn 拓扑排序 ────

  describe('拓扑排序 (Kahn 算法)', () => {
    it('线性 DAG: a→b→c', () => {
      const { result } = renderHook(() => useMockExecution());
      const nodes = [
        makeNode('a', 'userInput'),
        makeNode('b', 'aiChat'),
        makeNode('c', 'msgOutput'),
      ];
      const edges = [
        makeEdge('e1', 'a', 'b', 'userChatInput', 'question'),
        makeEdge('e2', 'b', 'c', 'aiReply', 'message'),
      ];

      let session!: ReturnType<typeof result.current.mockExecute>;
      act(() => {
        session = result.current.mockExecute(nodes, edges, '你好');
      });

      // 拓扑序应为 a → b → c
      const traceIds = session.trace.map((r) => r.nodeId);
      expect(traceIds).toEqual(['a', 'b', 'c']);
      expect(session.status).toBe('completed');
      expect(session.trace).toHaveLength(3);
    });

    it('分支 DAG: a→b, a→c (两分支并行)', () => {
      const { result } = renderHook(() => useMockExecution());
      const nodes = [
        makeNode('a', 'userInput'),
        makeNode('b', 'aiChat'),
        makeNode('c', 'kbSearch'),
      ];
      const edges = [
        makeEdge('e1', 'a', 'b', 'userChatInput', 'question'),
        makeEdge('e2', 'a', 'c', 'userChatInput', 'query'),
      ];

      let session!: ReturnType<typeof result.current.mockExecute>;
      act(() => {
        session = result.current.mockExecute(nodes, edges, '你好');
      });

      // a 必须先于 b 和 c
      const traceIds = session.trace.map((r) => r.nodeId);
      expect(traceIds[0]).toBe('a');
      expect(traceIds).toContain('b');
      expect(traceIds).toContain('c');
      expect(session.trace).toHaveLength(3);
    });

    it('菱形 DAG: a→b→d, a→c→d', () => {
      const { result } = renderHook(() => useMockExecution());
      const nodes = [
        makeNode('a', 'userInput'),
        makeNode('b', 'aiChat'),
        makeNode('c', 'kbSearch'),
        makeNode('d', 'msgOutput'),
      ];
      const edges = [
        makeEdge('e1', 'a', 'b', 'userChatInput', 'question'),
        makeEdge('e2', 'a', 'c', 'userChatInput', 'query'),
        makeEdge('e3', 'b', 'd', 'aiReply', 'message'),
        makeEdge('e4', 'c', 'd', 'knowledges', 'message'),
      ];

      let session!: ReturnType<typeof result.current.mockExecute>;
      act(() => {
        session = result.current.mockExecute(nodes, edges, '你好');
      });

      const traceIds = session.trace.map((r) => r.nodeId);
      expect(traceIds[0]).toBe('a');
      expect(traceIds[traceIds.length - 1]).toBe('d');
      expect(session.trace).toHaveLength(4);
    });

    it('单节点 DAG', () => {
      const { result } = renderHook(() => useMockExecution());
      const nodes = [makeNode('x', 'userInput')];
      const edges: OrchestrateEdge[] = [];

      let session!: ReturnType<typeof result.current.mockExecute>;
      act(() => {
        session = result.current.mockExecute(nodes, edges, 'test');
      });

      expect(session.trace).toHaveLength(1);
      expect(session.trace[0].nodeId).toBe('x');
      expect(session.status).toBe('completed');
    });

    it('空节点列表', () => {
      const { result } = renderHook(() => useMockExecution());
      let session!: ReturnType<typeof result.current.mockExecute>;
      act(() => {
        session = result.current.mockExecute([], [], 'empty');
      });

      expect(session.trace).toHaveLength(0);
      expect(session.status).toBe('completed');
    });
  });

  // ──── 环路检测 ────

  describe('环路检测', () => {
    it('简单环路 a→b→a 返回错误 session', () => {
      const { result } = renderHook(() => useMockExecution());
      const nodes = [
        makeNode('a', 'userInput'),
        makeNode('b', 'aiChat'),
      ];
      const edges = [
        makeEdge('e1', 'a', 'b'),
        makeEdge('e2', 'b', 'a'),
      ];

      let session!: ReturnType<typeof result.current.mockExecute>;
      act(() => {
        session = result.current.mockExecute(nodes, edges, 'cycle');
      });

      expect(session.status).toBe('completed');
      expect(session.trace).toHaveLength(1);
      expect(session.trace[0].nodeId).toBe('__cycle__');
      expect(session.trace[0].status).toBe('error');
      expect(session.trace[0].error).toContain('环路');
    });

    it('自环路 a→a 返回错误', () => {
      const { result } = renderHook(() => useMockExecution());
      const nodes = [makeNode('a', 'userInput')];
      const edges = [makeEdge('e1', 'a', 'a')];

      let session!: ReturnType<typeof result.current.mockExecute>;
      act(() => {
        session = result.current.mockExecute(nodes, edges, 'self');
      });

      expect(session.trace[0].nodeId).toBe('__cycle__');
      expect(session.trace[0].status).toBe('error');
    });
  });

  // ──── 执行记录结构 ────

  describe('执行记录 (NodeExecutionRecord) 结构', () => {
    it('每条记录包含必要字段', () => {
      const { result } = renderHook(() => useMockExecution());
      const nodes = [makeNode('n1', 'userInput')];
      const edges: OrchestrateEdge[] = [];

      let session!: ReturnType<typeof result.current.mockExecute>;
      act(() => {
        session = result.current.mockExecute(nodes, edges, 'hello');
      });

      const record = session.trace[0];
      expect(record.nodeId).toBe('n1');
      expect(record.nodeType).toBe('userInput');
      expect(record.status).toBe('success');
      expect(record.startedAt).toBeDefined();
      expect(record.finishedAt).toBeDefined();
      expect(record.durationMs).toBeGreaterThanOrEqual(0);
      expect(record.inputs).toBeDefined();
      expect(record.outputs).toBeDefined();
    });

    it('userInput 节点输出包含 userChatInput', () => {
      const { result } = renderHook(() => useMockExecution());
      const nodes = [makeNode('n1', 'userInput')];
      const edges: OrchestrateEdge[] = [];

      let session!: ReturnType<typeof result.current.mockExecute>;
      act(() => {
        session = result.current.mockExecute(nodes, edges, '你好世界');
      });

      const record = session.trace[0];
      expect(record.outputs.userChatInput).toBe('你好世界');
    });

    it('DebugSession 包含 sessionId 和 userMessage', () => {
      const { result } = renderHook(() => useMockExecution());
      const nodes = [makeNode('n1', 'userInput')];
      const edges: OrchestrateEdge[] = [];

      let session!: ReturnType<typeof result.current.mockExecute>;
      act(() => {
        session = result.current.mockExecute(nodes, edges, '测试消息');
      });

      expect(session.sessionId.startsWith('debug-')).toBe(true);
      expect(session.userMessage).toBe('测试消息');
      expect(session.startedAt).toBeDefined();
      expect(session.totalDurationMs).toBeGreaterThanOrEqual(0);
    });
  });

  // ──── 未实现节点 ────

  describe('未注册节点类型处理', () => {
    it('未知节点类型标记为 warning', () => {
      const { result } = renderHook(() => useMockExecution());
      const nodes = [makeNode('n1', 'totallyUnknownType')];
      const edges: OrchestrateEdge[] = [];

      let session!: ReturnType<typeof result.current.mockExecute>;
      act(() => {
        session = result.current.mockExecute(nodes, edges, 'test');
      });

      const record = session.trace[0];
      expect(record.status).toBe('warning');
      expect(record.mockNote).toContain('未实现');
    });
  });

  // ──── 子流程递归执行 ────

  describe('subflowCall 递归执行', () => {
    it('subflowCall 节点引用已保存的子流程时成功执行', () => {
      // 先保存子流程到 localStorage
      const { result: storageResult } = renderHook(() => useSubflowStorage());

      const savedSubflow: SubflowPersisted = {
        id: 'sf-exec-1',
        name: 'Internal Subflow',
        desc: '',
        interface: {
          inputs: [],
          outputs: [{ key: 'aiReply', varName: 'aiReply', dataType: 'any', direction: 'output', label: 'aiChat · AI回复' }],
        },
        nodes: [
          {
            id: 'sf-inner-1',
            type: 'customNode',
            position: { x: 0, y: 0 },
            data: { nodeType: 'aiChat', config: { model: 'DeepSeek' }, inputs: {} },
          },
        ],
        edges: [],
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
        version: 1,
      };

      act(() => {
        storageResult.current.saveSubflow(savedSubflow);
      });

      // 然后 mock 执行引用该子流程
      const { result: execResult } = renderHook(() => useMockExecution());
      const nodes = [
        makeNode('n1', 'subflowCall', { subflowId: 'sf-exec-1', subflowName: 'Internal Subflow' }),
      ];
      const edges: OrchestrateEdge[] = [];

      let session!: ReturnType<typeof execResult.current.mockExecute>;
      act(() => {
        session = execResult.current.mockExecute(nodes, edges, 'test');
      });

      const record = session.trace[0];
      expect(record.status).toBe('success');
      expect(record.mockNote).toContain('子流程调用');
    });

    it('subflowCall 引用不存在的子流程时报错', () => {
      const { result } = renderHook(() => useMockExecution());
      const nodes = [
        makeNode('n1', 'subflowCall', { subflowId: 'nonexistent-subflow' }),
      ];
      const edges: OrchestrateEdge[] = [];

      let session!: ReturnType<typeof result.current.mockExecute>;
      act(() => {
        session = result.current.mockExecute(nodes, edges, 'test');
      });

      const record = session.trace[0];
      expect(record.status).toBe('error');
      expect(record.error).toContain('未找到');
    });

    it('subflowCall 无 subflowId 时标记 warning', () => {
      const { result } = renderHook(() => useMockExecution());
      const nodes = [
        makeNode('n1', 'subflowCall', { subflowId: undefined }),
      ];
      const edges: OrchestrateEdge[] = [];

      let session!: ReturnType<typeof result.current.mockExecute>;
      act(() => {
        session = result.current.mockExecute(nodes, edges, 'test');
      });

      const record = session.trace[0];
      expect(record.status).toBe('warning');
      expect(record.mockNote).toContain('子流程 ID 未定义');
    });
  });

  // ──── 输出节点标记 ────

  describe('输出节点 mockNote 标记', () => {
    it('msgOutput 节点标记 mockNote', () => {
      const { result } = renderHook(() => useMockExecution());
      const nodes = [makeNode('n1', 'msgOutput')];
      const edges: OrchestrateEdge[] = [];

      let session!: ReturnType<typeof result.current.mockExecute>;
      act(() => {
        session = result.current.mockExecute(nodes, edges, 'test');
      });

      expect(session.trace[0].mockNote).toContain('消息输出节点');
    });
  });
});

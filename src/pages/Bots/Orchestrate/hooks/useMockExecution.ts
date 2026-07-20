import { useCallback } from 'react';
import {
  mockExecutors,
  defaultMockExecutor,
  OUTPUT_NODE_TYPES,
  type ExecutionContext,
  type MockFunction,
} from '../data/mockExecutors';
import { useSubflowStorage } from './useSubflowStorage';
import type {
  NodeExecutionRecord,
  DebugSession,
  SerializedNode,
  SerializedEdge,
} from '../types/orchestrate';
import type { OrchestrateNode, OrchestrateEdge } from '../components/FlowCanvas';

/** DAG 结构 */
interface DAG {
  adj: Map<string, string[]>;
  inDegree: Map<string, number>;
}

/** 生成调试会话 ID */
function generateSessionId(): string {
  return `debug-${Date.now()}`;
}

/**
 * Mock 执行引擎 hook。
 * 接收画布 nodes/edges 和用户消息，按拓扑序逐节点执行 mock 策略。
 */
export function useMockExecution() {
  const { loadSubflow } = useSubflowStorage();

  /** 构建邻接表和入度表 */
  const buildDAG = useCallback(
    (nodes: OrchestrateNode[], edges: OrchestrateEdge[]): DAG => {
      const adj = new Map<string, string[]>();
      const inDegree = new Map<string, number>();

      for (const node of nodes) {
        adj.set(node.id, []);
        inDegree.set(node.id, 0);
      }

      for (const edge of edges) {
        const neighbors = adj.get(edge.source);
        if (neighbors) {
          neighbors.push(edge.target);
        }
        inDegree.set(edge.target, (inDegree.get(edge.target) ?? 0) + 1);
      }

      return { adj, inDegree };
    },
    [],
  );

  /** Kahn 算法拓扑排序 */
  const topologicalSort = useCallback(
    (nodes: OrchestrateNode[], dag: DAG): string[] => {
      const result: string[] = [];
      const inDegree = new Map(dag.inDegree);
      const queue: string[] = [];

      for (const node of nodes) {
        if ((inDegree.get(node.id) ?? 0) === 0) {
          queue.push(node.id);
        }
      }

      while (queue.length > 0) {
        const current = queue.shift()!;
        result.push(current);

        const neighbors = dag.adj.get(current) ?? [];
        for (const neighbor of neighbors) {
          const newDegree = (inDegree.get(neighbor) ?? 0) - 1;
          inDegree.set(neighbor, newDegree);
          if (newDegree === 0) {
            queue.push(neighbor);
          }
        }
      }

      return result;
    },
    [],
  );

  /** 收集上游节点的输出值，映射到当前节点的输入端口 */
  const collectInputs = useCallback(
    (
      nodeId: string,
      _nodes: OrchestrateNode[],
      edges: OrchestrateEdge[],
      nodeOutputs: Map<string, Record<string, unknown>>,
      context: ExecutionContext,
    ): Record<string, unknown> => {
      const collected: Record<string, unknown> = {};
      const incomingEdges = edges.filter((e) => e.target === nodeId);

      for (const edge of incomingEdges) {
        const sourceOutputs = nodeOutputs.get(edge.source);
        if (sourceOutputs && edge.sourceHandle) {
          collected[edge.targetHandle ?? ''] = sourceOutputs[edge.sourceHandle];
        }
      }

      // 同时从 context 中注入 userChatInput（适用于 userInput 等节点）
      return { ...collected, userChatInput: context.userChatInput };
    },
    [],
  );

  /** 创建单节点执行记录 */
  const createRecord = useCallback(
    (
      nodeId: string,
      nodeName: string,
      nodeType: string,
      status: NodeExecutionRecord['status'],
      startedAt: string,
      finishedAt: string,
      inputs: Record<string, unknown>,
      outputs: Record<string, unknown>,
      mockNote?: string,
      error?: string,
    ): NodeExecutionRecord => {
      const durationMs = new Date(finishedAt).getTime() - new Date(startedAt).getTime();
      return {
        nodeId,
        nodeName,
        nodeType,
        status,
        startedAt,
        finishedAt,
        durationMs,
        inputs,
        outputs,
        mockNote,
        error,
      };
    },
    [],
  );

  /** 执行子流程调用（递归） */
  const executeSubflowNode = useCallback(
    (
      subflowId: string,
      externalInputs: Record<string, unknown>,
      context: ExecutionContext,
    ): { outputs: Record<string, unknown>; subTrace: NodeExecutionRecord[] } => {
      const subflow = loadSubflow(subflowId);
      if (!subflow) {
        return {
          outputs: { _error: `子流程 ${subflowId} 未找到` },
          subTrace: [],
        };
      }

      // 构建子流程内部 DAG
      const subNodes: OrchestrateNode[] = subflow.nodes.map((n: SerializedNode) => ({
        id: n.id,
        type: n.type,
        position: n.position,
        data: {
          nodeType: n.data.nodeType,
          config: { ...n.data.config },
          inputs: { ...n.data.inputs },
        },
      }));

      const subEdges: OrchestrateEdge[] = subflow.edges.map((e: SerializedEdge) => ({
        id: e.id,
        source: e.source,
        target: e.target,
        sourceHandle: e.sourceHandle,
        targetHandle: e.targetHandle,
      }));

      const dag = buildDAG(subNodes, subEdges);
      const order = topologicalSort(subNodes, dag);

      if (order.length !== subNodes.length) {
        return {
          outputs: { _error: '子流程存在环路' },
          subTrace: [],
        };
      }

      const subNodeMap = new Map(subNodes.map((n) => [n.id, n]));
      const subEdgeMap = subEdges;
      const subNodeOutputs = new Map<string, Record<string, unknown>>();
      const subTrace: NodeExecutionRecord[] = [];
      const subContext: ExecutionContext = {
        ...context,
        ...externalInputs,
      };

      // 注入外部输入到子流程初始节点
      for (const [key, value] of Object.entries(externalInputs)) {
        subContext[key] = value;
      }

      for (const nodeId of order) {
        const node = subNodeMap.get(nodeId);
        if (!node) continue;

        const startedAt = new Date().toISOString();
        const inputs = collectInputs(nodeId, subNodes, subEdgeMap, subNodeOutputs, subContext);

        // 对于 userInput 节点，将外部输入注入
        if (node.data.nodeType === 'userInput') {
          inputs.userChatInput = subContext.userChatInput;
        }

        const executor: MockFunction = mockExecutors[node.data.nodeType] ?? defaultMockExecutor;

        let outputs: Record<string, unknown>;
        let status: NodeExecutionRecord['status'] = 'success';
        let mockNote: string | undefined;
        let error: string | undefined;

        try {
          outputs = executor(subContext, node.data.config as Record<string, unknown>, inputs);

          if (OUTPUT_NODE_TYPES.has(node.data.nodeType)) {
            mockNote = '消息输出节点，mock 模式下不实际发送';
          }
          if (outputs._unimplemented) {
            status = 'warning';
            mockNote = '未实现的节点类型，已透传输入值';
          }
        } catch (e) {
          outputs = {};
          status = 'error';
          error = e instanceof Error ? e.message : String(e);
        }

        subNodeOutputs.set(nodeId, outputs);
        const finishedAt = new Date().toISOString();

        subTrace.push(
          createRecord(nodeId, node.data.nodeType, node.data.nodeType, status, startedAt, finishedAt, inputs, outputs, mockNote, error),
        );
      }

      // 汇总子流程输出接口
      const aggregatedOutputs: Record<string, unknown> = {};
      for (const outPort of subflow.interface.outputs) {
        // 查找子流程内部产生此输出的节点
        for (const node of subNodes) {
          const outputs = subNodeOutputs.get(node.id);
          if (outputs && outPort.key in outputs) {
            aggregatedOutputs[outPort.key] = outputs[outPort.key];
          }
        }
      }

      return { outputs: aggregatedOutputs, subTrace };
    },
    [loadSubflow, buildDAG, topologicalSort, collectInputs, createRecord],
  );

  /**
   * 主执行入口：
   * 1. 构建 DAG + 拓扑排序
   * 2. 按拓扑序逐节点 mock 执行
   * 3. 返回 DebugSession
   */
  const mockExecute = useCallback(
    (nodes: OrchestrateNode[], edges: OrchestrateEdge[], userMessage: string): DebugSession => {
      const sessionId = generateSessionId();
      const sessionStartedAt = new Date().toISOString();

      const dag = buildDAG(nodes, edges);
      const order = topologicalSort(nodes, dag);

      // 环路检测
      if (order.length !== nodes.length) {
        const trace: NodeExecutionRecord[] = [
          createRecord(
            '__cycle__', '环路检测', 'system', 'error',
            sessionStartedAt, new Date().toISOString(),
            { userMessage }, {},
            undefined, '工作流存在环路，无法执行',
          ),
        ];
        return {
          sessionId,
          startedAt: sessionStartedAt,
          status: 'completed',
          trace,
          totalDurationMs: 0,
          userMessage,
        };
      }

      const nodeMap = new Map(nodes.map((n) => [n.id, n]));
      const nodeOutputs = new Map<string, Record<string, unknown>>();
      const trace: NodeExecutionRecord[] = [];
      const context: ExecutionContext = { userChatInput: userMessage };

      for (const nodeId of order) {
        const node = nodeMap.get(nodeId);
        if (!node) continue;

        const startedAt = new Date().toISOString();
        const inputs = collectInputs(nodeId, nodes, edges, nodeOutputs, context);

        let outputs: Record<string, unknown> = {};
        let status: NodeExecutionRecord['status'] = 'success';
        let mockNote: string | undefined;
        let error: string | undefined;

        // subflowCall 特殊处理
        if (node.data.nodeType === 'subflowCall') {
          const subflowId = node.data.subflowId;
          if (subflowId) {
            const subResult = executeSubflowNode(subflowId, inputs, context);
            outputs = subResult.outputs;
            mockNote = `子流程调用，内部 ${subResult.subTrace.length} 个节点已执行`;

            if (outputs._error) {
              status = 'error';
              error = outputs._error as string;
            }
          } else {
            status = 'warning';
            mockNote = '子流程 ID 未定义，跳过执行';
          }
        } else {
          const executor: MockFunction = mockExecutors[node.data.nodeType] ?? defaultMockExecutor;

          try {
            outputs = executor(context, node.data.config as Record<string, unknown>, inputs);

            if (OUTPUT_NODE_TYPES.has(node.data.nodeType)) {
              mockNote = '消息输出节点，mock 模式下不实际发送';
            }
            if (outputs._unimplemented) {
              status = 'warning';
              mockNote = '未实现的节点类型，已透传输入值';
              delete outputs._unimplemented;
            }
          } catch (e) {
            outputs = {};
            status = 'error';
            error = e instanceof Error ? e.message : String(e);
          }
        }

        // 写入 context（供下游节点查询）
        for (const [key, value] of Object.entries(outputs)) {
          context[`${nodeId}.${key}`] = value;
        }

        nodeOutputs.set(nodeId, outputs);
        const finishedAt = new Date().toISOString();

        const nodeName = node.data.subflowName ?? node.data.nodeType;

        trace.push(
          createRecord(nodeId, nodeName, node.data.nodeType, status, startedAt, finishedAt, inputs, outputs, mockNote, error),
        );
      }

      const totalDurationMs = trace.reduce((sum, r) => sum + r.durationMs, 0);

      return {
        sessionId,
        startedAt: sessionStartedAt,
        status: 'completed',
        trace,
        totalDurationMs,
        userMessage,
      };
    },
    [buildDAG, topologicalSort, collectInputs, createRecord, executeSubflowNode],
  );

  return { mockExecute };
}

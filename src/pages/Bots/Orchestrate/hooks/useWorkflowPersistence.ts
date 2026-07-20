import { useCallback } from 'react';
import { useOrchestrateStore } from '../store/orchestrateStore';
import { createDefaultWorkflow } from '../data/defaultWorkflow';
import { workflowApi } from '../../../../api/client';
import type {
  OrchestrateNode,
  OrchestrateEdge,
} from '../components/FlowCanvas';
import type { WorkflowPersisted, SerializedNode, SerializedEdge } from '../types/orchestrate';

const STORAGE_KEY_PREFIX = 'morphix_workflow_';

function storageKey(botId: string): string {
  return `${STORAGE_KEY_PREFIX}${botId}`;
}

function serializeNode(node: OrchestrateNode): SerializedNode {
  const data: SerializedNode['data'] = {
    nodeType: node.data.nodeType,
    config: { ...node.data.config },
    inputs: { ...node.data.inputs },
  };

  // 保留 subflowCall 节点特有字段
  if (node.data.subflowId) data.subflowId = node.data.subflowId;
  if (node.data.subflowName) data.subflowName = node.data.subflowName;
  if (node.data.subflowDesc) data.subflowDesc = node.data.subflowDesc;
  if (node.data.inputPortsCount !== undefined) data.inputPortsCount = node.data.inputPortsCount;
  if (node.data.outputPortsCount !== undefined) data.outputPortsCount = node.data.outputPortsCount;

  return {
    id: node.id,
    type: node.type ?? 'customNode',
    position: { x: node.position.x, y: node.position.y },
    data,
  };
}

function serializeEdge(edge: OrchestrateEdge): SerializedEdge {
  return {
    id: edge.id,
    source: edge.source,
    target: edge.target,
    sourceHandle: edge.sourceHandle ?? '',
    targetHandle: edge.targetHandle ?? '',
  };
}

function buildPersistedData(
  botId: string,
  nodes: OrchestrateNode[],
  edges: OrchestrateEdge[],
): WorkflowPersisted {
  return {
    botId,
    nodes: nodes.map(serializeNode),
    edges: edges.map(serializeEdge),
    lastEdited: new Date().toISOString(),
    version: 1,
  };
}

/**
 * localStorage 持久化 hook（API 优先 + localStorage fallback）。
 *
 * - loadWorkflow：先尝试 workflowApi.load(botId)，失败则从 localStorage 读取
 * - saveWorkflow：先尝试 workflowApi.save(botId, data)，失败则写入 localStorage
 * - exportWorkflow：生成 JSON 文件下载
 * - getDefaultWorkflow：返回默认工作流
 *
 * 当后端工作流 CRUD 就绪后，将 USE_API 设为 true 即可切换。
 */
export function useWorkflowPersistence() {
  const { updateLastEdited } = useOrchestrateStore();

  /**
   * 从 localStorage 加载工作流（内部 fallback 路径）。
   */
  const loadFromLocalStorage = useCallback(
    (botId: string): WorkflowPersisted | null => {
      try {
        const raw = localStorage.getItem(storageKey(botId));
        if (!raw) return null;
        const parsed: WorkflowPersisted = JSON.parse(raw);
        if (parsed && parsed.nodes && parsed.edges) {
          return parsed;
        }
        return null;
      } catch (err) {
        console.warn('加载工作流失败:', err);
        return null;
      }
    },
    [],
  );

  /**
   * 写入 localStorage（内部 fallback 路径）。
   */
  const saveToLocalStorage = useCallback(
    (data: WorkflowPersisted): boolean => {
      try {
        localStorage.setItem(storageKey(data.botId), JSON.stringify(data));
        updateLastEdited();
        return true;
      } catch (err) {
        console.error('保存工作流失败:', err);
        return false;
      }
    },
    [updateLastEdited],
  );

  /**
   * 加载工作流：API 优先 → localStorage fallback。
   */
  const loadWorkflow = useCallback(
    async (botId: string): Promise<WorkflowPersisted | null> => {
      try {
        const data = await workflowApi.load(botId);
        return data as WorkflowPersisted;
      } catch {
        return loadFromLocalStorage(botId);
      }
    },
    [loadFromLocalStorage],
  );

  /**
   * 保存工作流：API 优先 → localStorage fallback。
   */
  const saveWorkflow = useCallback(
    async (botId: string, nodes: OrchestrateNode[], edges: OrchestrateEdge[]): Promise<boolean> => {
      const data = buildPersistedData(botId, nodes, edges);
      try {
        await workflowApi.save(botId, data);
        updateLastEdited();
        return true;
      } catch {
        return saveToLocalStorage(data);
      }
    },
    [updateLastEdited, saveToLocalStorage],
  );

  const exportWorkflow = useCallback(
    (botId: string, botName: string, nodes: OrchestrateNode[], edges: OrchestrateEdge[]): void => {
      try {
        const data = buildPersistedData(botId, nodes, edges);
        const blob = new Blob([JSON.stringify(data, null, 2)], {
          type: 'application/json',
        });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        const dateStr = new Date().toISOString().slice(0, 10);
        a.download = `${botName}_workflow_${dateStr}.json`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
      } catch (err) {
        console.error('导出工作流失败:', err);
      }
    },
    [],
  );

  const getDefaultWorkflow = useCallback(
    (botId: string): WorkflowPersisted => {
      return createDefaultWorkflow(botId);
    },
    [],
  );

  return { loadWorkflow, saveWorkflow, exportWorkflow, getDefaultWorkflow };
}

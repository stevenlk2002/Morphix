import { useCallback } from 'react';
import { type Node, type XYPosition } from '@xyflow/react';
import { NODE_SCHEMAS } from '../data/nodeDefinitions';
import { loadCustomNodes } from '../data/customNodeStorage';
import { useOrchestrateStore } from '../store/orchestrateStore';
import { useSubflowStorage } from './useSubflowStorage';
import type { NodeInstanceData, NodeSchema } from '../types/orchestrate';

let nextNodeId = 3;

/** 重置节点 ID 计数器（加载工作流后调用） */
export function setNextNodeId(n: number) {
  nextNodeId = n;
}

/** 查找节点 Schema（先查内置，再查自定义） */
function findSchema(nodeType: string): NodeSchema | null {
  if (NODE_SCHEMAS[nodeType]) return NODE_SCHEMAS[nodeType];

  if (nodeType.startsWith('custom:')) {
    const customNodes = loadCustomNodes();
    const found = customNodes.find((cn) => cn.id === nodeType);
    if (found) {
      return {
        inputs: found.inputs,
        outputs: found.outputs,
        config: found.config,
      };
    }
  }

  return null;
}

/**
 * 面板节点→画布拖拽 hook。
 * 处理画布上的 dragover 和 drop 事件，创建新的 React Flow 节点。
 * 支持普通节点拖入、自定义节点拖入和子流程拖入。
 */
export function useNodeDrag() {
  const setSelectedNodeId = useOrchestrateStore((s) => s.setSelectedNodeId);
  const { loadSubflow } = useSubflowStorage();

  const handleDragOver = useCallback((event: React.DragEvent) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = 'copy';
  }, []);

  const handleDrop = useCallback(
    (event: React.DragEvent, position: XYPosition) => {
      event.preventDefault();

      // 检查是否是子流程拖入
      const subflowId = event.dataTransfer.getData('application/morphix-subflow-id');
      if (subflowId) {
        const subflow = loadSubflow(subflowId);
        if (!subflow) return;

        const newNode: Node<NodeInstanceData> = {
          id: `node-${nextNodeId++}`,
          type: 'customNode',
          position,
          data: {
            nodeType: 'subflowCall',
            subflowId: subflow.id,
            subflowName: subflow.name,
            subflowDesc: subflow.desc,
            inputPortsCount: subflow.interface.inputs.length,
            outputPortsCount: subflow.interface.outputs.length,
            config: { note: '' },
            inputs: {},
          },
        };

        const dropEvent = new CustomEvent('morphix-node-drop', {
          detail: { node: newNode },
        });
        window.dispatchEvent(dropEvent);

        setSelectedNodeId(newNode.id);
        return;
      }

      // 普通/自定义节点拖入
      const nodeType = event.dataTransfer.getData('application/morphix-node-type');
      if (!nodeType) return;

      const schema = findSchema(nodeType);
      if (!schema) return;

      // 根据 schema.config 计算默认 config 值
      const defaultConfig: Record<string, string | number> = {};
      for (const field of schema.config) {
        if (field.default !== undefined) {
          defaultConfig[field.key] = field.default;
        }
      }

      const newNode: Node<NodeInstanceData> = {
        id: `node-${nextNodeId++}`,
        type: 'customNode',
        position,
        data: {
          nodeType,
          config: defaultConfig,
          inputs: {},
        },
      };

      // 通过自定义事件传递给 FlowCanvas（因为 addNodes 需要在 ReactFlow 上下文中调用）
      const dropEvent = new CustomEvent('morphix-node-drop', {
        detail: { node: newNode },
      });
      window.dispatchEvent(dropEvent);

      setSelectedNodeId(newNode.id);
    },
    [setSelectedNodeId, loadSubflow],
  );

  return { handleDragOver, handleDrop };
}

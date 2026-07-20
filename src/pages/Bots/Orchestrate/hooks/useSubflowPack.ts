import { useCallback } from 'react';
import { NODE_SCHEMAS } from '../data/nodeDefinitions';
import { loadCustomNodes } from '../data/customNodeStorage';
import { generateSubflowId } from './useSubflowStorage';
import type {
  SerializedNode,
  SerializedEdge,
  SubflowPersisted,
  SubflowInterface,
  SubflowPortDef,
  NodeSchema,
} from '../types/orchestrate';
import type { OrchestrateNode, OrchestrateEdge } from '../components/FlowCanvas';

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
 * 子流程打包 hook。
 * 框选画布节点后，分析暴露接口并生成 SubflowPersisted。
 */
export function useSubflowPack() {
  /**
   * 分析框选节点的暴露接口：
   * - 未连线输入 → 暴露为子流程输入接口
   * - 未连线输出 → 暴露为子流程输出接口
   */
  const analyzeSubflowInterface = useCallback(
    (
      allNodes: OrchestrateNode[],
      allEdges: OrchestrateEdge[],
      selectedNodeIds: string[],
    ): SubflowInterface => {
      const selectedSet = new Set(selectedNodeIds);
      const selectedNodes = allNodes.filter((n) => selectedSet.has(n.id));

      const inputs: SubflowPortDef[] = [];
      const outputs: SubflowPortDef[] = [];

      for (const node of selectedNodes) {
        const schema = findSchema(node.data.nodeType);
        if (!schema) continue;

        // 分析输入端口：检查是否没有任何外部边连接到此端口
        for (const inp of schema.inputs) {
          const hasInternalConnection = allEdges.some(
            (e) =>
              selectedSet.has(e.source) &&
              e.target === node.id &&
              e.targetHandle === inp.key,
          );

          // 如果该端口没有内部连线（来自框选内的其他节点），则暴露为接口输入
          if (!hasInternalConnection) {
            inputs.push({
              key: inp.key,
              varName: inp.varName,
              dataType: inp.dataType,
              direction: 'input',
              label: `${schema.outputs.length > 0 ? node.data.nodeType : node.data.nodeType} · ${inp.name}`,
            });
          }
        }

        // 分析输出端口：检查是否有外部边从此端口出发
        for (const out of schema.outputs) {
          const hasInternalConsumer = allEdges.some(
            (e) =>
              e.source === node.id &&
              e.sourceHandle === out.varName &&
              selectedSet.has(e.target),
          );
          const hasExternalConsumer = allEdges.some(
            (e) =>
              e.source === node.id &&
              e.sourceHandle === out.varName &&
              !selectedSet.has(e.target),
          );

          // 如果该端口有外部消费者（但不被内部消费），或没有被内部消费且原本没有消费者，暴露为接口输出
          if (hasExternalConsumer || !hasInternalConsumer) {
            outputs.push({
              key: out.varName,
              varName: out.varName,
              dataType: out.dataType,
              direction: 'output',
              label: `${node.data.nodeType} · ${out.name}`,
            });
          }
        }
      }

      return { inputs, outputs };
    },
    [],
  );

  /**
   * 执行打包：
   * 1. 生成子流程 ID
   * 2. 重新生成内部节点 ID
   * 3. 构建 SubflowPersisted → localStorage
   * 4. 替换画布选中节点为 subflowCall 节点
   */
  const packSubflow = useCallback(
    (
      name: string,
      desc: string,
      allNodes: OrchestrateNode[],
      allEdges: OrchestrateEdge[],
      selectedNodeIds: string[],
      iface: SubflowInterface,
    ): {
      subflow: SubflowPersisted;
      newNodes: OrchestrateNode[];
      newEdges: OrchestrateEdge[];
      subflowCallNodeId: string;
    } => {
      const selectedSet = new Set(selectedNodeIds);
      const subflowId = generateSubflowId();
      const idPrefix = subflowId.substring(0, 8);

      // 构建旧 ID → 新 ID 映射
      const idMap = new Map<string, string>();
      let counter = 0;
      for (const nodeId of selectedNodeIds) {
        const newId = `sf-${idPrefix}-node-${++counter}`;
        idMap.set(nodeId, newId);
      }

      // 重新生成内部节点
      const internalNodes: SerializedNode[] = [];
      for (const nodeId of selectedNodeIds) {
        const original = allNodes.find((n) => n.id === nodeId);
        if (!original) continue;
        const newId = idMap.get(nodeId) ?? nodeId;
        internalNodes.push({
          id: newId,
          type: original.type ?? 'customNode',
          position: {
            x: original.position.x,
            y: original.position.y,
          },
          data: {
            nodeType: original.data.nodeType,
            config: { ...original.data.config },
            inputs: { ...original.data.inputs },
          },
        });
      }

      // 重新生成内部边
      const internalEdges: SerializedEdge[] = [];
      const externalEdgesToKeep: OrchestrateEdge[] = [];
      const edgesToRemove: string[] = [];

      for (const edge of allEdges) {
        const sourceIn = selectedSet.has(edge.source);
        const targetIn = selectedSet.has(edge.target);

        if (sourceIn && targetIn) {
          // 内部边：重新映射 ID
          const newSourceId = idMap.get(edge.source) ?? edge.source;
          const newTargetId = idMap.get(edge.target) ?? edge.target;
          internalEdges.push({
            id: `sf-${idPrefix}-edge-${Date.now()}-${Math.random().toString(36).substring(2, 6)}`,
            source: newSourceId,
            target: newTargetId,
            sourceHandle: edge.sourceHandle ?? '',
            targetHandle: edge.targetHandle ?? '',
          });
          edgesToRemove.push(edge.id);
        } else if (!sourceIn && targetIn) {
          // 外部 → 内部：转为 subflowCall 输入连线
          // 保留这条边，但 target 改为 subflowCall 节点（后续处理）
          edgesToRemove.push(edge.id);
          externalEdgesToKeep.push(edge);
        } else if (sourceIn && !targetIn) {
          // 内部 → 外部：转为 subflowCall 输出连线
          edgesToRemove.push(edge.id);
          externalEdgesToKeep.push(edge);
        }
      }

      // 构建 SubflowPersisted
      const now = new Date().toISOString();
      const subflow: SubflowPersisted = {
        id: subflowId,
        name,
        desc,
        interface: iface,
        nodes: internalNodes,
        edges: internalEdges,
        createdAt: now,
        updatedAt: now,
        version: 1,
      };

      // 创建 subflowCall 节点
      const callNodeId = `node-${Date.now()}`;
      // 计算选中节点的平均位置
      let avgX = 0;
      let avgY = 0;
      let count = 0;
      for (const nodeId of selectedNodeIds) {
        const node = allNodes.find((n) => n.id === nodeId);
        if (node) {
          avgX += node.position.x;
          avgY += node.position.y;
          count++;
        }
      }
      if (count > 0) {
        avgX /= count;
        avgY /= count;
      }

      const subflowCallNode: OrchestrateNode = {
        id: callNodeId,
        type: 'customNode',
        position: { x: avgX, y: avgY },
        data: {
          nodeType: 'subflowCall',
          subflowId,
          subflowName: name,
          subflowDesc: desc,
          inputPortsCount: iface.inputs.length,
          outputPortsCount: iface.outputs.length,
          config: { note: '' },
          inputs: {},
        },
      };

      // 重新映射外部边：source/target 指向 subflowCallNode
      const remappedExternalEdges: OrchestrateEdge[] = externalEdgesToKeep.map((edge) => {
        const sourceIn = selectedSet.has(edge.source);
        const targetIn = selectedSet.has(edge.target);
        return {
          ...edge,
          id: `edge-${Date.now()}-${Math.random().toString(36).substring(2, 8)}`,
          source: sourceIn ? callNodeId : edge.source,
          target: targetIn ? callNodeId : edge.target,
          sourceHandle: sourceIn
            ? iface.outputs.find((o) => o.key === edge.sourceHandle)?.key ?? edge.sourceHandle
            : edge.sourceHandle,
          targetHandle: targetIn
            ? iface.inputs.find((i) => i.key === edge.targetHandle)?.key ?? edge.targetHandle
            : edge.targetHandle,
        };
      });

      // 构造新节点列表：移除选中节点，加入 subflowCall 节点
      const newNodes = [
        ...allNodes.filter((n) => !selectedSet.has(n.id)),
        subflowCallNode,
      ];

      // 构造新边列表：移除涉及选中节点的边，加入重新映射的外部边
      const edgesToRemoveSet = new Set(edgesToRemove);
      const newEdges = [
        ...allEdges.filter((e) => !edgesToRemoveSet.has(e.id)),
        ...remappedExternalEdges,
      ];

      return { subflow, newNodes, newEdges, subflowCallNodeId: callNodeId };
    },
    [],
  );

  return { analyzeSubflowInterface, packSubflow };
}

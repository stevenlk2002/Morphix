import { useCallback } from 'react';
import { NODE_SCHEMAS } from '../data/nodeDefinitions';
import { ORCHESTRATE_NODES } from '../data/panelNodes';
import { loadCustomNodes } from '../data/customNodeStorage';
import type { OrchestrateNode, OrchestrateEdge } from '../components/FlowCanvas';
import type { ValidationResult, ValidationError, NodeSchema } from '../types/orchestrate';

/** 获取节点显示名称 */
function getNodeName(nodeType: string): string {
  if (nodeType.startsWith('custom:')) {
    const customNodes = loadCustomNodes();
    const found = customNodes.find((cn) => cn.id === nodeType);
    if (found) return found.name;
    return nodeType;
  }

  for (const tab of Object.values(ORCHESTRATE_NODES)) {
    for (const cat of tab) {
      const found = cat.nodes.find((n) => n.id === nodeType);
      if (found) return found.title;
    }
  }
  return nodeType;
}

/** 查找节点 Schema */
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
 * 保存前校验 hook。
 * 遍历所有 nodes，检查：
 * 1. schema.inputs 中 required:true 的端口是否已连线或已直接输入值
 * 2. schema.config 中 required:true 的字段是否已填写
 */
export function useValidation() {
  const validate = useCallback(
    (nodes: OrchestrateNode[], edges: OrchestrateEdge[]): ValidationResult => {
      const errors: ValidationError[] = [];

      for (const node of nodes) {
        // 跳过占位节点 strongReminder
        if (node.data.nodeType === 'strongReminder') continue;

        const schema = findSchema(node.data.nodeType);
        if (!schema) continue;

        const nodeName = getNodeName(node.data.nodeType);

        // 检查 inputs
        for (const inp of schema.inputs) {
          if (!inp.required) continue;

          // 检查是否已连线
          const isConnected = edges.some(
            (e) => e.target === node.id && e.targetHandle === inp.key,
          );

          // 检查是否有直接输入值
          const hasInputValue =
            node.data.inputs[inp.key] !== undefined &&
            node.data.inputs[inp.key] !== '';

          if (!isConnected && !hasInputValue) {
            errors.push({
              nodeId: node.id,
              nodeName,
              fieldKey: inp.key,
              fieldName: inp.name,
              message: `节点『${nodeName}』的『${inp.name}』输入端口为必填项，请连线或输入值`,
            });
          }
        }

        // 检查 config
        for (const field of schema.config) {
          if (!field.required) continue;
          if (field.fieldType === 'note') continue;

          const value = node.data.config[field.key];
          if (value === undefined || value === '' || value === null) {
            errors.push({
              nodeId: node.id,
              nodeName,
              fieldKey: field.key,
              fieldName: field.label,
              message: `节点『${nodeName}』的『${field.label}』为必填项，请完成配置`,
            });
          }
        }
      }

      return {
        valid: errors.length === 0,
        errors,
      };
    },
    [],
  );

  return { validate };
}

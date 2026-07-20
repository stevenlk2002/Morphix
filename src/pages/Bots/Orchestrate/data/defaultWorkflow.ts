import type { SerializedNode, SerializedEdge, WorkflowPersisted } from '../types/orchestrate';

/**
 * 默认工作流：首次加载时展示 2 个节点 + 1 条连线（用户输入 → 智能体嵌入）。
 * 让用户打开即能看到彩色端口、贝塞尔曲线连线、× 删除按钮。
 */
export function createDefaultWorkflow(botId: string): WorkflowPersisted {
  const nodes: SerializedNode[] = [
    {
      id: 'node-1',
      type: 'customNode',
      position: { x: 60, y: 80 },
      data: {
        nodeType: 'userInput',
        config: {},
        inputs: {},
      },
    },
    {
      id: 'node-2',
      type: 'customNode',
      position: { x: 320, y: 80 },
      data: {
        nodeType: 'agentEmbed',
        config: { bot: '杨奇成健康机器人' },
        inputs: {},
      },
    },
  ];

  const edges: SerializedEdge[] = [
    {
      id: 'edge-default-1',
      source: 'node-1',
      target: 'node-2',
      sourceHandle: 'userChatInput',
      targetHandle: 'question',
    },
  ];

  return {
    botId,
    nodes,
    edges,
    lastEdited: new Date().toISOString(),
    version: 1,
  };
}

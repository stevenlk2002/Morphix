import type { DragEvent } from 'react';
import type { PanelNodeDef } from '../types/orchestrate';
import './NodeCard.css';

interface NodeCardProps {
  node: PanelNodeDef;
  onDragStart: (nodeType: string) => void;
}

/** 简单 icon 渲染 */
function renderIcon(def: PanelNodeDef): string {
  const map: Record<string, string> = {
    text: 'T',
    variable: 'Fx',
    'message-circle': '💬',
    send: '➤',
    image: '🖼',
    user: '👤',
    'git-branch': '◇',
    clock: '⏱',
    bot: '🤖',
    database: '📚',
    regex: '.*',
    braces: '{}',
    'alert-triangle': '⚠',
    package: '📦',
    file: '📄',
    video: '🎬',
    mic: '🎤',
    link: '🔗',
    'file-text': '📝',
    mail: '📧',
    smartphone: '📱',
  };
  return map[def.icon] ?? def.icon.substring(0, 2);
}

/**
 * 节点卡片（面板中可拖拽的节点卡片）。
 * 拖拽时通过 dataTransfer 传递 nodeType 或 subflowId。
 */
export default function NodeCard({ node, onDragStart }: NodeCardProps) {
  function handleDragStart(e: DragEvent<HTMLDivElement>) {
    // 子流程卡片：传递 subflowId
    if (node.id.startsWith('subflow:')) {
      const subflowId = node.id.substring('subflow:'.length);
      e.dataTransfer.setData('application/morphix-subflow-id', subflowId);
    } else {
      e.dataTransfer.setData('application/morphix-node-type', node.id);
    }
    e.dataTransfer.effectAllowed = 'copy';
    onDragStart(node.id);
  }

  return (
    <div
      className="node-card"
      draggable
      onDragStart={handleDragStart}
      data-node-type={node.id}
    >
      <div
        className="node-card__icon"
        style={{ backgroundColor: node.color + '20', color: node.color }}
      >
        {renderIcon(node)}
      </div>
      <div className="node-card__info">
        <div className="node-card__title">{node.title}</div>
        <div className="node-card__desc">{node.desc}</div>
      </div>
    </div>
  );
}

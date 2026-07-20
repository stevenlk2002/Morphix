/**
 * FlowNode — SOP 流程节点渲染组件。
 *
 * 支持 7 种节点类型：settings / group-settings / message / attr / robot / runRobot / delay
 * - settings 类型的节点不可删除，是流程的根节点
 * - 每个节点右侧有"+"按钮可添加子节点
 * - 非 settings 节点右上角有"×"删除按钮
 */
import { useState } from 'react'
import type { SopNode, SopNodeType } from '../../../types/sops'
import { NODE_TYPE_LABELS, CHILD_NODE_TYPES, GROUP_CHILD_NODE_TYPES } from '../../../types/sops'

interface FlowNodeProps {
  node: SopNode
  isFirst: boolean
  isGroup: boolean
  selected: boolean
  onSelect: (nodeId: string) => void
  onDelete: (nodeId: string) => void
  onAddChild: (parentNodeId: string, childType: SopNodeType) => void
}

const NODE_ICONS: Record<string, string> = {
  'settings': '⚙️',
  'group-settings': '⚙️',
  'message': '💬',
  'attr': '🏷️',
  'robot': '🤖',
  'runRobot': '▶️',
  'delay': '⏱️',
}

export default function FlowNode({
  node,
  isFirst,
  isGroup,
  selected,
  onSelect,
  onDelete,
  onAddChild,
}: FlowNodeProps) {
  const [menuOpen, setMenuOpen] = useState(false)
  const isSettings = node.type === 'settings' || node.type === 'group-settings'
  const childTypes = isGroup ? GROUP_CHILD_NODE_TYPES : CHILD_NODE_TYPES

  return (
    <div className="flow-node-wrapper">
      {/* 连线 */}
      {!isFirst && <div className="flow-connector" />}

      <div
        className={`flow-node ${selected ? 'flow-node--selected' : ''} ${isSettings ? 'flow-node--settings' : ''}`}
        onClick={() => onSelect(node.id)}
      >
        {/* 删除按钮（非 settings 节点） */}
        {!isSettings && (
          <button
            type="button"
            className="flow-node-delete"
            onClick={(e) => {
              e.stopPropagation()
              onDelete(node.id)
            }}
            title="删除节点"
          >
            ×
          </button>
        )}

        <div className="flow-node-icon">{NODE_ICONS[node.type] || '📌'}</div>
        <div className="flow-node-label">{NODE_TYPE_LABELS[node.type] || node.type}</div>
        {node.type === 'delay' && node.config.hours && (
          <div className="flow-node-sub">{node.config.hours}h</div>
        )}
        {node.type === 'message' && node.config.contentType && (
          <div className="flow-node-sub">
            {node.config.contentType === 'text' ? '文本' : node.config.contentType}
          </div>
        )}
      </div>

      {/* "+" 按钮 */}
      {!isGroup && (
        <div className="flow-add-wrapper">
          <button
            type="button"
            className="flow-add-btn"
            onClick={(e) => {
              e.stopPropagation()
              setMenuOpen(!menuOpen)
            }}
            title="添加节点"
          >
            +
          </button>
          {menuOpen && (
            <>
              <div className="flow-add-backdrop" onClick={() => setMenuOpen(false)} />
              <div className="flow-add-menu">
                {childTypes.map((ct) => (
                  <button
                    key={ct.type}
                    type="button"
                    className="flow-add-menu-item"
                    onClick={() => {
                      onAddChild(node.id, ct.type)
                      setMenuOpen(false)
                    }}
                  >
                    <span>{ct.icon}</span>
                    <span>{ct.label}</span>
                  </button>
                ))}
              </div>
            </>
          )}
        </div>
      )}
    </div>
  )
}

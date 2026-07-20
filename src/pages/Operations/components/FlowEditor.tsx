/**
 * FlowEditor — 可复用的流程编辑器容器。
 *
 * 三栏布局：左侧工具栏 + 中间画布 + 右侧配置面板。
 * 支持客户SOP和群聊SOP两种模式。
 */
import { useState, useCallback } from 'react'
import FlowNode from './FlowNode'
import FlowConfigPanel from './FlowConfigPanel'
import type { SopNode, SopNodeType, SopNodeConfig } from '../../../types/sops'

interface FlowEditorProps {
  initialNodes: SopNode[]
  isGroup: boolean
  onChange: (nodes: SopNode[]) => void
}

let idCounter = 0
function genNodeId(): string {
  idCounter += 1
  return `node-${Date.now()}-${idCounter}`
}

const NODE_WIDTH = 220
const NODE_GAP = 60

function createDefaultNode(type: SopNodeType, x: number, y: number): SopNode {
  const base: SopNode = { id: genNodeId(), type, x, y, config: {} }
  if (type === 'settings' || type === 'group-settings') {
    base.config = {
      channel: '企业微信',
      filterType: 'dynamic',
      dynamicFilter: { hostingAccountId: '', hostingBotId: '', tagRelation: 'and', tagIds: [] },
      stopWhenNotMatch: false,
      triggerType: 'attribute_change',
      triggerConfig: {},
    }
  }
  if (type === 'message') {
    base.config = { contentType: 'text', content: '' }
  }
  if (type === 'delay') {
    base.config = { hours: 0 }
  }
  return base
}

export default function FlowEditor({ initialNodes, isGroup, onChange }: FlowEditorProps) {
  const [nodes, setNodes] = useState<SopNode[]>(
    initialNodes.length > 0
      ? initialNodes
      : [createDefaultNode(isGroup ? 'group-settings' : 'settings', 60, 80)]
  )
  const [selectedId, setSelectedId] = useState<string | null>(
    nodes.length > 0 ? nodes[0].id : null
  )

  const selectedNode = nodes.find((n) => n.id === selectedId) || null

  const updateNodes = useCallback(
    (newNodes: SopNode[]) => {
      setNodes(newNodes)
      onChange(newNodes)
    },
    [onChange]
  )

  const handleSelect = (nodeId: string) => {
    setSelectedId(nodeId)
  }

  const handleDelete = (nodeId: string) => {
    const filtered = nodes.filter((n) => n.id !== nodeId)
    // 重新计算位置
    const repositioned = repositionNodes(filtered)
    if (selectedId === nodeId) {
      setSelectedId(repositioned.length > 0 ? repositioned[0].id : null)
    }
    updateNodes(repositioned)
  }

  const handleAddChild = (parentNodeId: string, childType: SopNodeType) => {
    const parentIdx = nodes.findIndex((n) => n.id === parentNodeId)
    if (parentIdx === -1) return

    const parentNode = nodes[parentIdx]
    const x = parentNode.x + NODE_WIDTH + NODE_GAP
    const y = parentNode.y

    // 如果目标位置已有节点，将后续节点右移
    const newNode = createDefaultNode(childType, x, y)
    const newNodes = [...nodes]

    // 插入到父节点之后
    const insertIdx = parentIdx + 1

    // 所有在插入位置之后的节点右移
    for (let i = insertIdx; i < newNodes.length; i++) {
      newNodes[i] = { ...newNodes[i], x: newNodes[i].x + NODE_WIDTH + NODE_GAP }
    }

    newNodes.splice(insertIdx, 0, newNode)
    updateNodes(newNodes)
    setSelectedId(newNode.id)
  }

  const handleConfigChange = (config: SopNodeConfig) => {
    if (!selectedId) return
    const updated = nodes.map((n) =>
      n.id === selectedId ? { ...n, config } : n
    )
    updateNodes(updated)
  }

  return (
    <div className="flow-editor">
      {/* 左侧工具栏 */}
      <div className="flow-toolbar">
        <div className="flow-toolbar-title">节点类型</div>
        <div className="flow-toolbar-items">
          <div className="flow-toolbar-item" title="流程设置">
            <span className="flow-toolbar-icon">⚙️</span>
            <span>{isGroup ? '群聊设置' : '流程设置'}</span>
          </div>
          <div className="flow-toolbar-item" title="消息触达">
            <span className="flow-toolbar-icon">💬</span>
            <span>消息触达</span>
          </div>
          {!isGroup && (
            <>
              <div className="flow-toolbar-item" title="属性修改">
                <span className="flow-toolbar-icon">🏷️</span>
                <span>属性修改</span>
              </div>
              <div className="flow-toolbar-item" title="机器人托管">
                <span className="flow-toolbar-icon">🤖</span>
                <span>机器人托管</span>
              </div>
              <div className="flow-toolbar-item" title="运行机器人">
                <span className="flow-toolbar-icon">▶️</span>
                <span>运行机器人</span>
              </div>
            </>
          )}
          <div className="flow-toolbar-item" title="等待">
            <span className="flow-toolbar-icon">⏱️</span>
            <span>等待</span>
          </div>
        </div>
      </div>

      {/* 中间画布 */}
      <div className="flow-canvas">
        {nodes.length === 0 ? (
          <div className="flow-canvas-empty">
            <p>暂无流程节点，请添加节点</p>
          </div>
        ) : (
          <div className="flow-canvas-nodes">
            {nodes.map((node, idx) => (
              <FlowNode
                key={node.id}
                node={node}
                isFirst={idx === 0}
                isGroup={isGroup}
                selected={node.id === selectedId}
                onSelect={handleSelect}
                onDelete={handleDelete}
                onAddChild={handleAddChild}
              />
            ))}
          </div>
        )}
      </div>

      {/* 右侧配置面板 */}
      <FlowConfigPanel node={selectedNode} onChange={handleConfigChange} />
    </div>
  )
}

/** 重新计算节点位置（水平排列，间距固定） */
function repositionNodes(nodes: SopNode[]): SopNode[] {
  return nodes.map((n, idx) => ({
    ...n,
    x: 60 + idx * (NODE_WIDTH + NODE_GAP),
  }))
}

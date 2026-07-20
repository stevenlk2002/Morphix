import { useMemo } from 'react';
import {
  ReactFlow,
  Background,
  MiniMap,
  type Node,
  type Edge,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { X } from 'lucide-react';
import { useSubflowStorage } from '../hooks/useSubflowStorage';
import { NODE_SCHEMAS } from '../data/nodeDefinitions';
import { getPortType } from '../data/portTypes';
import type { SubflowPersisted, NodeInstanceData } from '../types/orchestrate';
import './SubflowPreviewModal.css';

interface SubflowPreviewModalProps {
  subflowId: string;
  onClose: () => void;
}

/** Mini 只读节点（复用 CustomNode 的关键视觉元素） */
function MiniNode({ data }: { data: NodeInstanceData }) {
  const schema = NODE_SCHEMAS[data.nodeType];
  const nodeTypeLabel = data.nodeType;

  return (
    <div className="subflow-preview-node">
      <div className="subflow-preview-node__header">
        <span className="subflow-preview-node__type">{nodeTypeLabel}</span>
      </div>
      {schema && (
        <div className="subflow-preview-node__ports">
          <div className="subflow-preview-node__ports-col">
            {schema.inputs.slice(0, 3).map((inp) => (
              <div className="subflow-preview-node__port" key={inp.key}>
                <span
                  className="subflow-preview-node__port-dot"
                  style={{ backgroundColor: getPortType(inp.dataType).color }}
                />
                <span className="subflow-preview-node__port-name">{inp.name}</span>
              </div>
            ))}
            {schema.inputs.length > 3 && (
              <span className="subflow-preview-node__port-more">+{schema.inputs.length - 3}</span>
            )}
          </div>
          <div className="subflow-preview-node__ports-col subflow-preview-node__ports-col--right">
            {schema.outputs.slice(0, 3).map((out) => (
              <div className="subflow-preview-node__port" key={out.varName}>
                <span className="subflow-preview-node__port-name">{out.name}</span>
                <span
                  className="subflow-preview-node__port-dot"
                  style={{ backgroundColor: getPortType(out.dataType).color }}
                />
              </div>
            ))}
            {schema.outputs.length > 3 && (
              <span className="subflow-preview-node__port-more">+{schema.outputs.length - 3}</span>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

const previewNodeTypes = {
  miniNode: MiniNode,
};

/**
 * 子流程内部结构只读预览弹窗。
 * 使用 React Flow MiniMap + 只读画布展示子流程拓扑。
 */
export default function SubflowPreviewModal({
  subflowId,
  onClose,
}: SubflowPreviewModalProps) {
  const { loadSubflow } = useSubflowStorage();
  const subflow: SubflowPersisted | null = useMemo(
    () => loadSubflow(subflowId),
    [loadSubflow, subflowId],
  );

  const { rfNodes, rfEdges } = useMemo(() => {
    if (!subflow) return { rfNodes: [], rfEdges: [] };

    const nodes: Node<NodeInstanceData>[] = subflow.nodes.map((n) => ({
      id: n.id,
      type: 'miniNode',
      position: n.position,
      data: {
        nodeType: n.data.nodeType,
        config: { ...n.data.config },
        inputs: { ...n.data.inputs },
      },
    }));

    const edges: Edge[] = subflow.edges.map((e) => ({
      id: e.id,
      source: e.source,
      target: e.target,
      sourceHandle: e.sourceHandle,
      targetHandle: e.targetHandle,
      animated: false,
      style: { stroke: '#94a3b8', strokeWidth: 1.5 },
    }));

    return { rfNodes: nodes, rfEdges: edges };
  }, [subflow]);

  return (
    <div className="subflow-preview-modal__overlay" onClick={onClose}>
      <div
        className="subflow-preview-modal"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="subflow-preview-modal__header">
          <div>
            <h2 className="subflow-preview-modal__title">
              {subflow?.name ?? '子流程预览'}
            </h2>
            {subflow?.desc && (
              <p className="subflow-preview-modal__desc">{subflow.desc}</p>
            )}
          </div>
          <button
            className="subflow-preview-modal__close"
            onClick={onClose}
            title="关闭"
          >
            <X size={18} />
          </button>
        </div>

        {/* 接口摘要 */}
        {subflow && (
          <div className="subflow-preview-modal__interface">
            <span className="subflow-preview-modal__interface-badge">
              {subflow.interface.inputs.length} 入
            </span>
            <span className="subflow-preview-modal__interface-badge">
              {subflow.interface.outputs.length} 出
            </span>
          </div>
        )}

        {/* 只读画布 */}
        <div className="subflow-preview-modal__canvas">
          {subflow ? (
            <ReactFlow
              nodes={rfNodes}
              edges={rfEdges}
              nodeTypes={previewNodeTypes}
              nodesDraggable={false}
              nodesConnectable={false}
              elementsSelectable={false}
              deleteKeyCode={null}
              panOnDrag
              zoomOnScroll
              fitView
              proOptions={{ hideAttribution: true }}
            >
              <Background color="#e8eef6" gap={20} size={1} />
              <MiniMap
                position="bottom-left"
                nodeColor={(n) => {
                  const data = n.data as NodeInstanceData | undefined;
                  if (!data) return '#cbd5e1';
                  const schema = NODE_SCHEMAS[data.nodeType];
                  if (!schema || schema.outputs.length === 0) return '#94a3b8';
                  return getPortType(schema.outputs[0].dataType).color;
                }}
                maskColor="rgba(244, 248, 254, 0.6)"
                style={{ background: 'var(--surface)', border: '1px solid var(--border)' }}
              />
            </ReactFlow>
          ) : (
            <div className="subflow-preview-modal__empty">
              无法加载子流程数据
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

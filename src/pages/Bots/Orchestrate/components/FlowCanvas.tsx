import { useCallback, useEffect, useRef, useState, useMemo } from 'react';
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  type Node,
  type Edge,
  type Connection,
  type OnNodesChange,
  type OnEdgesChange,
  useReactFlow,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { Package } from 'lucide-react';
import CustomNode from './CustomNode';
import CustomEdge from './CustomEdge';
import ConnectionLine from './ConnectionLine';
import EmptyCanvas from './EmptyCanvas';
import SubflowPackModal from './SubflowPackModal';
import { canConnectTypes, getPortType } from '../data/portTypes';
import { NODE_SCHEMAS } from '../data/nodeDefinitions';
import { loadCustomNodes } from '../data/customNodeStorage';
import { useOrchestrateStore } from '../store/orchestrateStore';
import { useNodeDrag, setNextNodeId } from '../hooks/useNodeDrag';
import { toast } from '../../../../utils/toast';
import type { NodeInstanceData, NodeSchema } from '../types/orchestrate';
import './FlowCanvas.css';

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

export type OrchestrateNode = Node<NodeInstanceData>;
export type OrchestrateEdge = Edge;

/** React Flow 自定义节点/边类型注册表。
 * 兼容旧工作流数据：后端早期持久化将 data.nodeType 直接作为 node.type，
 * 统一兜底到 CustomNode，避免未知类型导致 MiniMap 崩溃白屏。
 */
const nodeTypes = {
  customNode: CustomNode,
  userInput: CustomNode,
  kbSearch: CustomNode,
  aiChat: CustomNode,
  msgOutput: CustomNode,
  agentEmbed: CustomNode,
};
const edgeTypes = { customEdge: CustomEdge };

interface FlowCanvasProps {
  nodes: OrchestrateNode[];
  edges: OrchestrateEdge[];
  onNodesChange: OnNodesChange<OrchestrateNode>;
  onEdgesChange: OnEdgesChange<OrchestrateEdge>;
  onNodesUpdate: (nodes: OrchestrateNode[]) => void;
  onEdgesUpdate: (edges: OrchestrateEdge[]) => void;
}

/**
 * React Flow 画布包装组件。
 * - 集成自定义节点/边/连线预览
 * - 处理 drop（面板→画布）、onConnect（连线校验）、选中事件
 * - Delete 键删除选中节点/线
 * - 框选 ≥2 节点 → 浮动"打包为子流程"按钮
 * - 测试模式下禁用交互 + 高亮当前执行节点
 */
export default function FlowCanvas({
  nodes,
  edges,
  onNodesChange,
  onEdgesChange,
  onNodesUpdate,
  onEdgesUpdate,
}: FlowCanvasProps) {
  const {
    setSelectedNodeId,
    setSelectedEdgeId,
    selectedNodeId,
    testMode,
    debugSession,
  } = useOrchestrateStore();

  const { handleDragOver, handleDrop } = useNodeDrag();
  const reactFlowInstance = useReactFlow();
  const clipboardRef = useRef<OrchestrateNode | null>(null);

  // 框选节点 ID 集合（用于显示打包按钮）
  const [selectedNodeIds, setSelectedNodeIds] = useState<string[]>([]);
  const [showPackModal, setShowPackModal] = useState(false);

  // 当前执行节点 ID（来自 debugSession.trace 中 status==='running' 的记录）
  const executingNodeId = useMemo(() => {
    if (!debugSession) return null;
    const running = debugSession.trace.find((r) => r.status === 'running');
    return running?.nodeId ?? null;
  }, [debugSession]);

  // 监听自定义 drop 事件
  useEffect(() => {
    function onNodeDrop(e: Event) {
      const detail = (e as CustomEvent).detail as { node: OrchestrateNode };
      if (detail?.node) {
        onNodesUpdate([...nodes, detail.node]);
      }
    }

    function onEdgeDelete(e: Event) {
      const detail = (e as CustomEvent).detail as { edgeId: string };
      if (detail?.edgeId) {
        onEdgesUpdate(edges.filter((ed) => ed.id !== detail.edgeId));
        setSelectedEdgeId(null);
        toast('已删除连线');
      }
    }

    window.addEventListener('morphix-node-drop', onNodeDrop);
    window.addEventListener('morphix-edge-delete', onEdgeDelete);

    return () => {
      window.removeEventListener('morphix-node-drop', onNodeDrop);
      window.removeEventListener('morphix-edge-delete', onEdgeDelete);
    };
  }, [nodes, edges, onNodesUpdate, onEdgesUpdate, setSelectedEdgeId]);

  // 更新 nextNodeId
  useEffect(() => {
    let maxId = 1;
    for (const n of nodes) {
      const match = n.id.match(/^node-(\d+)$/);
      if (match) {
        const num = parseInt(match[1], 10);
        if (num >= maxId) maxId = num + 1;
      }
    }
    setNextNodeId(maxId);
  }, [nodes]);

  // 监听 React Flow 选中变化（框选检测）
  const handleSelectionChange = useCallback(
    (params: { nodes: OrchestrateNode[] }) => {
      const ids = params.nodes.map((n) => n.id);
      setSelectedNodeIds(ids);
    },
    [],
  );

  // ──── 连线处理 ────
  const handleConnect = useCallback(
    (connection: Connection) => {
      if (!connection.source || !connection.target) return;
      if (!connection.sourceHandle || !connection.targetHandle) return;

      // 获取源节点和目标节点的 schema
      const sourceNode = nodes.find((n) => n.id === connection.source);
      const targetNode = nodes.find((n) => n.id === connection.target);

      if (!sourceNode || !targetNode) return;

      const sourceNodeType = sourceNode.data.nodeType;
      const targetNodeType = targetNode.data.nodeType;

      // 处理 subflowCall 节点：需要从子流程定义中获取端口信息
      let sourceType = 'any';
      let targetType = 'any';

      if (sourceNodeType === 'subflowCall' && sourceNode.data.subflowId) {
        // subflowCall 输出端口：从子流程定义的 interface.outputs 中查找
        const key = `morphix_subflow_${sourceNode.data.subflowId}`;
        try {
          const raw = localStorage.getItem(key);
          if (raw) {
            const sf = JSON.parse(raw);
            const outPort = sf.interface?.outputs?.find(
              (o: { key: string }) => o.key === connection.sourceHandle,
            );
            if (outPort) sourceType = outPort.dataType;
          }
        } catch { /* ignore */ }
      } else {
        const sourceSchema = findSchema(sourceNodeType);
        if (sourceSchema) {
          const sourceOutput = sourceSchema.outputs.find(
            (o) => o.varName === connection.sourceHandle,
          );
          sourceType = sourceOutput?.dataType ?? 'any';
        }
      }

      if (targetNodeType === 'subflowCall' && targetNode.data.subflowId) {
        // subflowCall 输入端口
        const key = `morphix_subflow_${targetNode.data.subflowId}`;
        try {
          const raw = localStorage.getItem(key);
          if (raw) {
            const sf = JSON.parse(raw);
            const inPort = sf.interface?.inputs?.find(
              (i: { key: string }) => i.key === connection.targetHandle,
            );
            if (inPort) targetType = inPort.dataType;
          }
        } catch { /* ignore */ }
      } else {
        const targetSchema = findSchema(targetNodeType);
        if (targetSchema) {
          const targetInput = targetSchema.inputs.find(
            (i) => i.key === connection.targetHandle,
          );
          targetType = targetInput?.dataType ?? 'any';
        }
      }

      // 校验类型兼容性
      if (!canConnectTypes(sourceType, targetType)) {
        toast(
          `连接类型不一致：${getPortType(sourceType).label} → ${getPortType(targetType).label}`,
        );
        return;
      }

      // 检查是否已存在相同连线
      const exists = edges.some(
        (e) =>
          e.source === connection.source &&
          e.target === connection.target &&
          e.sourceHandle === connection.sourceHandle &&
          e.targetHandle === connection.targetHandle,
      );
      if (exists) {
        toast('该连接已存在');
        return;
      }

      // 不允许自连接
      if (connection.source === connection.target) {
        toast('不能连接同一节点');
        return;
      }

      // 创建新边
      const newEdge: OrchestrateEdge = {
        id: `edge-${Date.now()}`,
        source: connection.source,
        target: connection.target,
        sourceHandle: connection.sourceHandle,
        targetHandle: connection.targetHandle,
        type: 'customEdge',
      };

      onEdgesUpdate([...edges, newEdge]);
    },
    [nodes, edges, onEdgesUpdate],
  );

  // ──── 选中处理 ────
  const handleNodeClick = useCallback(
    (_e: React.MouseEvent, node: OrchestrateNode) => {
      setSelectedNodeId(node.id);
    },
    [setSelectedNodeId],
  );

  const handleEdgeClick = useCallback(
    (_e: React.MouseEvent, edge: OrchestrateEdge) => {
      setSelectedEdgeId(edge.id);
    },
    [setSelectedEdgeId],
  );

  const handlePaneClick = useCallback(() => {
    setSelectedNodeId(null);
  }, [setSelectedNodeId]);

  // ──── Delete 键处理 + 复制粘贴 ────
  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      // 测试模式下禁用快捷键操作
      if (testMode) return;

      // 不拦截输入框的按键
      const tag = (document.activeElement?.tagName ?? '').toLowerCase();
      if (tag === 'input' || tag === 'textarea' || tag === 'select') return;
      if (document.activeElement?.getAttribute('contenteditable') === 'true') return;

      // Ctrl+C 复制选中节点
      if ((e.ctrlKey || e.metaKey) && e.key === 'c') {
        if (selectedNodeId) {
          const node = nodes.find((n) => n.id === selectedNodeId);
          if (node) {
            clipboardRef.current = { ...node, id: '', position: { ...node.position } };
            toast('已复制节点');
          }
        }
        e.preventDefault();
        return;
      }

      // Ctrl+V 粘贴节点
      if ((e.ctrlKey || e.metaKey) && e.key === 'v') {
        if (clipboardRef.current) {
          const src = clipboardRef.current;
          const newNode: OrchestrateNode = {
            id: `node-${Date.now()}`,
            type: src.type,
            position: { x: src.position.x + 50, y: src.position.y + 50 },
            data: {
              nodeType: src.data.nodeType,
              config: { ...src.data.config },
              inputs: { ...src.data.inputs },
            },
          };
          onNodesUpdate([...nodes, newNode]);
          setSelectedNodeId(newNode.id);
          toast('已粘贴节点');
        }
        e.preventDefault();
        return;
      }

      if (e.key !== 'Delete' && e.key !== 'Backspace') return;

      // 删除选中连线
      if (useOrchestrateStore.getState().selectedEdgeId) {
        const edgeId = useOrchestrateStore.getState().selectedEdgeId;
        onEdgesUpdate(edges.filter((ed) => ed.id !== edgeId));
        setSelectedEdgeId(null);
        toast('已删除连线');
        e.preventDefault();
        return;
      }

      // 删除选中节点
      if (selectedNodeId) {
        onNodesUpdate(nodes.filter((n) => n.id !== selectedNodeId));
        onEdgesUpdate(
          edges.filter(
            (ed) => ed.source !== selectedNodeId && ed.target !== selectedNodeId,
          ),
        );
        setSelectedNodeId(null);
        toast('已删除节点');
        e.preventDefault();
      }
    },
    [nodes, edges, selectedNodeId, testMode, onNodesUpdate, onEdgesUpdate, setSelectedNodeId, setSelectedEdgeId],
  );

  // ──── Drop 处理 ────
  const handleDropEvent = useCallback(
    (event: React.DragEvent) => {
      const bounds = (event.target as HTMLElement)
        .closest('.react-flow__pane')
        ?.getBoundingClientRect();
      if (!bounds) return;
      const position = reactFlowInstance.screenToFlowPosition({
        x: event.clientX,
        y: event.clientY,
      });
      handleDrop(event, position);
    },
    [handleDrop, reactFlowInstance],
  );

  // ──── 打包子流程回调 ────
  const handlePackComplete = useCallback(
    (newNodes: OrchestrateNode[], newEdges: OrchestrateEdge[]) => {
      onNodesUpdate(newNodes);
      onEdgesUpdate(newEdges);
    },
    [onNodesUpdate, onEdgesUpdate],
  );

  const isEmpty = nodes.length === 0;
  const showPackButton = !testMode && selectedNodeIds.length >= 2;

  return (
    <div className="flow-canvas" onKeyDown={handleKeyDown} tabIndex={0}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={handleConnect}
        onNodeClick={handleNodeClick}
        onEdgeClick={handleEdgeClick}
        onPaneClick={handlePaneClick}
        onDragOver={handleDragOver}
        onDrop={handleDropEvent}
        onSelectionChange={handleSelectionChange}
        nodeTypes={nodeTypes}
        edgeTypes={edgeTypes}
        connectionLineComponent={ConnectionLine}
        deleteKeyCode={null}
        nodesDraggable={!testMode}
        nodesConnectable={!testMode}
        elementsSelectable={!testMode}
        fitView={false}
        defaultViewport={{ x: 0, y: 0, zoom: 1 }}
        minZoom={0.2}
        maxZoom={2}
        snapToGrid
        snapGrid={[10, 10]}
        proOptions={{ hideAttribution: true }}
      >
        <Background color="#e8eef6" gap={20} size={1} />
        <Controls
          position="bottom-right"
          showInteractive={!testMode}
          className="flow-canvas__controls"
        />
        <MiniMap
          position="bottom-left"
          nodeColor={(n) => {
            const data = n.data as NodeInstanceData | undefined;
            if (!data) return '#cbd5e1';
            if (data.nodeType === 'subflowCall') return '#8b5cf6';
            const schema = findSchema(data.nodeType);
            if (!schema) return '#cbd5e1';
            if (schema.outputs.length > 0) {
              return getPortType(schema.outputs[0].dataType).color;
            }
            return '#94a3b8';
          }}
          maskColor="rgba(244, 248, 254, 0.6)"
          style={{ background: 'var(--surface)', border: '1px solid var(--border)' }}
        />
        {isEmpty && <EmptyCanvas />}
      </ReactFlow>

      {/* 浮动打包按钮 */}
      {showPackButton && (
        <div className="flow-canvas__pack-toolbar">
          <button
            className="flow-canvas__pack-btn"
            onClick={() => setShowPackModal(true)}
          >
            <Package size={14} />
            <span>打包为子流程 ({selectedNodeIds.length})</span>
          </button>
        </div>
      )}

      {/* 打包弹窗 */}
      {showPackModal && (
        <SubflowPackModal
          selectedNodeIds={selectedNodeIds}
          allNodes={nodes}
          allEdges={edges}
          onClose={() => setShowPackModal(false)}
          onPackComplete={handlePackComplete}
        />
      )}

      {/* 测试模式标识：将 executingNodeId 传递给 CustomNode 的 data */}
      {testMode && executingNodeId}
    </div>
  );
}

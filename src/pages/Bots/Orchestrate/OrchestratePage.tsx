import { useEffect, useCallback, useRef } from 'react';
import { useParams } from 'react-router-dom';
import { ReactFlowProvider, useNodesState, useEdgesState } from '@xyflow/react';
import OrchestrateHeader from './components/OrchestrateHeader';
import NodePanel from './components/NodePanel';
import FlowCanvas from './components/FlowCanvas';
import NodeInspector from './components/NodeInspector';
import TestPanel from './components/TestPanel';
import { useOrchestrateStore } from './store/orchestrateStore';
import { useWorkflowPersistence } from './hooks/useWorkflowPersistence';
import { useValidation } from './hooks/useValidation';
import { toast } from '../../../utils/toast';
import type { OrchestrateNode, OrchestrateEdge } from './components/FlowCanvas';
import './OrchestratePage.css';

/**
 * 编排页内部组件（必须在 ReactFlowProvider 内部使用 hooks）。
 */
function OrchestratePageInner() {
  const { botId } = useParams<{ botId: string }>();
  const {
    setBotInfo,
    updateLastEdited,
    testMode,
    setTestMode,
    resetDebugSession,
  } = useOrchestrateStore();

  const { loadWorkflow, saveWorkflow, exportWorkflow, getDefaultWorkflow } =
    useWorkflowPersistence();
  const { validate } = useValidation();

  const [nodes, setNodes, onNodesChange] = useNodesState<OrchestrateNode>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<OrchestrateEdge>([]);
  const isDirtyRef = useRef(false);

  // beforeunload 提醒未保存变更
  useEffect(() => {
    function onBeforeUnload(e: BeforeUnloadEvent) {
      if (isDirtyRef.current) {
        e.preventDefault();
        e.returnValue = '';
      }
    }
    window.addEventListener('beforeunload', onBeforeUnload);
    return () => window.removeEventListener('beforeunload', onBeforeUnload);
  }, []);

  // 标记脏状态（任意 nodes/edges 变更即标记）
  useEffect(() => {
    isDirtyRef.current = true;
  }, [nodes, edges]);

  // 初始化：加载工作流或默认工作流
  useEffect(() => {
    if (!botId) return;

    const id = botId;
    setBotInfo(id, '');

    async function init() {
      const persisted = await loadWorkflow(id);
      if (persisted) {
        // 恢复持久化数据
      const restoredNodes: OrchestrateNode[] = persisted.nodes.map((n) => {
        // 兼容旧数据：后端早期将业务类型存在 node.type，data 里没有 nodeType
        const nodeType = n.data.nodeType || n.type || 'unknown';
        return {
          id: n.id,
          // 统一使用 customNode 渲染组件，data.nodeType 保留具体业务类型
          type: 'customNode',
          position: n.position,
          data: {
            nodeType,
            config: { ...n.data.config },
            inputs: { ...n.data.inputs },
            ...(n.data.subflowId ? { subflowId: n.data.subflowId } : {}),
            ...(n.data.subflowName ? { subflowName: n.data.subflowName } : {}),
            ...(n.data.subflowDesc ? { subflowDesc: n.data.subflowDesc } : {}),
            ...(n.data.inputPortsCount !== undefined ? { inputPortsCount: n.data.inputPortsCount } : {}),
            ...(n.data.outputPortsCount !== undefined ? { outputPortsCount: n.data.outputPortsCount } : {}),
          },
        };
      });
        const restoredEdges: OrchestrateEdge[] = persisted.edges.map((e) => ({
          id: e.id,
          source: e.source,
          target: e.target,
          sourceHandle: e.sourceHandle,
          targetHandle: e.targetHandle,
          type: 'customEdge',
        }));
        setNodes(restoredNodes);
        setEdges(restoredEdges);

        if (persisted.lastEdited) {
          useOrchestrateStore.getState().lastEdited = persisted.lastEdited;
        }
      } else {
        const defaultWf = getDefaultWorkflow(id);
        const defaultNodes: OrchestrateNode[] = defaultWf.nodes.map((n) => ({
          id: n.id,
          type: n.type,
          position: n.position,
          data: {
            nodeType: n.data.nodeType,
            config: { ...n.data.config },
            inputs: { ...n.data.inputs },
          },
        }));
        const defaultEdges: OrchestrateEdge[] = defaultWf.edges.map((e) => ({
          id: e.id,
          source: e.source,
          target: e.target,
          sourceHandle: e.sourceHandle,
          targetHandle: e.targetHandle,
          type: 'customEdge',
        }));
        setNodes(defaultNodes);
        setEdges(defaultEdges);
        updateLastEdited();
      }
    }

    init();
  }, [botId]); // eslint-disable-line react-hooks/exhaustive-deps

  // 保存
  const handleSave = useCallback(async () => {
    if (!botId) return;

    const result = validate(nodes, edges);
    if (!result.valid) {
      const firstError = result.errors[0];
      toast(firstError.message);
      return;
    }

    const ok = await saveWorkflow(botId, nodes, edges);
    if (ok) {
      isDirtyRef.current = false;
      toast('已保存');
    } else {
      toast('保存失败，请重试');
    }
  }, [botId, nodes, edges, validate, saveWorkflow]);

  // 导出
  const handleExport = useCallback(() => {
    if (!botId) return;
    const botName = useOrchestrateStore.getState().botName || botId;
    exportWorkflow(botId, botName, nodes, edges);
    toast('已导出工作流 JSON');
  }, [botId, nodes, edges, exportWorkflow]);

  // 进入测试模式
  const handleEnterTest = useCallback(() => {
    const result = validate(nodes, edges);
    if (!result.valid) {
      const firstError = result.errors[0];
      toast(firstError.message);
      return;
    }

    // 自动保存
    if (botId) {
      saveWorkflow(botId, nodes, edges);
    }
    isDirtyRef.current = false;

    setTestMode(true);
    resetDebugSession();
  }, [nodes, edges, validate, botId, saveWorkflow, setTestMode, resetDebugSession]);

  // 退出测试模式
  const handleExitTest = useCallback(() => {
    setTestMode(false);
    resetDebugSession();
  }, [setTestMode, resetDebugSession]);

  // 更新节点 data
  const handleUpdateNodeData = useCallback(
    (nodeId: string, config: Record<string, string | number>) => {
      setNodes((nds) =>
        nds.map((n) =>
          n.id === nodeId
            ? { ...n, data: { ...n.data, config: { ...n.data.config, ...config } } }
            : n,
        ),
      );
    },
    [setNodes],
  );

  return (
    <div className={`orchestrate-page${testMode ? ' orchestrate-page--test-mode' : ''}`}>
      <OrchestrateHeader
        onSave={handleSave}
        onExport={handleExport}
        onEnterTest={handleEnterTest}
        onExitTest={handleExitTest}
      />
      <div className="orchestrate-page__body">
        <NodePanel />
        <FlowCanvas
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onNodesUpdate={setNodes}
          onEdgesUpdate={setEdges}
        />
        <NodeInspector
          nodes={nodes}
          onUpdateNodeData={handleUpdateNodeData}
        />
      </div>
      {testMode && (
        <TestPanel nodes={nodes} edges={edges} />
      )}
    </div>
  );
}

/**
 * 编排页主组件。
 * 三栏布局：NodePanel | FlowCanvas | NodeInspector。
 * 测试模式下底部显示 TestPanel。
 */
export function OrchestratePage() {
  return (
    <ReactFlowProvider>
      <OrchestratePageInner />
    </ReactFlowProvider>
  );
}

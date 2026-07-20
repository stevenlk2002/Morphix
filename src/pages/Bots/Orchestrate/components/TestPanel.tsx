import { useCallback, useRef } from 'react';
import { useOrchestrateStore } from '../store/orchestrateStore';
import TestPanelInput from './TestPanelInput';
import TestPanelTrace from './TestPanelTrace';
import type { OrchestrateNode, OrchestrateEdge } from './FlowCanvas';
import './TestPanel.css';

interface TestPanelProps {
  nodes: OrchestrateNode[];
  edges: OrchestrateEdge[];
}

/**
 * 底部测试面板主容器。
 * 默认 320px 高度，顶部拖拽手柄可调整（200~600px）。
 * 左侧输入区 + 右侧执行时序列表。
 */
export default function TestPanel({ nodes, edges }: TestPanelProps) {
  const {
    testPanelHeight,
    setTestPanelHeight,
    resetDebugSession,
  } = useOrchestrateStore();

  const resizeRef = useRef<{ startY: number; startH: number } | null>(null);
  const panelRef = useRef<HTMLDivElement>(null);

  // 拖拽调整高度
  const handleResizeStart = useCallback(
    (e: React.MouseEvent) => {
      e.preventDefault();
      resizeRef.current = { startY: e.clientY, startH: testPanelHeight };

      function onMove(ev: MouseEvent) {
        if (!resizeRef.current) return;
        const deltaY = resizeRef.current.startY - ev.clientY;
        let h = resizeRef.current.startH + deltaY;
        if (h < 200) h = 200;
        if (h > 600) h = 600;
        setTestPanelHeight(h);
      }

      function onUp() {
        resizeRef.current = null;
        document.removeEventListener('mousemove', onMove);
        document.removeEventListener('mouseup', onUp);
      }

      document.addEventListener('mousemove', onMove);
      document.addEventListener('mouseup', onUp);
    },
    [testPanelHeight, setTestPanelHeight],
  );

  // 清空上下文
  const handleClear = useCallback(() => {
    resetDebugSession();
  }, [resetDebugSession]);

  return (
    <div
      ref={panelRef}
      className="test-panel"
      style={{ height: testPanelHeight }}
    >
      {/* 拖拽手柄 */}
      <div
        className="test-panel__handle"
        onMouseDown={handleResizeStart}
      >
        <div className="test-panel__handle-bar" />
        <span className="test-panel__handle-label">调试控制台</span>
        <button
          className="test-panel__clear-btn"
          onClick={handleClear}
        >
          清空
        </button>
      </div>

      {/* 面板内容 */}
      <div className="test-panel__body">
        <div className="test-panel__input">
          <TestPanelInput nodes={nodes} edges={edges} />
        </div>
        <div className="test-panel__trace">
          <TestPanelTrace />
        </div>
      </div>
    </div>
  );
}

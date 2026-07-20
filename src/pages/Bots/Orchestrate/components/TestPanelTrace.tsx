import { useCallback, useState } from 'react';
import { CheckCircle, XCircle, AlertTriangle, Loader, ChevronDown, ChevronRight } from 'lucide-react';
import { useOrchestrateStore } from '../store/orchestrateStore';
import type { NodeExecutionRecord } from '../types/orchestrate';
import './TestPanelTrace.css';

/** 状态图标映射 */
function StatusIcon({ status }: { status: NodeExecutionRecord['status'] }) {
  const size = 14;
  switch (status) {
    case 'success':
      return <CheckCircle size={size} className="test-trace__icon test-trace__icon--success" />;
    case 'error':
      return <XCircle size={size} className="test-trace__icon test-trace__icon--error" />;
    case 'warning':
      return <AlertTriangle size={size} className="test-trace__icon test-trace__icon--warning" />;
    case 'running':
      return <Loader size={size} className="test-trace__icon test-trace__icon--running" />;
    default:
      return <span className="test-trace__icon test-trace__icon--pending">○</span>;
  }
}

/** 格式化 JSON 摘要 */
function formatSummary(obj: Record<string, unknown>): string {
  const entries = Object.entries(obj).slice(0, 3);
  if (entries.length === 0) return '{}';
  return entries
    .map(([k, v]) => {
      const vs = typeof v === 'string'
        ? (v.length > 20 ? v.substring(0, 18) + '…' : v)
        : JSON.stringify(v);
      return `${k}: ${vs}`;
    })
    .join(', ');
}

/** 单条执行记录行（可展开） */
function TraceRow({ record, index }: { record: NodeExecutionRecord; index: number }) {
  const [expanded, setExpanded] = useState(false);

  const toggle = useCallback(() => {
    setExpanded((prev) => !prev);
  }, []);

  return (
    <div className="test-trace__row-wrapper">
      <div
        className={`test-trace__row test-trace__row--${record.status}`}
        onClick={toggle}
      >
        <span className="test-trace__row-index">{index + 1}</span>
        <StatusIcon status={record.status} />
        <span className="test-trace__row-name">{record.nodeName}</span>
        <span className="test-trace__row-summary">
          {formatSummary(record.outputs)}
        </span>
        <span className="test-trace__row-duration">
          {record.durationMs}ms
        </span>
        {expanded ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
      </div>

      {/* 展开详情 */}
      {expanded && (
        <div className="test-trace__detail">
          <div className="test-trace__detail-section">
            <h5 className="test-trace__detail-title">输入值</h5>
            <pre className="test-trace__detail-json">
              {JSON.stringify(record.inputs, null, 2)}
            </pre>
          </div>

          <div className="test-trace__detail-section">
            <h5 className="test-trace__detail-title">输出值</h5>
            <pre className="test-trace__detail-json">
              {JSON.stringify(record.outputs, null, 2)}
            </pre>
          </div>

          {record.mockNote && (
            <div className="test-trace__detail-note">{record.mockNote}</div>
          )}

          {record.error && (
            <div className="test-trace__detail-error">{record.error}</div>
          )}
        </div>
      )}
    </div>
  );
}

/**
 * 执行时序列表。
 * 显示逐节点执行状态、输入/输出摘要，点击展开详情。
 */
export default function TestPanelTrace() {
  const debugSession = useOrchestrateStore((s) => s.debugSession);

  // 空状态
  if (!debugSession || debugSession.trace.length === 0) {
    return (
      <div className="test-trace test-trace--empty">
        <div className="test-trace__empty">
          <p className="test-trace__empty-text">尚未执行，请发送测试消息</p>
        </div>
      </div>
    );
  }

  const { trace, totalDurationMs, userMessage } = debugSession;

  return (
    <div className="test-trace">
      {/* 摘要信息 */}
      <div className="test-trace__summary">
        <span className="test-trace__summary-msg">
          消息: "{userMessage.length > 20 ? userMessage.substring(0, 18) + '…' : userMessage}"
        </span>
        <span className="test-trace__summary-meta">
          {trace.length} 节点 · {totalDurationMs}ms
        </span>
      </div>

      {/* 执行列表 */}
      <div className="test-trace__list">
        {trace.map((record, idx) => (
          <TraceRow key={record.nodeId} record={record} index={idx} />
        ))}
      </div>
    </div>
  );
}

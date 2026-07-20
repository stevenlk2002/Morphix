import { useState, useCallback, useRef } from 'react';
import { Send } from 'lucide-react';
import { useOrchestrateStore } from '../store/orchestrateStore';
import { useMockExecution } from '../hooks/useMockExecution';
import { toast } from '../../../../utils/toast';
import type { OrchestrateNode, OrchestrateEdge } from './FlowCanvas';

interface TestPanelInputProps {
  nodes: OrchestrateNode[];
  edges: OrchestrateEdge[];
}

/**
 * 测试面板消息输入区。
 * 输入框 + 发送按钮 + 快捷预设消息。
 */
export default function TestPanelInput({ nodes, edges }: TestPanelInputProps) {
  const { quickMessages, setDebugSession } = useOrchestrateStore();
  const { mockExecute } = useMockExecution();

  const [message, setMessage] = useState('');
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const handleSend = useCallback(() => {
    const trimmed = message.trim();
    if (!trimmed) {
      toast('请输入测试消息');
      return;
    }

    if (nodes.length === 0) {
      toast('画布为空，请先添加节点');
      return;
    }

    const session = mockExecute(nodes, edges, trimmed);
    setDebugSession(session);
  }, [message, nodes, edges, mockExecute, setDebugSession]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        handleSend();
      }
    },
    [handleSend],
  );

  const handleQuickMessage = useCallback((msg: string) => {
    setMessage(msg);
    inputRef.current?.focus();
  }, []);

  return (
    <div className="test-input">
      {/* 输入区域 */}
      <div className="test-input__area">
        <textarea
          ref={inputRef}
          className="test-input__textarea"
          placeholder="输入测试消息，Enter 发送 / Shift+Enter 换行"
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          onKeyDown={handleKeyDown}
          rows={3}
        />
        <button
          className="test-input__send-btn"
          onClick={handleSend}
          disabled={!message.trim()}
          title="发送 (Enter)"
        >
          <Send size={16} />
        </button>
      </div>

      {/* 快捷预设 */}
      <div className="test-input__quick">
        <span className="test-input__quick-label">快捷消息：</span>
        <div className="test-input__quick-list">
          {quickMessages.map((msg, idx) => (
            <button
              key={idx}
              className="test-input__quick-item"
              onClick={() => handleQuickMessage(msg)}
            >
              {msg}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

import { Bot, Download, Save, Play, Square } from 'lucide-react';
import Button from '../../../../components/common/Button';
import { useOrchestrateStore } from '../store/orchestrateStore';
import './OrchestrateHeader.css';

interface OrchestrateHeaderProps {
  onSave: () => void;
  onExport: () => void;
  onEnterTest: () => void;
  onExitTest: () => void;
}

/**
 * 编排台顶部 Header。
 * 显示：返回按钮 + Bot 头像/名称 + 最后编辑时间 + 测试/退出测试 + 导出 + 保存按钮。
 * 测试模式下显示橙色标识和 [退出测试] 按钮。
 */
export default function OrchestrateHeader({
  onSave,
  onExport,
  onEnterTest,
  onExitTest,
}: OrchestrateHeaderProps) {
  const { botName, lastEdited, testMode } = useOrchestrateStore();

  function formatTime(iso: string): string {
    if (!iso) return '--';
    try {
      const d = new Date(iso);
      const pad = (n: number) => String(n).padStart(2, '0');
      return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
    } catch {
      return iso;
    }
  }

  return (
    <header className={`orchestrate-header${testMode ? ' orchestrate-header--test-mode' : ''}`}>
      <div className="orchestrate-header__left">
        {/* 测试模式标识 */}
        {testMode && (
          <span className="orchestrate-header__test-badge">测试模式</span>
        )}

        <div className="orchestrate-header__bot-info">
          <div className="orchestrate-header__bot-avatar">
            <Bot size={20} />
          </div>
          <div className="orchestrate-header__bot-meta">
            <h2 className="orchestrate-header__bot-name">{botName || '未命名'}</h2>
            {lastEdited && (
              <span className="orchestrate-header__bot-time">
                编辑于 {formatTime(lastEdited)}
              </span>
            )}
          </div>
        </div>
      </div>

      <div className="orchestrate-header__right">
        {testMode ? (
          <Button
            variant="secondary"
            size="sm"
            icon={<Square size={15} />}
            onClick={onExitTest}
            style={{ borderColor: '#f59e0b', color: '#f59e0b' }}
          >
            退出测试
          </Button>
        ) : (
          <>
            <Button
              variant="secondary"
              size="sm"
              icon={<Play size={15} />}
              onClick={onEnterTest}
            >
              测试
            </Button>
            <Button
              variant="secondary"
              size="sm"
              icon={<Download size={15} />}
              onClick={onExport}
            >
              导出
            </Button>
            <Button
              variant="primary"
              size="sm"
              icon={<Save size={15} />}
              onClick={onSave}
            >
              保存
            </Button>
          </>
        )}
      </div>
    </header>
  );
}

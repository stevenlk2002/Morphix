import { Workflow } from 'lucide-react';
import './EmptyCanvas.css';

/**
 * 空画布引导组件。
 * 当画布无节点时显示，引导用户从左侧面板拖拽节点。
 */
export default function EmptyCanvas() {
  return (
    <div className="empty-canvas">
      <div className="empty-canvas__icon">
        <Workflow size={48} />
      </div>
      <p className="empty-canvas__title">开始编排工作流</p>
      <p className="empty-canvas__hint">
        从左侧节点面板拖拽节点到此处开始编排
      </p>
    </div>
  );
}

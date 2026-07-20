import { useState } from 'react';
import {
  BaseEdge,
  getBezierPath,
  type EdgeProps,
  type Edge,
} from '@xyflow/react';
import './CustomEdge.css';

/**
 * React Flow 自定义边。
 * - 贝塞尔曲线渲染
 * - hover 时加粗 + 显示 × 删除按钮
 * - 选中时描边红色加粗
 */
export default function CustomEdge({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  selected,
  markerEnd,
}: EdgeProps<Edge>) {
  const [hover, setHover] = useState(false);

  const [edgePath] = getBezierPath({
    sourceX,
    sourceY,
    targetX,
    targetY,
  });

  // 中点位置（删除按钮）
  const midX = (sourceX + targetX) / 2;
  const midY = (sourceY + targetY) / 2;

  const isHighlighted = hover || selected;

  return (
    <g
      className={`custom-edge${selected ? ' custom-edge--selected' : ''}${hover ? ' custom-edge--hover' : ''}`}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
    >
      {/* 加宽透明点击区域 */}
      <path
        d={edgePath}
        fill="none"
        stroke="transparent"
        strokeWidth={20}
        className="custom-edge__hitarea"
      />
      {/* 可见连线 */}
      <BaseEdge
        id={id}
        path={edgePath}
        markerEnd={markerEnd}
        style={{
          stroke: isHighlighted ? '#ef4444' : '#94a3b8',
          strokeWidth: isHighlighted ? 2.5 : 1.5,
          transition: 'stroke 150ms ease, stroke-width 150ms ease',
        }}
      />
      {/* Hover 删除按钮（透明大圈扩大点击范围） */}
      {hover && (
        <g
          className="custom-edge__delete"
          transform={`translate(${midX}, ${midY})`}
          onClick={(e) => {
            e.stopPropagation();
            const event = new CustomEvent('morphix-edge-delete', {
              detail: { edgeId: id },
            });
            window.dispatchEvent(event);
          }}
          style={{ cursor: 'pointer' }}
        >
          {/* 透明点击热区：半径 32px（64px 直径），随手可点中 */}
          <circle r="32" fill="transparent" />
          {/* 可视 × 按钮（略放大） */}
          <circle r="12" fill="var(--surface)" stroke="#ef4444" strokeWidth="1.5" />
          <line x1="-5" y1="-5" x2="5" y2="5" stroke="#ef4444" strokeWidth="2" strokeLinecap="round" />
          <line x1="5" y1="-5" x2="-5" y2="5" stroke="#ef4444" strokeWidth="2" strokeLinecap="round" />
        </g>
      )}
    </g>
  );
}

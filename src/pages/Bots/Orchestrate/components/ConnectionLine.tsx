import { getBezierPath, type ConnectionLineComponentProps } from '@xyflow/react';
import { canConnectTypes } from '../data/portTypes';

/**
 * 拖拽连线时的实时预览组件。
 * - 合法连线目标 → 蓝色路径
 * - 不合法连线目标 → 红色路径
 */
export default function ConnectionLine({
  fromX,
  fromY,
  toX,
  toY,
  fromHandle,
  toHandle,
}: ConnectionLineComponentProps) {
  // 从 fromHandle 读取源端口类型
  const sourceType: string =
    (fromHandle as { type?: string } | null)?.type ?? 'any';

  // 尝试从 toHandle 读取目标端口类型
  const targetType: string =
    (toHandle as { type?: string } | null)?.type ?? '';

  const isValid = targetType ? canConnectTypes(sourceType, targetType) : true;
  const strokeColor = isValid ? '#3b82f6' : '#ef4444';

  const [edgePath] = getBezierPath({
    sourceX: fromX,
    sourceY: fromY,
    targetX: toX,
    targetY: toY,
  });

  return (
    <g>
      <path
        fill="none"
        stroke={strokeColor}
        strokeWidth={2}
        strokeDasharray="5 5"
        d={edgePath}
      />
      <circle
        cx={toX}
        cy={toY}
        r={5}
        fill={strokeColor}
        fillOpacity={0.5}
      />
    </g>
  );
}

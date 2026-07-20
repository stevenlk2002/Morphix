import type { PortDataType, PortTypeMap } from '../types/orchestrate';

/** 7 种端口类型颜色表（与原型完全一致） */
export const PORT_TYPES: PortTypeMap = {
  string: { label: '字符串', color: '#3b82f6', desc: '字符串类型' },
  number: { label: '数字', color: '#f97316', desc: '数字类型' },
  boolean: { label: '布尔', color: '#22c55e', desc: '布尔值' },
  chatHistory: { label: '聊天记录', color: '#06b6d4', desc: '专属类型，传递聊天记录' },
  knowledgeRef: { label: '引用内容', color: '#ef4444', desc: '专属类型，传递知识库查询结果' },
  any: { label: '任意', color: '#eab308', desc: '任意类型' },
  property: { label: '属性', color: '#8b5cf6', desc: '专属类型' },
};

/** 获取端口类型信息，未知类型回退到 any */
export function getPortType(dt: string): { label: string; color: string; desc: string } {
  return PORT_TYPES[dt as PortDataType] ?? PORT_TYPES.any;
}

/**
 * 连线类型兼容性校验。
 * - 任意一侧为 'any' → 允许连接
 * - 两侧类型完全一致 → 允许连接
 * - 否则 → 不允许连接
 */
export function canConnectTypes(sourceType: string, targetType: string): boolean {
  if (sourceType === 'any' || targetType === 'any') return true;
  return sourceType === targetType;
}

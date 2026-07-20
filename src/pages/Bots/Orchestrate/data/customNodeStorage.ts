import type { CustomNodeDef } from '../types/orchestrate';

const STORAGE_KEY = 'morphix_custom_nodes';

/**
 * 自定义节点 localStorage 持久化层。
 * 结构：morphix_custom_nodes → CustomNodeDef[]
 */

/** 读取所有自定义节点 */
export function loadCustomNodes(): CustomNodeDef[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed as CustomNodeDef[];
  } catch {
    return [];
  }
}

/** 保存自定义节点列表 */
export function saveCustomNodes(nodes: CustomNodeDef[]): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(nodes));
  } catch {
    // localStorage 满或不可用，静默失败
  }
}

/** 添加单个自定义节点 */
export function addCustomNode(node: CustomNodeDef): void {
  const nodes = loadCustomNodes();
  nodes.push(node);
  saveCustomNodes(nodes);
}

/** 删除自定义节点 */
export function deleteCustomNode(id: string): void {
  const nodes = loadCustomNodes().filter((n) => n.id !== id);
  saveCustomNodes(nodes);
}

/** 更新单个自定义节点 */
export function updateCustomNode(id: string, updates: Partial<CustomNodeDef>): void {
  const nodes = loadCustomNodes();
  const idx = nodes.findIndex((n) => n.id === id);
  if (idx === -1) return;
  nodes[idx] = { ...nodes[idx], ...updates };
  saveCustomNodes(nodes);
}

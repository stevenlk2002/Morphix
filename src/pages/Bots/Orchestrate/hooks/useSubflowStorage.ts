import { useCallback } from 'react';
import type { SubflowPersisted } from '../types/orchestrate';
import { toast } from '../../../../utils/toast';

const SUBFLOW_KEY_PREFIX = 'morphix_subflow_';
const SUBFLOW_INDEX_KEY = 'morphix_subflow_index';

/** 生成子流程 ID：格式 subflow-{timestamp36}-{random4} */
export function generateSubflowId(): string {
  const ts = Date.now().toString(36);
  const rand = Math.random().toString(36).substring(2, 6);
  return `subflow-${ts}-${rand}`;
}

/** 读取子流程索引 */
function readIndex(): string[] {
  try {
    const raw = localStorage.getItem(SUBFLOW_INDEX_KEY);
    if (!raw) return [];
    const parsed: unknown = JSON.parse(raw);
    if (Array.isArray(parsed) && parsed.every((v) => typeof v === 'string')) {
      return parsed as string[];
    }
    return [];
  } catch {
    return [];
  }
}

/** 写入子流程索引 */
function writeIndex(index: string[]): void {
  try {
    localStorage.setItem(SUBFLOW_INDEX_KEY, JSON.stringify(index));
  } catch (e) {
    toast('子流程索引保存失败');
    console.error('writeIndex error:', e);
  }
}

/**
 * 子流程 localStorage CRUD hook。
 * 管理 morphix_subflow_{id} 和 morphix_subflow_index 两套 key。
 */
export function useSubflowStorage() {
  /** 加载单个子流程 */
  const loadSubflow = useCallback((id: string): SubflowPersisted | null => {
    try {
      const raw = localStorage.getItem(`${SUBFLOW_KEY_PREFIX}${id}`);
      if (!raw) return null;
      const data: SubflowPersisted = JSON.parse(raw);
      return data;
    } catch (e) {
      console.error('loadSubflow error:', e);
      return null;
    }
  }, []);

  /** 保存子流程（新增或更新） */
  const saveSubflow = useCallback((data: SubflowPersisted): void => {
    try {
      localStorage.setItem(`${SUBFLOW_KEY_PREFIX}${data.id}`, JSON.stringify(data));

      const index = readIndex();
      if (!index.includes(data.id)) {
        index.push(data.id);
        writeIndex(index);
      }
    } catch (e) {
      toast('子流程保存失败');
      console.error('saveSubflow error:', e);
    }
  }, []);

  /** 删除子流程 */
  const deleteSubflow = useCallback((id: string): void => {
    try {
      localStorage.removeItem(`${SUBFLOW_KEY_PREFIX}${id}`);

      const index = readIndex().filter((subflowId) => subflowId !== id);
      writeIndex(index);
    } catch (e) {
      toast('子流程删除失败');
      console.error('deleteSubflow error:', e);
    }
  }, []);

  /** 列出所有已保存子流程 */
  const listSubflows = useCallback((): SubflowPersisted[] => {
    try {
      const index = readIndex();
      const result: SubflowPersisted[] = [];
      for (const id of index) {
        const sf = loadSubflow(id);
        if (sf) result.push(sf);
      }
      return result;
    } catch (e) {
      console.error('listSubflows error:', e);
      return [];
    }
  }, [loadSubflow]);

  /** 获取子流程索引 ID 列表 */
  const getSubflowIndex = useCallback((): string[] => {
    return readIndex();
  }, []);

  return { loadSubflow, saveSubflow, deleteSubflow, listSubflows, getSubflowIndex };
}

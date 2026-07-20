import { describe, it, expect, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import {
  useSubflowStorage,
  generateSubflowId,
} from '../hooks/useSubflowStorage';
import type { SubflowPersisted } from '../types/orchestrate';

/** 构造测试用 SubflowPersisted */
function makeSubflow(id: string, name: string = 'Test Subflow'): SubflowPersisted {
  return {
    id,
    name,
    desc: 'A test subflow',
    interface: {
      inputs: [
        { key: 'question', varName: 'userChatInput', dataType: 'any', direction: 'input', label: 'userInput · 用户问题' },
      ],
      outputs: [
        { key: 'aiReply', varName: 'aiReply', dataType: 'any', direction: 'output', label: 'aiChat · AI回复内容' },
      ],
    },
    nodes: [
      {
        id: 'sf-node-1',
        type: 'customNode',
        position: { x: 0, y: 0 },
        data: { nodeType: 'userInput', config: {}, inputs: {} },
      },
      {
        id: 'sf-node-2',
        type: 'customNode',
        position: { x: 300, y: 0 },
        data: { nodeType: 'aiChat', config: { model: 'DeepSeek' }, inputs: {} },
      },
    ],
    edges: [
      {
        id: 'sf-edge-1',
        source: 'sf-node-1',
        target: 'sf-node-2',
        sourceHandle: 'userChatInput',
        targetHandle: 'question',
      },
    ],
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
    version: 1,
  };
}

describe('generateSubflowId', () => {
  it('生成以 subflow- 开头的 ID', () => {
    const id = generateSubflowId();
    expect(id.startsWith('subflow-')).toBe(true);
  });

  it('每次生成不同的 ID', () => {
    const ids = new Set<string>();
    for (let i = 0; i < 100; i++) {
      ids.add(generateSubflowId());
    }
    expect(ids.size).toBe(100);
  });

  it('ID 长度合理（>= 15）', () => {
    const id = generateSubflowId();
    expect(id.length).toBeGreaterThanOrEqual(15);
  });
});

describe('useSubflowStorage', () => {
  const SUBFLOW_INDEX_KEY = 'morphix_subflow_index';
  const KEY_PREFIX = 'morphix_subflow_';

  beforeEach(() => {
    localStorage.clear();
  });

  // ──── saveSubflow + loadSubflow ────

  describe('saveSubflow → loadSubflow 往返', () => {
    it('save 后 load 可完整恢复子流程数据', () => {
      const { result } = renderHook(() => useSubflowStorage());
      const sf = makeSubflow('sf-test-001', 'My Subflow');

      act(() => {
        result.current.saveSubflow(sf);
      });

      const loaded = result.current.loadSubflow('sf-test-001');
      expect(loaded).not.toBeNull();
      expect(loaded!.id).toBe('sf-test-001');
      expect(loaded!.name).toBe('My Subflow');
      expect(loaded!.desc).toBe('A test subflow');
      expect(loaded!.nodes).toHaveLength(2);
      expect(loaded!.edges).toHaveLength(1);
      expect(loaded!.interface.inputs).toHaveLength(1);
      expect(loaded!.interface.outputs).toHaveLength(1);
      expect(loaded!.version).toBe(1);
    });

    it('save 后 index 包含该子流程 ID', () => {
      const { result } = renderHook(() => useSubflowStorage());
      const sf = makeSubflow('sf-test-002');

      act(() => {
        result.current.saveSubflow(sf);
      });

      const index = result.current.getSubflowIndex();
      expect(index).toContain('sf-test-002');
    });

    it('localStorage key 格式为 morphix_subflow_{id}', () => {
      const { result } = renderHook(() => useSubflowStorage());
      const sf = makeSubflow('sf-fmt-001');

      act(() => {
        result.current.saveSubflow(sf);
      });

      const raw = localStorage.getItem(`${KEY_PREFIX}sf-fmt-001`);
      expect(raw).not.toBeNull();
      const parsed = JSON.parse(raw!);
      expect(parsed.id).toBe('sf-fmt-001');
      expect(parsed.name).toBe('Test Subflow');
    });

    it('索引 key 格式为 morphix_subflow_index', () => {
      const { result } = renderHook(() => useSubflowStorage());
      const sf = makeSubflow('sf-idx-001');

      act(() => {
        result.current.saveSubflow(sf);
      });

      const rawIndex = localStorage.getItem(SUBFLOW_INDEX_KEY);
      expect(rawIndex).not.toBeNull();
      const parsedIndex = JSON.parse(rawIndex!);
      expect(parsedIndex).toContain('sf-idx-001');
    });

    it('不存在的子流程 load 返回 null', () => {
      const { result } = renderHook(() => useSubflowStorage());
      const loaded = result.current.loadSubflow('nonexistent-id');
      expect(loaded).toBeNull();
    });
  });

  // ──── 批量 list ────

  describe('listSubflows', () => {
    it('空存储时返回空数组', () => {
      const { result } = renderHook(() => useSubflowStorage());
      const list = result.current.listSubflows();
      expect(list).toEqual([]);
    });

    it('保存多个子流程后 list 返回全部', () => {
      const { result } = renderHook(() => useSubflowStorage());

      act(() => {
        result.current.saveSubflow(makeSubflow('sf-list-a', 'A'));
        result.current.saveSubflow(makeSubflow('sf-list-b', 'B'));
        result.current.saveSubflow(makeSubflow('sf-list-c', 'C'));
      });

      const list = result.current.listSubflows();
      expect(list).toHaveLength(3);
      const names = list.map((s) => s.name).sort();
      expect(names).toEqual(['A', 'B', 'C']);
    });

    it('getSubflowIndex 返回所有已保存子流程的 ID 列表', () => {
      const { result } = renderHook(() => useSubflowStorage());

      act(() => {
        result.current.saveSubflow(makeSubflow('sf-ga', 'GA'));
        result.current.saveSubflow(makeSubflow('sf-gb', 'GB'));
      });

      const index = result.current.getSubflowIndex();
      expect(index).toHaveLength(2);
      expect(index).toContain('sf-ga');
      expect(index).toContain('sf-gb');
    });
  });

  // ──── 重复保存（index 去重）────

  describe('重复保存去重', () => {
    it('同一 ID 重复保存不会导致 index 重复', () => {
      const { result } = renderHook(() => useSubflowStorage());
      const sf = makeSubflow('sf-dup', 'Dup');

      act(() => {
        result.current.saveSubflow(sf);
        result.current.saveSubflow(sf);
        result.current.saveSubflow(sf);
      });

      const index = result.current.getSubflowIndex();
      expect(index).toHaveLength(1);
      expect(index[0]).toBe('sf-dup');
    });

    it('重复保存会更新子流程数据', () => {
      const { result } = renderHook(() => useSubflowStorage());
      const sf1 = makeSubflow('sf-update', 'Original');
      const sf2 = makeSubflow('sf-update', 'Updated');
      sf2.desc = 'Updated description';
      sf2.version = 2;

      act(() => {
        result.current.saveSubflow(sf1);
        result.current.saveSubflow(sf2);
      });

      const loaded = result.current.loadSubflow('sf-update');
      expect(loaded!.name).toBe('Updated');
      expect(loaded!.desc).toBe('Updated description');
      expect(loaded!.version).toBe(2);
    });
  });

  // ──── deleteSubflow ────

  describe('deleteSubflow', () => {
    it('删除后 load 返回 null', () => {
      const { result } = renderHook(() => useSubflowStorage());
      const sf = makeSubflow('sf-del-1');

      act(() => {
        result.current.saveSubflow(sf);
        result.current.deleteSubflow('sf-del-1');
      });

      const loaded = result.current.loadSubflow('sf-del-1');
      expect(loaded).toBeNull();
    });

    it('删除后索引中不再包含该 ID', () => {
      const { result } = renderHook(() => useSubflowStorage());

      act(() => {
        result.current.saveSubflow(makeSubflow('sf-keep'));
        result.current.saveSubflow(makeSubflow('sf-remove'));
      });

      act(() => {
        result.current.deleteSubflow('sf-remove');
      });

      const index = result.current.getSubflowIndex();
      expect(index).toHaveLength(1);
      expect(index).toContain('sf-keep');
      expect(index).not.toContain('sf-remove');
    });

    it('删除后 list 中不包含该子流程', () => {
      const { result } = renderHook(() => useSubflowStorage());

      act(() => {
        result.current.saveSubflow(makeSubflow('sf-lk'));
        result.current.saveSubflow(makeSubflow('sf-lr'));
      });

      act(() => {
        result.current.deleteSubflow('sf-lr');
      });

      const list = result.current.listSubflows();
      expect(list).toHaveLength(1);
      expect(list[0].id).toBe('sf-lk');
    });

    it('删除不存在的子流程不会报错', () => {
      const { result } = renderHook(() => useSubflowStorage());

      expect(() => {
        act(() => {
          result.current.deleteSubflow('never-exists');
        });
      }).not.toThrow();
    });
  });

  // ──── 容错处理 ────

  describe('容错处理', () => {
    it('损坏的 JSON 数据 load 返回 null', () => {
      localStorage.setItem(`${KEY_PREFIX}corrupt`, '{broken json!!!');

      const { result } = renderHook(() => useSubflowStorage());
      const loaded = result.current.loadSubflow('corrupt');
      expect(loaded).toBeNull();
    });

    it('损坏的 index JSON 返回空数组且不崩溃', () => {
      localStorage.setItem(SUBFLOW_INDEX_KEY, 'not-valid-json}');

      const { result } = renderHook(() => useSubflowStorage());
      const index = result.current.getSubflowIndex();
      expect(index).toEqual([]);

      // list 也不崩溃
      const list = result.current.listSubflows();
      expect(list).toEqual([]);
    });

    it('index 为非数组类型时返回空数组', () => {
      localStorage.setItem(SUBFLOW_INDEX_KEY, JSON.stringify({ not: 'array' }));

      const { result } = renderHook(() => useSubflowStorage());
      const index = result.current.getSubflowIndex();
      expect(index).toEqual([]);
    });

    it('index 中包含非字符串元素时返回空数组', () => {
      localStorage.setItem(SUBFLOW_INDEX_KEY, JSON.stringify(['a', 123, 'b']));

      const { result } = renderHook(() => useSubflowStorage());
      const index = result.current.getSubflowIndex();
      expect(index).toEqual([]);
    });

    it('index 中引用了不存在的数据时 list 跳过缺失项', () => {
      // 直接在 localStorage 写入一个 index，其中包含一个没有对应数据的 ID
      localStorage.setItem(SUBFLOW_INDEX_KEY, JSON.stringify(['sf-exists', 'sf-missing']));
      localStorage.setItem(`${KEY_PREFIX}sf-exists`, JSON.stringify(makeSubflow('sf-exists', 'Exists')));

      const { result } = renderHook(() => useSubflowStorage());
      const list = result.current.listSubflows();
      expect(list).toHaveLength(1);
      expect(list[0].id).toBe('sf-exists');
    });
  });
});

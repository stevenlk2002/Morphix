import { create } from 'zustand';
import type { OrchestrateStore, PanelTabKey, DebugSession } from '../types/orchestrate';

/** 默认快捷消息 */
const DEFAULT_QUICK_MESSAGES = [
  '你好',
  '我想了解产品',
  '帮我查询订单',
];

/**
 * 编排台 Zustand store。
 * 管理面板状态、选中状态、Bot 信息、测试模式，与 React Flow 内部状态解耦。
 */
export const useOrchestrateStore = create<OrchestrateStore>((set) => ({
  // 面板状态
  activeTab: 'basic' as PanelTabKey,
  panelCollapsed: false,
  searchQuery: '',
  panelWidth: 280,

  // 选中状态
  selectedNodeId: null,
  selectedEdgeId: null,

  // Bot 信息
  botId: '',
  botName: '',
  lastEdited: '',

  // 测试模式
  testMode: false,
  debugSession: null,
  testPanelHeight: 320,
  quickMessages: [...DEFAULT_QUICK_MESSAGES],

  // Actions
  setActiveTab: (tab: PanelTabKey) => set({ activeTab: tab }),
  setPanelCollapsed: (collapsed: boolean) => set({ panelCollapsed: collapsed }),
  setSearchQuery: (query: string) => set({ searchQuery: query }),
  setPanelWidth: (width: number) => set({ panelWidth: width }),
  setSelectedNodeId: (id: string | null) => set({ selectedNodeId: id, selectedEdgeId: null }),
  setSelectedEdgeId: (id: string | null) => set({ selectedEdgeId: id, selectedNodeId: null }),
  setBotInfo: (id: string, name: string) => set({ botId: id, botName: name }),
  updateLastEdited: () => set({ lastEdited: new Date().toISOString() }),

  // 测试模式 Actions
  setTestMode: (mode: boolean) => set({ testMode: mode }),
  setDebugSession: (session: DebugSession | null) => set({ debugSession: session }),
  resetDebugSession: () => set({
    debugSession: null,
  }),
  setTestPanelHeight: (height: number) => set({ testPanelHeight: height }),
  setQuickMessages: (msgs: string[]) => set({ quickMessages: msgs }),
}));

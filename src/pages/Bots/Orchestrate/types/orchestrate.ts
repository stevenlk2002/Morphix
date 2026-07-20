// ──── 端口类型定义 ────

/** 7 种端口数据类型 */
export type PortDataType =
  | 'string'
  | 'number'
  | 'boolean'
  | 'chatHistory'
  | 'knowledgeRef'
  | 'any'
  | 'property';

export interface PortTypeInfo {
  label: string;
  color: string;
  desc: string;
}

/** 端口类型常量表 */
export type PortTypeMap = Record<PortDataType, PortTypeInfo>;

// ──── 节点协议（来自 NODE_SCHEMAS）────

/** 节点输入点定义 */
export interface InputPortDef {
  key: string;
  name: string;
  varName: string;
  dataType: PortDataType;
  required: boolean;
  mode: 'connect' | 'input' | 'both';
}

/** 节点输出点定义 */
export interface OutputPortDef {
  name: string;
  varName: string;
  dataType: PortDataType;
}

/** Config 字段类型 */
export type ConfigFieldType = 'text' | 'textarea' | 'select' | 'number' | 'note';

/** Config 字段定义 */
export interface ConfigFieldDef {
  key: string;
  label: string;
  fieldType: ConfigFieldType;
  required: boolean;
  options?: string[];
  default?: string | number;
  placeholder?: string;
}

/** 节点 Schema（完整协议） */
export interface NodeSchema {
  inputs: InputPortDef[];
  outputs: OutputPortDef[];
  config: ConfigFieldDef[];
}

// ──── 面板节点（ORCHESTRATE_NODES）────

/** 面板中的节点卡片定义 */
export interface PanelNodeDef {
  id: string;
  title: string;
  desc: string;
  color: string;
  icon: string;
}

/** 面板节点分类 */
export interface PanelCategory {
  category: string;
  nodes: PanelNodeDef[];
}

/** 面板 Tab 名称 */
export type PanelTabKey = 'basic' | 'composite' | 'special';

/** 面板 3 Tab */
export type PanelTabs = Record<PanelTabKey, PanelCategory[]>;

// ──── 运行时数据 ────

/** 画布上节点实例的自定义数据（React Flow node.data） */
export interface NodeInstanceData {
  nodeType: string;
  config: Record<string, string | number>;
  inputs: Record<string, string>;
  /** 子流程 ID（仅 subflowCall 节点使用） */
  subflowId?: string;
  /** 子流程名称（仅 subflowCall 节点使用，冗余存储） */
  subflowName?: string;
  /** 子流程描述（仅 subflowCall 节点使用，冗余存储） */
  subflowDesc?: string;
  /** 输入端口数（仅 subflowCall 节点使用） */
  inputPortsCount?: number;
  /** 输出端口数（仅 subflowCall 节点使用） */
  outputPortsCount?: number;
  [key: string]: unknown;
}

// ──── 持久化格式 ────

/** localStorage 序列化节点的 position + data */
export interface SerializedNode {
  id: string;
  type: string;
  position: { x: number; y: number };
  data: NodeInstanceData;
}

/** localStorage 序列化边 */
export interface SerializedEdge {
  id: string;
  source: string;
  target: string;
  sourceHandle: string;
  targetHandle: string;
}

/** localStorage 序列化结构 */
export interface WorkflowPersisted {
  botId: string;
  nodes: SerializedNode[];
  edges: SerializedEdge[];
  lastEdited: string;
  version: number;
}

// ──── 校验 ────

/** 校验错误 */
export interface ValidationError {
  nodeId: string;
  nodeName: string;
  fieldKey: string;
  fieldName: string;
  message: string;
}

/** 校验结果 */
export interface ValidationResult {
  valid: boolean;
  errors: ValidationError[];
}

// ═══════════════════════════════════════════
// 新增：子流程类型
// ═══════════════════════════════════════════

/** 子流程接口端口定义 */
export interface SubflowPortDef {
  key: string;
  varName: string;
  dataType: PortDataType;
  direction: 'input' | 'output';
  label: string;
}

/** 子流程接口 */
export interface SubflowInterface {
  inputs: SubflowPortDef[];
  outputs: SubflowPortDef[];
}

/** 子流程持久化格式（localStorage key: morphix_subflow_{id}） */
export interface SubflowPersisted {
  id: string;
  name: string;
  desc: string;
  interface: SubflowInterface;
  nodes: SerializedNode[];
  edges: SerializedEdge[];
  createdAt: string;
  updatedAt: string;
  version: number;
}

/** 子流程索引（localStorage key: morphix_subflow_index） */
export type SubflowIndex = string[];

// ═══════════════════════════════════════════
// 新增：自定义节点类型
// ═══════════════════════════════════════════

/** 自定义节点分类（扩展对应的 PanelTab） */
export type CustomNodeCategory =
  | '获取内容'
  | '输出'
  | '工具'
  | '流程控制'
  | '逻辑处理'
  | '复合'
  | '特殊渠道';

/** 自定义节点持久化格式（localStorage key: morphix_custom_nodes） */
export interface CustomNodeDef {
  id: string;
  name: string;
  category: CustomNodeCategory;
  desc: string;
  color: string;
  icon: string;
  inputs: InputPortDef[];
  outputs: OutputPortDef[];
  config: ConfigFieldDef[];
  createdAt: string;
}

// ═══════════════════════════════════════════
// 新增：调试台类型
// ═══════════════════════════════════════════

/** 单节点执行记录 */
export interface NodeExecutionRecord {
  nodeId: string;
  nodeName: string;
  nodeType: string;
  status: 'pending' | 'running' | 'success' | 'warning' | 'error';
  startedAt: string;
  finishedAt: string;
  durationMs: number;
  inputs: Record<string, unknown>;
  outputs: Record<string, unknown>;
  mockNote?: string;
  error?: string;
}

/** 调试会话 */
export interface DebugSession {
  sessionId: string;
  startedAt: string;
  status: 'idle' | 'running' | 'completed';
  trace: NodeExecutionRecord[];
  totalDurationMs: number;
  userMessage: string;
}

/** 测试面板状态（内嵌于 OrchestrateStore，不独立持久化） */
export interface TestPanelState {
  height: number;
  inputMessage: string;
  quickMessages: string[];
}

// ──── Zustand Store ────

export interface OrchestrateStore {
  // 面板状态
  activeTab: PanelTabKey;
  panelCollapsed: boolean;
  searchQuery: string;
  panelWidth: number;

  // 选中状态
  selectedNodeId: string | null;
  selectedEdgeId: string | null;

  // Bot 信息
  botId: string;
  botName: string;
  lastEdited: string;

  // ── 新增：测试模式 ──
  testMode: boolean;
  debugSession: DebugSession | null;
  testPanelHeight: number;
  quickMessages: string[];

  // Actions
  setActiveTab: (tab: PanelTabKey) => void;
  setPanelCollapsed: (collapsed: boolean) => void;
  setSearchQuery: (query: string) => void;
  setPanelWidth: (width: number) => void;
  setSelectedNodeId: (id: string | null) => void;
  setSelectedEdgeId: (id: string | null) => void;
  setBotInfo: (id: string, name: string) => void;
  updateLastEdited: () => void;

  // ── 新增 Actions ──
  setTestMode: (mode: boolean) => void;
  setDebugSession: (session: DebugSession | null) => void;
  resetDebugSession: () => void;
  setTestPanelHeight: (height: number) => void;
  setQuickMessages: (msgs: string[]) => void;
}

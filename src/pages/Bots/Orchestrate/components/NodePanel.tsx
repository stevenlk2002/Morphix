import { useCallback, useRef, useMemo, useState } from 'react';
import { Search, PanelLeftClose, PanelLeft, Plus } from 'lucide-react';
import { useOrchestrateStore } from '../store/orchestrateStore';
import { ORCHESTRATE_NODES } from '../data/panelNodes';
import { loadCustomNodes } from '../data/customNodeStorage';
import { useSubflowStorage } from '../hooks/useSubflowStorage';
import NodeCard from './NodeCard';
import CustomNodeModal from './CustomNodeModal';
import type { PanelTabKey, PanelNodeDef, PanelCategory } from '../types/orchestrate';
import './NodePanel.css';

const TAB_LABELS: Record<PanelTabKey, string> = {
  basic: '基础节点',
  composite: '复合节点',
  special: '特殊渠道节点',
};

/**
 * 左侧节点面板。
 * 支持 3 Tab 切换、搜索过滤、折叠/展开、新增自定义节点。
 * 复合 Tab "子流程调用" 分类动态读取 localStorage 中已保存的子流程。
 * 底部显示 "自定义" 分类（来自 morphix_custom_nodes）。
 */
export default function NodePanel() {
  const {
    activeTab,
    panelCollapsed,
    searchQuery,
    panelWidth,
    setActiveTab,
    setPanelCollapsed,
    setSearchQuery,
    setPanelWidth,
  } = useOrchestrateStore();

  const { listSubflows } = useSubflowStorage();
  const resizeRef = useRef<{ startX: number; startW: number } | null>(null);
  const [customNodeModalOpen, setCustomNodeModalOpen] = useState(false);
  // 用 key 来强制刷新自定义节点列表（每次重新加载）
  const [customNodesVersion, setCustomNodesVersion] = useState(0);

  const handleDragStart = useCallback((_nodeType: string) => {
    // drag start is handled by NodeCard's dataTransfer
  }, []);

  const handleCustomNodeSaved = useCallback(() => {
    setCustomNodeModalOpen(false);
    setCustomNodesVersion((v) => v + 1);
  }, []);

  // 面板宽度拖拽调整
  function handleResizeStart(e: React.MouseEvent) {
    e.preventDefault();
    resizeRef.current = { startX: e.clientX, startW: panelWidth };

    function onMove(ev: MouseEvent) {
      if (!resizeRef.current) return;
      let w = resizeRef.current.startW + (ev.clientX - resizeRef.current.startX);
      if (w < 200) w = 200;
      if (w > 500) w = 500;
      setPanelWidth(w);
    }

    function onUp() {
      resizeRef.current = null;
      document.removeEventListener('mousemove', onMove);
      document.removeEventListener('mouseup', onUp);
    }

    document.addEventListener('mousemove', onMove);
    document.addEventListener('mouseup', onUp);
  }

  // 动态构建 tabData：composite tab 中注入已保存子流程；追加自定义节点分类
  const tabData = useMemo(() => {
    const base = ORCHESTRATE_NODES[activeTab] ?? [];
    let result = [...base];

    if (activeTab === 'composite') {
      const subflows = listSubflows();
      const subflowNodes: PanelNodeDef[] = subflows.map((sf) => ({
        id: `subflow:${sf.id}`,
        title: sf.name,
        desc: sf.desc || `${sf.interface.inputs.length} 入 / ${sf.interface.outputs.length} 出`,
        color: '#8b5cf6',
        icon: 'package',
      }));

      result = result.map((cat: PanelCategory) => {
        if (cat.category === '子流程调用') {
          return {
            ...cat,
            nodes: [...cat.nodes, ...subflowNodes],
          };
        }
        return cat;
      });
    }

    // 追加自定义节点（从 localStorage 加载）
    const customNodes = loadCustomNodes();
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    void customNodesVersion; // 用于触发重新计算

    const customPanelNodes: PanelNodeDef[] = customNodes.map((cn) => ({
      id: cn.id,
      title: cn.name,
      desc: cn.desc || `${cn.inputs.length} 入 / ${cn.outputs.length} 出`,
      color: cn.color,
      icon: cn.icon,
    }));

    if (customPanelNodes.length > 0) {
      result = [
        ...result,
        {
          category: '自定义',
          nodes: customPanelNodes,
        },
      ];
    }

    return result;
  }, [activeTab, listSubflows, customNodesVersion]);

  const filter = searchQuery.toLowerCase();
  const filteredCategories = tabData
    .map((cat) => {
      const nodes = cat.nodes.filter(
        (n) =>
          !filter ||
          n.title.toLowerCase().includes(filter) ||
          n.desc.toLowerCase().includes(filter),
      );
      return { ...cat, nodes };
    })
    .filter((cat) => cat.nodes.length > 0);

  if (panelCollapsed) {
    return (
      <div className="node-panel node-panel--collapsed" style={{ width: 48 }}>
        <button
          className="node-panel__toggle-btn"
          onClick={() => setPanelCollapsed(false)}
          title="展开节点面板"
        >
          <PanelLeft size={18} />
        </button>
        <div className="node-panel__collapsed-tabs">
          {(Object.keys(TAB_LABELS) as PanelTabKey[]).map((tab) => (
            <button
              key={tab}
              className={`node-panel__collapsed-tab${activeTab === tab ? ' active' : ''}`}
              onClick={() => {
                setActiveTab(tab);
                setPanelCollapsed(false);
              }}
              title={TAB_LABELS[tab]}
            >
              {TAB_LABELS[tab].charAt(0)}
            </button>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="node-panel" style={{ width: panelWidth }}>
      {/* Header */}
      <div className="node-panel__header">
        <span className="node-panel__title">节点列表</span>
        <button
          className="node-panel__collapse-btn"
          onClick={() => setPanelCollapsed(true)}
          title="折叠面板"
        >
          <PanelLeftClose size={16} />
        </button>
      </div>

      {/* 搜索框 + 新增按钮 */}
      <div className="node-panel__search-row">
        <div className="node-panel__search">
          <Search size={14} className="node-panel__search-icon" />
          <input
            type="text"
            className="node-panel__search-input"
            placeholder="搜索节点..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
        </div>
        <button
          className="node-panel__add-custom-btn"
          onClick={() => setCustomNodeModalOpen(true)}
          title="新增自定义节点"
        >
          <Plus size={14} />
          新增节点
        </button>
      </div>

      {/* Tabs */}
      <div className="node-panel__tabs">
        {(Object.keys(TAB_LABELS) as PanelTabKey[]).map((tab) => (
          <button
            key={tab}
            className={`node-panel__tab${activeTab === tab ? ' active' : ''}`}
            onClick={() => setActiveTab(tab)}
          >
            {TAB_LABELS[tab]}
          </button>
        ))}
      </div>

      {/* 节点列表 */}
      <div className="node-panel__list">
        {filteredCategories.length === 0 ? (
          <div className="node-panel__empty">未找到匹配节点</div>
        ) : (
          filteredCategories.map((cat) => (
            <div className="node-panel__category" key={cat.category}>
              <div className="node-panel__category-title">{cat.category}</div>
              <div className="node-panel__category-nodes">
                {cat.nodes.map((n) => (
                  <NodeCard
                    key={n.id}
                    node={n}
                    onDragStart={handleDragStart}
                  />
                ))}
              </div>
            </div>
          ))
        )}
        {/* 面板底部 "新增节点" 快捷入口 */}
        {filteredCategories.length > 0 && (
          <button
            className="node-panel__add-bottom-btn"
            onClick={() => setCustomNodeModalOpen(true)}
            title="新增自定义节点"
          >
            <Plus size={14} />
            新增节点
          </button>
        )}
      </div>

      {/* 拖拽调整手柄 */}
      <div
        className="node-panel__resize-handle"
        onMouseDown={handleResizeStart}
      />

      {/* 自定义节点弹窗 */}
      {customNodeModalOpen && (
        <CustomNodeModal onClose={handleCustomNodeSaved} />
      )}
    </div>
  );
}

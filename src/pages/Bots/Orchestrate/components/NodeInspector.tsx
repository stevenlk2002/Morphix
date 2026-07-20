import { useCallback, useState } from 'react';
import { SlidersHorizontal, ExternalLink } from 'lucide-react';
import { useOrchestrateStore } from '../store/orchestrateStore';
import { NODE_SCHEMAS } from '../data/nodeDefinitions';
import { ORCHESTRATE_NODES } from '../data/panelNodes';
import { loadCustomNodes } from '../data/customNodeStorage';
import { useSubflowStorage } from '../hooks/useSubflowStorage';
import SubflowPreviewModal from './SubflowPreviewModal';
import ConfigField from './ConfigField';
import type { OrchestrateNode } from './FlowCanvas';
import type { PanelNodeDef, NodeSchema } from '../types/orchestrate';
import './NodeInspector.css';

/** 从 ORCHESTRATE_NODES + 自定义节点 查找节点展示定义 */
function findPanelDef(nodeType: string): PanelNodeDef | null {
  if (nodeType.startsWith('custom:')) {
    const customNodes = loadCustomNodes();
    const found = customNodes.find((cn) => cn.id === nodeType);
    if (found) {
      return {
        id: found.id,
        title: found.name,
        desc: found.desc || '',
        color: found.color,
        icon: found.icon,
      };
    }
    return null;
  }

  for (const tab of Object.values(ORCHESTRATE_NODES)) {
    for (const cat of tab) {
      const found = cat.nodes.find((n) => n.id === nodeType);
      if (found) return found;
    }
  }
  return null;
}

/** 查找节点 Schema（先查内置，再查自定义） */
function findSchema(nodeType: string): NodeSchema | null {
  if (NODE_SCHEMAS[nodeType]) return NODE_SCHEMAS[nodeType];

  if (nodeType.startsWith('custom:')) {
    const customNodes = loadCustomNodes();
    const found = customNodes.find((cn) => cn.id === nodeType);
    if (found) {
      return {
        inputs: found.inputs,
        outputs: found.outputs,
        config: found.config,
      };
    }
  }

  return null;
}

interface NodeInspectorProps {
  nodes: OrchestrateNode[];
  onUpdateNodeData: (nodeId: string, data: Record<string, string | number>) => void;
}

/**
 * 右侧属性面板。
 * - 读取 selectedNodeId → 查找 node → 渲染 schema.config 动态表单
 * - subflowCall 节点：只读信息 + "展开查看内部"按钮
 * - 测试模式下折叠为占位提示
 * - 无选中时显示占位提示
 */
export default function NodeInspector({ nodes, onUpdateNodeData }: NodeInspectorProps) {
  const selectedNodeId = useOrchestrateStore((s) => s.selectedNodeId);
  const testMode = useOrchestrateStore((s) => s.testMode);
  const { loadSubflow } = useSubflowStorage();

  const [showPreview, setShowPreview] = useState(false);

  const selectedNode = selectedNodeId
    ? nodes.find((n) => n.id === selectedNodeId)
    : null;

  const def = selectedNode ? findPanelDef(selectedNode.data.nodeType) : null;
  const schema = selectedNode ? findSchema(selectedNode.data.nodeType) : null;

  const handleConfigChange = useCallback(
    (key: string, value: string | number) => {
      if (!selectedNodeId) return;
      const updatedConfig = {
        ...(selectedNode?.data.config ?? {}),
        [key]: value,
      };
      onUpdateNodeData(selectedNodeId, updatedConfig);
    },
    [selectedNodeId, selectedNode, onUpdateNodeData],
  );

  // 测试模式下折叠
  if (testMode) {
    return (
      <div className="node-inspector node-inspector--empty">
        <div className="node-inspector__empty">
          <SlidersHorizontal size={32} className="node-inspector__empty-icon" />
          <p className="node-inspector__empty-text">测试模式中</p>
          <p className="node-inspector__empty-hint">属性面板暂不可用，退出测试后恢复</p>
        </div>
      </div>
    );
  }

  // 无选中状态
  if (!selectedNode || !def || !schema) {
    return (
      <div className="node-inspector node-inspector--empty">
        <div className="node-inspector__empty">
          <SlidersHorizontal size={32} className="node-inspector__empty-icon" />
          <p className="node-inspector__empty-text">点击节点查看属性</p>
        </div>
      </div>
    );
  }

  // ──── subflowCall 节点属性 ────
  if (selectedNode.data.nodeType === 'subflowCall') {
    const subflowId = selectedNode.data.subflowId;
    const subflow = subflowId ? loadSubflow(subflowId) : null;

    return (
      <div className="node-inspector">
        <div className="node-inspector__header">
          <div
            className="node-inspector__header-icon"
            style={{ backgroundColor: '#8b5cf620', color: '#8b5cf6' }}
          >
            📦
          </div>
          <h3 className="node-inspector__title">
            {selectedNode.data.subflowName ?? subflow?.name ?? '子流程调用'}
          </h3>
        </div>

        <div className="node-inspector__body">
          {/* 子流程描述 */}
          {(selectedNode.data.subflowDesc || subflow?.desc) && (
            <div className="node-inspector__section">
              <h4 className="node-inspector__section-title">描述</h4>
              <p className="node-inspector__readonly-text">
                {selectedNode.data.subflowDesc || subflow?.desc}
              </p>
            </div>
          )}

          {/* 输入接口 */}
          {subflow && subflow.interface.inputs.length > 0 && (
            <div className="node-inspector__section">
              <h4 className="node-inspector__section-title">
                输入接口 ({subflow.interface.inputs.length})
              </h4>
              {subflow.interface.inputs.map((inp) => (
                <div className="node-inspector__port-info" key={inp.key}>
                  <span className="node-inspector__port-name">{inp.label}</span>
                  <span className="node-inspector__port-meta">{inp.dataType}</span>
                </div>
              ))}
            </div>
          )}

          {/* 输出接口 */}
          {subflow && subflow.interface.outputs.length > 0 && (
            <div className="node-inspector__section">
              <h4 className="node-inspector__section-title">
                输出接口 ({subflow.interface.outputs.length})
              </h4>
              {subflow.interface.outputs.map((out) => (
                <div className="node-inspector__port-info" key={out.key}>
                  <span className="node-inspector__port-name">{out.label}</span>
                  <span className="node-inspector__port-meta">{out.dataType}</span>
                </div>
              ))}
            </div>
          )}

          {/* 展开查看内部按钮 */}
          {subflowId && (
            <div className="node-inspector__section">
              <button
                className="node-inspector__expand-btn"
                onClick={() => setShowPreview(true)}
              >
                <ExternalLink size={14} />
                展开查看内部
              </button>
            </div>
          )}

          {/* 说明字段 */}
          {schema.config.map((field) => (
            <div className="node-inspector__section" key={field.key}>
              <ConfigField
                field={field}
                value={selectedNode.data.config[field.key]}
                onChange={handleConfigChange}
              />
            </div>
          ))}
        </div>

        {/* 预览弹窗 */}
        {showPreview && subflowId && (
          <SubflowPreviewModal
            subflowId={subflowId}
            onClose={() => setShowPreview(false)}
          />
        )}
      </div>
    );
  }

  // ──── 普通节点属性 ────
  return (
    <div className="node-inspector">
      <div className="node-inspector__header">
        <div
          className="node-inspector__header-icon"
          style={{ backgroundColor: def.color + '20', color: def.color }}
        >
          {def.icon}
        </div>
        <h3 className="node-inspector__title">{def.title}</h3>
      </div>

      <div className="node-inspector__body">
        {/* 输入端口信息 */}
        {schema.inputs.length > 0 && (
          <div className="node-inspector__section">
            <h4 className="node-inspector__section-title">输入端口</h4>
            {schema.inputs.map((inp) => (
              <div className="node-inspector__port-info" key={inp.key}>
                <span className="node-inspector__port-name">
                  {inp.name}
                  {inp.required && <span className="config-field__required">*</span>}
                </span>
                <span className="node-inspector__port-meta">
                  {inp.mode === 'connect' ? '仅连线' : inp.mode === 'input' ? '仅输入' : '连线/输入'}
                </span>
              </div>
            ))}
          </div>
        )}

        {/* 配置字段 */}
        {schema.config.length > 0 && (
          <div className="node-inspector__section">
            <h4 className="node-inspector__section-title">配置</h4>
            {schema.config.map((field) => (
              <ConfigField
                key={field.key}
                field={field}
                value={selectedNode.data.config[field.key]}
                onChange={handleConfigChange}
              />
            ))}
          </div>
        )}

        {/* 输出端口信息 */}
        {schema.outputs.length > 0 && (
          <div className="node-inspector__section">
            <h4 className="node-inspector__section-title">输出端口</h4>
            {schema.outputs.map((out) => (
              <div className="node-inspector__port-info" key={out.varName}>
                <span className="node-inspector__port-name">{out.name}</span>
                <span className="node-inspector__port-meta">
                  {out.dataType} · {out.varName}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

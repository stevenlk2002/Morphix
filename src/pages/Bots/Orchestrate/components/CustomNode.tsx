import { memo } from 'react';
import { Handle, Position, type NodeProps, type Node } from '@xyflow/react';
import { NODE_SCHEMAS } from '../data/nodeDefinitions';
import { ORCHESTRATE_NODES } from '../data/panelNodes';
import { loadCustomNodes } from '../data/customNodeStorage';
import { getPortType } from '../data/portTypes';
import { useOrchestrateStore } from '../store/orchestrateStore';
import type { NodeInstanceData, PanelNodeDef, SubflowPersisted } from '../types/orchestrate';
import './CustomNode.css';

/** 从 ORCHESTRATE_NODES 中查找节点定义 */
function findPanelDef(nodeType: string): PanelNodeDef | null {
  // 优先查自定义节点
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

/** 简单 icon 渲染 */
function renderIcon(def: PanelNodeDef): string {
  const map: Record<string, string> = {
    text: 'T',
    variable: 'Fx',
    'message-circle': '💬',
    send: '➤',
    image: '🖼',
    user: '👤',
    'git-branch': '◇',
    clock: '⏱',
    bot: '🤖',
    database: '📚',
    regex: '.*',
    braces: '{}',
    'alert-triangle': '⚠',
    package: '📦',
    file: '📄',
    video: '🎬',
    mic: '🎤',
    link: '🔗',
    'file-text': '📝',
    mail: '📧',
    smartphone: '📱',
    subflow: '🔀',
    tag: '🏷',
    group: '👥',
    edit: '✏',
    notice: '📢',
    code: '<>',
  };
  return map[def.icon] ?? def.icon.substring(0, 2);
}

/** 从 localStorage 读取子流程定义 */
function loadSubflowFromLS(subflowId: string): SubflowPersisted | null {
  try {
    const raw = localStorage.getItem(`morphix_subflow_${subflowId}`);
    if (!raw) return null;
    return JSON.parse(raw) as SubflowPersisted;
  } catch {
    return null;
  }
}

/**
 * React Flow 自定义节点。
 * 渲染节点卡片：Header（图标 + 名称）+ Body（左侧 input 端口、右侧 output 端口、中间描述）。
 * 支持 subflowCall 类型：动态端口 + 虚线边框 + 特殊标题。
 */
function CustomNode({ data, selected }: NodeProps<Node<NodeInstanceData>>) {
  const nodeType: string = data.nodeType || 'unknown';
  const testMode = useOrchestrateStore((s) => s.testMode);
  const debugSession = useOrchestrateStore((s) => s.debugSession);

  // 测试模式 & 调试会话可用（暂通过 FlowCanvas 注入 className；后续可扩展高亮逻辑）
  void testMode;
  void debugSession;

  // ──── subflowCall 节点渲染 ────
  if (nodeType === 'subflowCall') {
    const subflowId = data.subflowId;
    const subflow = subflowId ? loadSubflowFromLS(subflowId) : null;
    const sfInputs = subflow?.interface.inputs ?? [];
    const sfOutputs = subflow?.interface.outputs ?? [];
    const name = data.subflowName ?? subflow?.name ?? '子流程调用';
    const desc = data.subflowDesc ?? subflow?.desc ?? '';
    const inputCount = data.inputPortsCount ?? sfInputs.length;
    const outputCount = data.outputPortsCount ?? sfOutputs.length;

    return (
      <div className={`custom-node custom-node--subflow${selected ? ' custom-node--selected' : ''}`}>
        {/* 左侧色条 */}
        <div className="custom-node__accent" style={{ backgroundColor: '#8b5cf6' }} />

        {/* Header */}
        <div className="custom-node-header">
          <div
            className="custom-node-header__icon"
            style={{ backgroundColor: '#8b5cf620', color: '#8b5cf6' }}
          >
            📦
          </div>
          <div className="custom-node-header__info">
            <div className="custom-node-header__title">{name}</div>
            <div className="custom-node-header__subtitle">
              {inputCount} 入 / {outputCount} 出
            </div>
          </div>
        </div>

        {/* 描述 */}
        {desc && (
          <div className="custom-node-subflow__desc">{desc}</div>
        )}

        {/* Body：动态端口 */}
        <div className="custom-node-body">
          <div className="custom-node-ports custom-node-ports--input">
            {sfInputs.map((inp) => {
              const pt = getPortType(inp.dataType);
              return (
                <div className="custom-node-port custom-node-port--input" key={inp.key}>
                  <Handle
                    type="target"
                    position={Position.Left}
                    id={inp.key}
                    style={{
                      background: pt.color,
                      boxShadow: `0 0 0 2px ${pt.color}20`,
                      width: 10,
                      height: 10,
                      border: '2px solid var(--surface)',
                    }}
                    title={`${pt.label} · ${inp.label}`}
                  />
                  <span className="custom-node-port__name">{inp.label}</span>
                </div>
              );
            })}
            {sfInputs.length === 0 && (
              <div className="custom-node-port custom-node-port--input">
                <Handle
                  type="target"
                  position={Position.Left}
                  id="__no_input__"
                  style={{ visibility: 'hidden', width: 1, height: 1 }}
                />
              </div>
            )}
          </div>

          <div className="custom-node-body__desc">
            {sfInputs.length + sfOutputs.length === 0 ? '无端口' : ''}
          </div>

          <div className="custom-node-ports custom-node-ports--output">
            {sfOutputs.map((out) => {
              const pt = getPortType(out.dataType);
              return (
                <div className="custom-node-port custom-node-port--output" key={out.key}>
                  <span className="custom-node-port__name">{out.label}</span>
                  <Handle
                    type="source"
                    position={Position.Right}
                    id={out.key}
                    style={{
                      background: pt.color,
                      boxShadow: `0 0 0 2px ${pt.color}20`,
                      width: 10,
                      height: 10,
                      border: '2px solid var(--surface)',
                    }}
                    title={`${pt.label} · ${out.label}`}
                  />
                </div>
              );
            })}
            {sfOutputs.length === 0 && (
              <div className="custom-node-port custom-node-port--output">
                <Handle
                  type="source"
                  position={Position.Right}
                  id="__no_output__"
                  style={{ visibility: 'hidden', width: 1, height: 1 }}
                />
              </div>
            )}
          </div>
        </div>
      </div>
    );
  }

  // ──── 普通节点渲染 ────
  const def = findPanelDef(nodeType);
  // 自定义节点从 localStorage 读取完整 schema
  const isCustom = nodeType.startsWith('custom:');
  let schema = NODE_SCHEMAS[nodeType];
  if (isCustom && !schema) {
    const customNodes = loadCustomNodes();
    const customDef = customNodes.find((cn) => cn.id === nodeType);
    if (customDef) {
      schema = {
        inputs: customDef.inputs,
        outputs: customDef.outputs,
        config: customDef.config,
      };
    }
  }

  if (!def || !schema) {
    return (
      <div className="custom-node" style={{ border: '2px solid #ef4444' }}>
        <div className="custom-node-header">
          <span>未知节点: {nodeType}</span>
        </div>
      </div>
    );
  }

  return (
    <div className={`custom-node${selected ? ' custom-node--selected' : ''}`}>
      {/* 左侧色条 */}
      <div
        className="custom-node__accent"
        style={{ backgroundColor: def.color }}
      />

      {/* Header */}
      <div className="custom-node-header">
        <div
          className="custom-node-header__icon"
          style={{ backgroundColor: def.color + '20', color: def.color }}
        >
          {renderIcon(def)}
        </div>
        <div className="custom-node-header__title">{def.title}</div>
      </div>

      {/* Body */}
      <div className="custom-node-body">
        {/* 左侧输入端口 */}
        <div className="custom-node-ports custom-node-ports--input">
          {schema.inputs.map((inp) => {
            const pt = getPortType(inp.dataType);
            return (
              <div className="custom-node-port custom-node-port--input" key={inp.key}>
                <Handle
                  type="target"
                  position={Position.Left}
                  id={inp.key}
                  style={{
                    background: pt.color,
                    boxShadow: `0 0 0 2px ${pt.color}20`,
                    width: 10,
                    height: 10,
                    border: '2px solid var(--surface)',
                  }}
                  title={`${pt.label} · ${pt.desc}${inp.required ? ' (必填)' : ''}`}
                />
                <span className="custom-node-port__name">
                  {inp.name}
                  {inp.required && <span className="custom-node-port__required">*</span>}
                </span>
              </div>
            );
          })}
        </div>

        {/* 中间描述 */}
        <div className="custom-node-body__desc">{def.desc}</div>

        {/* 右侧输出端口 */}
        <div className="custom-node-ports custom-node-ports--output">
          {schema.outputs.map((out) => {
            const pt = getPortType(out.dataType);
            return (
              <div className="custom-node-port custom-node-port--output" key={out.varName}>
                <span className="custom-node-port__name">{out.name}</span>
                <Handle
                  type="source"
                  position={Position.Right}
                  id={out.varName}
                  style={{
                    background: pt.color,
                    boxShadow: `0 0 0 2px ${pt.color}20`,
                    width: 10,
                    height: 10,
                    border: '2px solid var(--surface)',
                  }}
                  title={`${pt.label} · ${pt.desc}`}
                />
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

export default memo(CustomNode);

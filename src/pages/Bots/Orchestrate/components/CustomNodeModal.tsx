import { useState, useCallback } from 'react';
import { X, Plus, Trash2 } from 'lucide-react';
import { addCustomNode } from '../data/customNodeStorage';
import type {
  CustomNodeCategory,
  CustomNodeDef,
  InputPortDef,
  OutputPortDef,
  ConfigFieldDef,
  PortDataType,
  ConfigFieldType,
} from '../types/orchestrate';
import './CustomNodeModal.css';

const CATEGORY_OPTIONS: CustomNodeCategory[] = [
  '获取内容', '输出', '工具', '流程控制', '逻辑处理', '复合', '特殊渠道',
];

const PORT_TYPE_OPTIONS: PortDataType[] = [
  'string', 'number', 'boolean', 'chatHistory', 'knowledgeRef', 'any', 'property',
];

const FIELD_TYPE_OPTIONS: ConfigFieldType[] = [
  'text', 'textarea', 'select', 'number', 'note',
];

const INPUT_MODE_OPTIONS: Array<InputPortDef['mode']> = ['connect', 'input', 'both'];

const PRESET_COLORS = [
  '#c9a87c', '#5fb5a6', '#6a9bcc', '#a88bd8', '#e49a6d', '#8b5cf6', '#ef4444',
];

interface CustomNodeModalProps {
  onClose: () => void;
}

/** 空输入端口模板 */
function emptyInputPort(): InputPortDef {
  return { key: '', name: '', varName: '', dataType: 'any', required: false, mode: 'both' };
}

/** 空输出端口模板 */
function emptyOutputPort(): OutputPortDef {
  return { name: '', varName: '', dataType: 'any' };
}

/** 空配置字段模板 */
function emptyConfigField(): ConfigFieldDef {
  return { key: '', label: '', fieldType: 'text', required: false };
}

/**
 * 新增自定义节点弹窗。
 * 支持配置名称、分类、描述、颜色、图标，以及动态增删输入/输出端口和配置字段。
 * 保存到 localStorage（morphix_custom_nodes）。
 */
export default function CustomNodeModal({ onClose }: CustomNodeModalProps) {
  const [name, setName] = useState('');
  const [category, setCategory] = useState<CustomNodeCategory>('工具');
  const [desc, setDesc] = useState('');
  const [color, setColor] = useState('#6a9bcc');
  const [icon, setIcon] = useState('code');
  const [inputs, setInputs] = useState<InputPortDef[]>([]);
  const [outputs, setOutputs] = useState<OutputPortDef[]>([
    { name: '结果', varName: 'result', dataType: 'any' },
  ]);
  const [configFields, setConfigFields] = useState<ConfigFieldDef[]>([]);
  const [nameError, setNameError] = useState('');

  // ──── 输入端口操作 ────
  const addInput = useCallback(() => {
    setInputs((prev) => [...prev, emptyInputPort()]);
  }, []);

  const updateInput = useCallback((idx: number, patch: Partial<InputPortDef>) => {
    setInputs((prev) => prev.map((p, i) => (i === idx ? { ...p, ...patch } : p)));
  }, []);

  const removeInput = useCallback((idx: number) => {
    setInputs((prev) => prev.filter((_, i) => i !== idx));
  }, []);

  // ──── 输出端口操作 ────
  const addOutput = useCallback(() => {
    setOutputs((prev) => [...prev, emptyOutputPort()]);
  }, []);

  const updateOutput = useCallback((idx: number, patch: Partial<OutputPortDef>) => {
    setOutputs((prev) => prev.map((p, i) => (i === idx ? { ...p, ...patch } : p)));
  }, []);

  const removeOutput = useCallback((idx: number) => {
    setOutputs((prev) => prev.filter((_, i) => i !== idx));
  }, []);

  // ──── 配置字段操作 ────
  const addConfigField = useCallback(() => {
    setConfigFields((prev) => [...prev, emptyConfigField()]);
  }, []);

  const updateConfigField = useCallback((idx: number, patch: Partial<ConfigFieldDef>) => {
    setConfigFields((prev) => prev.map((p, i) => (i === idx ? { ...p, ...patch } : p)));
  }, []);

  const removeConfigField = useCallback((idx: number) => {
    setConfigFields((prev) => prev.filter((_, i) => i !== idx));
  }, []);

  // ──── 保存 ────
  const handleSave = useCallback(() => {
    const trimmedName = name.trim();
    if (!trimmedName) {
      setNameError('请输入节点名称');
      return;
    }
    setNameError('');

    // 过滤空端口
    const validInputs = inputs.filter((p) => p.key.trim() && p.name.trim() && p.varName.trim());
    const validOutputs = outputs.filter((p) => p.name.trim() && p.varName.trim());
    const validConfig = configFields.filter((p) => p.key.trim());

    const node: CustomNodeDef = {
      id: `custom:${Date.now()}`,
      name: trimmedName,
      category,
      desc: desc.trim(),
      color,
      icon: icon.trim() || 'code',
      inputs: validInputs,
      outputs: validOutputs,
      config: validConfig,
      createdAt: new Date().toISOString(),
    };

    addCustomNode(node);
    onClose();
  }, [name, category, desc, color, icon, inputs, outputs, configFields, onClose]);

  return (
    <div className="custom-node-modal__overlay" onClick={onClose}>
      <div className="custom-node-modal" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className="custom-node-modal__header">
          <h2 className="custom-node-modal__title">+ 新增节点</h2>
          <button className="custom-node-modal__close" onClick={onClose} title="关闭">
            <X size={18} />
          </button>
        </div>

        {/* Body */}
        <div className="custom-node-modal__body">
          {/* 基本信息 */}
          <div className="custom-node-modal__row">
            <div className="custom-node-modal__field custom-node-modal__field--flex1">
              <label className="custom-node-modal__label">
                节点名称 <span className="custom-node-modal__required">*</span>
              </label>
              <input
                type="text"
                className={`custom-node-modal__input${nameError ? ' custom-node-modal__input--error' : ''}`}
                placeholder="输入节点名称"
                value={name}
                onChange={(e) => { setName(e.target.value); if (nameError) setNameError(''); }}
                autoFocus
              />
              {nameError && <span className="custom-node-modal__error">{nameError}</span>}
            </div>
            <div className="custom-node-modal__field custom-node-modal__field--flex1">
              <label className="custom-node-modal__label">
                节点分类 <span className="custom-node-modal__required">*</span>
              </label>
              <select
                className="custom-node-modal__select"
                value={category}
                onChange={(e) => setCategory(e.target.value as CustomNodeCategory)}
              >
                {CATEGORY_OPTIONS.map((c) => (
                  <option key={c} value={c}>{c}</option>
                ))}
              </select>
            </div>
          </div>

          <div className="custom-node-modal__field">
            <label className="custom-node-modal__label">节点描述</label>
            <input
              type="text"
              className="custom-node-modal__input"
              placeholder="输入节点描述（选填）"
              value={desc}
              onChange={(e) => setDesc(e.target.value)}
            />
          </div>

          {/* 颜色选择 */}
          <div className="custom-node-modal__field">
            <label className="custom-node-modal__label">节点颜色</label>
            <div className="custom-node-modal__colors">
              {PRESET_COLORS.map((c) => (
                <button
                  key={c}
                  type="button"
                  className={`custom-node-modal__color-swatch${color === c ? ' custom-node-modal__color-swatch--active' : ''}`}
                  style={{ backgroundColor: c }}
                  onClick={() => setColor(c)}
                  title={c}
                />
              ))}
              <input
                type="color"
                className="custom-node-modal__color-picker"
                value={color}
                onChange={(e) => setColor(e.target.value)}
                title="自定义颜色"
              />
            </div>
          </div>

          {/* 图标 */}
          <div className="custom-node-modal__field">
            <label className="custom-node-modal__label">图标</label>
            <input
              type="text"
              className="custom-node-modal__input"
              placeholder="图标名称（如 code、bot、user）"
              value={icon}
              onChange={(e) => setIcon(e.target.value)}
            />
          </div>

          {/* ──── 输入端口 ──── */}
          <div className="custom-node-modal__section">
            <div className="custom-node-modal__section-header">
              <h4 className="custom-node-modal__section-title">输入端口 ({inputs.length})</h4>
              <button
                type="button"
                className="custom-node-modal__add-btn"
                onClick={addInput}
                title="添加输入端口"
              >
                <Plus size={14} /> 添加
              </button>
            </div>
            {inputs.map((p, idx) => (
              <div className="custom-node-modal__port-row" key={idx}>
                <input
                  className="custom-node-modal__port-input"
                  placeholder="端口 key"
                  value={p.key}
                  onChange={(e) => updateInput(idx, { key: e.target.value })}
                />
                <input
                  className="custom-node-modal__port-input"
                  placeholder="端口名称"
                  value={p.name}
                  onChange={(e) => updateInput(idx, { name: e.target.value })}
                />
                <input
                  className="custom-node-modal__port-input"
                  placeholder="变量名"
                  value={p.varName}
                  onChange={(e) => updateInput(idx, { varName: e.target.value })}
                />
                <select
                  className="custom-node-modal__port-select"
                  value={p.dataType}
                  onChange={(e) => updateInput(idx, { dataType: e.target.value as PortDataType })}
                >
                  {PORT_TYPE_OPTIONS.map((t) => (
                    <option key={t} value={t}>{t}</option>
                  ))}
                </select>
                <select
                  className="custom-node-modal__port-select"
                  value={p.mode}
                  onChange={(e) => updateInput(idx, { mode: e.target.value as InputPortDef['mode'] })}
                >
                  {INPUT_MODE_OPTIONS.map((m) => (
                    <option key={m} value={m}>{m === 'connect' ? 'connect' : m === 'input' ? 'input' : 'both'}</option>
                  ))}
                </select>
                <label className="custom-node-modal__port-check">
                  <input
                    type="checkbox"
                    checked={p.required}
                    onChange={(e) => updateInput(idx, { required: e.target.checked })}
                  />
                  必填
                </label>
                <button
                  type="button"
                  className="custom-node-modal__remove-btn"
                  onClick={() => removeInput(idx)}
                  title="删除"
                >
                  <Trash2 size={14} />
                </button>
              </div>
            ))}
          </div>

          {/* ──── 输出端口 ──── */}
          <div className="custom-node-modal__section">
            <div className="custom-node-modal__section-header">
              <h4 className="custom-node-modal__section-title">输出端口 ({outputs.length})</h4>
              <button
                type="button"
                className="custom-node-modal__add-btn"
                onClick={addOutput}
                title="添加输出端口"
              >
                <Plus size={14} /> 添加
              </button>
            </div>
            {outputs.map((p, idx) => (
              <div className="custom-node-modal__port-row" key={idx}>
                <input
                  className="custom-node-modal__port-input"
                  placeholder="端口名称"
                  value={p.name}
                  onChange={(e) => updateOutput(idx, { name: e.target.value })}
                />
                <input
                  className="custom-node-modal__port-input"
                  placeholder="变量名"
                  value={p.varName}
                  onChange={(e) => updateOutput(idx, { varName: e.target.value })}
                />
                <select
                  className="custom-node-modal__port-select"
                  value={p.dataType}
                  onChange={(e) => updateOutput(idx, { dataType: e.target.value as PortDataType })}
                >
                  {PORT_TYPE_OPTIONS.map((t) => (
                    <option key={t} value={t}>{t}</option>
                  ))}
                </select>
                <button
                  type="button"
                  className="custom-node-modal__remove-btn"
                  onClick={() => removeOutput(idx)}
                  title="删除"
                >
                  <Trash2 size={14} />
                </button>
              </div>
            ))}
          </div>

          {/* ──── 配置字段 ──── */}
          <div className="custom-node-modal__section">
            <div className="custom-node-modal__section-header">
              <h4 className="custom-node-modal__section-title">配置字段 ({configFields.length})</h4>
              <button
                type="button"
                className="custom-node-modal__add-btn"
                onClick={addConfigField}
                title="添加配置字段"
              >
                <Plus size={14} /> 添加
              </button>
            </div>
            {configFields.map((f, idx) => (
              <div className="custom-node-modal__config-row" key={idx}>
                <div className="custom-node-modal__config-fields">
                  <input
                    className="custom-node-modal__port-input"
                    placeholder="字段 key"
                    value={f.key}
                    onChange={(e) => updateConfigField(idx, { key: e.target.value })}
                  />
                  <input
                    className="custom-node-modal__port-input"
                    placeholder="字段 label"
                    value={f.label}
                    onChange={(e) => updateConfigField(idx, { label: e.target.value })}
                  />
                  <select
                    className="custom-node-modal__port-select"
                    value={f.fieldType}
                    onChange={(e) => updateConfigField(idx, { fieldType: e.target.value as ConfigFieldType })}
                  >
                    {FIELD_TYPE_OPTIONS.map((t) => (
                      <option key={t} value={t}>{t}</option>
                    ))}
                  </select>
                </div>
                <div className="custom-node-modal__config-extras">
                  {f.fieldType === 'select' && (
                    <input
                      className="custom-node-modal__port-input"
                      placeholder="选项（逗号分隔）"
                      value={f.options ? f.options.join(',') : ''}
                      onChange={(e) => updateConfigField(idx, {
                        options: e.target.value ? e.target.value.split(',').map((s: string) => s.trim()).filter(Boolean) : undefined,
                      })}
                    />
                  )}
                  <input
                    className="custom-node-modal__port-input custom-node-modal__port-input--small"
                    placeholder="默认值"
                    value={f.default !== undefined ? String(f.default) : ''}
                    onChange={(e) => updateConfigField(idx, { default: e.target.value })}
                  />
                  <input
                    className="custom-node-modal__port-input custom-node-modal__port-input--small"
                    placeholder="占位文本"
                    value={f.placeholder ?? ''}
                    onChange={(e) => updateConfigField(idx, { placeholder: e.target.value || undefined })}
                  />
                  <label className="custom-node-modal__port-check">
                    <input
                      type="checkbox"
                      checked={f.required}
                      onChange={(e) => updateConfigField(idx, { required: e.target.checked })}
                    />
                    必填
                  </label>
                  <button
                    type="button"
                    className="custom-node-modal__remove-btn"
                    onClick={() => removeConfigField(idx)}
                    title="删除"
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Footer */}
        <div className="custom-node-modal__footer">
          <button
            className="custom-node-modal__btn custom-node-modal__btn--cancel"
            onClick={onClose}
          >
            取消
          </button>
          <button
            className="custom-node-modal__btn custom-node-modal__btn--confirm"
            onClick={handleSave}
            disabled={!name.trim()}
          >
            新增节点
          </button>
        </div>
      </div>
    </div>
  );
}

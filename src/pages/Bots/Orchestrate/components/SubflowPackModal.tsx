import { useState, useMemo, useCallback } from 'react';
import { X } from 'lucide-react';
import { useSubflowPack } from '../hooks/useSubflowPack';
import { useSubflowStorage } from '../hooks/useSubflowStorage';
import { getPortType } from '../data/portTypes';
import { toast } from '../../../../utils/toast';
import type { OrchestrateNode, OrchestrateEdge } from './FlowCanvas';
import type { SubflowInterface, SubflowPortDef } from '../types/orchestrate';
import './SubflowPackModal.css';

interface SubflowPackModalProps {
  selectedNodeIds: string[];
  allNodes: OrchestrateNode[];
  allEdges: OrchestrateEdge[];
  onClose: () => void;
  onPackComplete: (
    newNodes: OrchestrateNode[],
    newEdges: OrchestrateEdge[],
  ) => void;
}

/** 可勾选的接口端口项 */
function PortItem({
  port,
  checked,
  onToggle,
}: {
  port: SubflowPortDef;
  checked: boolean;
  onToggle: () => void;
}) {
  const pt = getPortType(port.dataType);
  return (
    <label className="subflow-pack-modal__port-item">
      <input
        type="checkbox"
        checked={checked}
        onChange={onToggle}
        className="subflow-pack-modal__port-checkbox"
      />
      <span
        className="subflow-pack-modal__port-dot"
        style={{ backgroundColor: pt.color }}
      />
      <span className="subflow-pack-modal__port-label">{port.label}</span>
      <span className="subflow-pack-modal__port-type">{pt.label}</span>
    </label>
  );
}

/**
 * 子流程打包配置弹窗。
 * 自动分析框选节点的暴露接口，让用户勾选/取消后确认打包。
 */
export default function SubflowPackModal({
  selectedNodeIds,
  allNodes,
  allEdges,
  onClose,
  onPackComplete,
}: SubflowPackModalProps) {
  const { analyzeSubflowInterface, packSubflow } = useSubflowPack();
  const { saveSubflow } = useSubflowStorage();

  const [name, setName] = useState('');
  const [desc, setDesc] = useState('');
  const [nameError, setNameError] = useState('');

  // 自动分析接口
  const rawInterface = useMemo(
    () => analyzeSubflowInterface(allNodes, allEdges, selectedNodeIds),
    [analyzeSubflowInterface, allNodes, allEdges, selectedNodeIds],
  );

  // 用户可勾选接口
  const [selectedInputs, setSelectedInputs] = useState<Set<string>>(
    () => new Set(rawInterface.inputs.map((p) => p.key)),
  );
  const [selectedOutputs, setSelectedOutputs] = useState<Set<string>>(
    () => new Set(rawInterface.outputs.map((p) => p.key)),
  );

  const toggleInput = useCallback((key: string) => {
    setSelectedInputs((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }, []);

  const toggleOutput = useCallback((key: string) => {
    setSelectedOutputs((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }, []);

  const handlePack = useCallback(() => {
    const trimmedName = name.trim();
    if (!trimmedName) {
      setNameError('请输入子流程名称');
      return;
    }
    setNameError('');

    // 构建最终接口（仅保留用户勾选的端口）
    const finalInterface: SubflowInterface = {
      inputs: rawInterface.inputs.filter((p) => selectedInputs.has(p.key)),
      outputs: rawInterface.outputs.filter((p) => selectedOutputs.has(p.key)),
    };

    const result = packSubflow(
      trimmedName,
      desc.trim(),
      allNodes,
      allEdges,
      selectedNodeIds,
      finalInterface,
    );

    saveSubflow(result.subflow);
    onPackComplete(result.newNodes, result.newEdges);
    toast('子流程已保存');
    onClose();
  }, [
    name, desc, rawInterface, selectedInputs, selectedOutputs,
    packSubflow, allNodes, allEdges, selectedNodeIds,
    saveSubflow, onPackComplete, onClose,
  ]);

  return (
    <div className="subflow-pack-modal__overlay" onClick={onClose}>
      <div
        className="subflow-pack-modal"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="subflow-pack-modal__header">
          <h2 className="subflow-pack-modal__title">打包为子流程</h2>
          <button
            className="subflow-pack-modal__close"
            onClick={onClose}
            title="关闭"
          >
            <X size={18} />
          </button>
        </div>

        {/* Body */}
        <div className="subflow-pack-modal__body">
          {/* 名称 */}
          <div className="subflow-pack-modal__field">
            <label className="subflow-pack-modal__label">
              子流程名称 <span className="subflow-pack-modal__required">*</span>
            </label>
            <input
              type="text"
              className={`subflow-pack-modal__input${nameError ? ' subflow-pack-modal__input--error' : ''}`}
              placeholder="输入子流程名称"
              value={name}
              onChange={(e) => {
                setName(e.target.value);
                if (nameError) setNameError('');
              }}
              autoFocus
            />
            {nameError && (
              <span className="subflow-pack-modal__error">{nameError}</span>
            )}
          </div>

          {/* 描述 */}
          <div className="subflow-pack-modal__field">
            <label className="subflow-pack-modal__label">描述</label>
            <textarea
              className="subflow-pack-modal__textarea"
              placeholder="输入子流程描述（选填）"
              value={desc}
              onChange={(e) => setDesc(e.target.value)}
              rows={2}
            />
          </div>

          {/* 接口预览 */}
          <div className="subflow-pack-modal__interface-section">
            {rawInterface.inputs.length > 0 && (
              <div className="subflow-pack-modal__interface-group">
                <h4 className="subflow-pack-modal__interface-title">
                  输入接口 ({selectedInputs.size}/{rawInterface.inputs.length})
                </h4>
                <div className="subflow-pack-modal__port-list">
                  {rawInterface.inputs.map((port) => (
                    <PortItem
                      key={port.key}
                      port={port}
                      checked={selectedInputs.has(port.key)}
                      onToggle={() => toggleInput(port.key)}
                    />
                  ))}
                </div>
              </div>
            )}

            {rawInterface.outputs.length > 0 && (
              <div className="subflow-pack-modal__interface-group">
                <h4 className="subflow-pack-modal__interface-title">
                  输出接口 ({selectedOutputs.size}/{rawInterface.outputs.length})
                </h4>
                <div className="subflow-pack-modal__port-list">
                  {rawInterface.outputs.map((port) => (
                    <PortItem
                      key={port.key}
                      port={port}
                      checked={selectedOutputs.has(port.key)}
                      onToggle={() => toggleOutput(port.key)}
                    />
                  ))}
                </div>
              </div>
            )}

            {rawInterface.inputs.length === 0 && rawInterface.outputs.length === 0 && (
              <div className="subflow-pack-modal__no-ports">
                未检测到需要暴露的接口端口
              </div>
            )}
          </div>
        </div>

        {/* Footer */}
        <div className="subflow-pack-modal__footer">
          <button
            className="subflow-pack-modal__btn subflow-pack-modal__btn--cancel"
            onClick={onClose}
          >
            取消
          </button>
          <button
            className="subflow-pack-modal__btn subflow-pack-modal__btn--confirm"
            onClick={handlePack}
            disabled={!name.trim()}
          >
            确认打包
          </button>
        </div>
      </div>
    </div>
  );
}

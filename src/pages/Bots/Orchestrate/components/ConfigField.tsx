import { useMemo } from 'react';
import type { ConfigFieldDef } from '../types/orchestrate';
import './ConfigField.css';

interface ConfigFieldProps {
  field: ConfigFieldDef;
  value: string | number | undefined;
  onChange: (key: string, value: string | number) => void;
}

/**
 * 动态表单字段渲染组件。
 * 根据 fieldType 渲染不同控件：
 * - text → input[type=text]
 * - textarea → textarea
 * - select → select + option
 * - number → input[type=number]
 * - note → 只读灰色提示
 */
export default function ConfigField({ field, value, onChange }: ConfigFieldProps) {
  const currentValue = value ?? field.default ?? '';

  function handleChange(val: string | number) {
    onChange(field.key, val);
  }

  // note 类型：只读提示
  if (field.fieldType === 'note') {
    return (
      <div className="config-field">
        <label className="config-field__label">
          {field.label}
        </label>
        <p className="config-field__note">{field.placeholder}</p>
      </div>
    );
  }

  // text
  if (field.fieldType === 'text') {
    return (
      <div className="config-field">
        <label className="config-field__label">
          {field.label}
          {field.required && <span className="config-field__required">*</span>}
        </label>
        <input
          type="text"
          className="config-field__input"
          value={String(currentValue)}
          placeholder={field.placeholder}
          onChange={(e) => handleChange(e.target.value)}
        />
      </div>
    );
  }

  // textarea（含变量引用高亮预览）
  if (field.fieldType === 'textarea') {
    const text = String(currentValue);
    const varMatches = useMemo(() => {
      const matches: Array<{ start: number; end: number; text: string }> = [];
      const re = /\{([^}]+)\}/g;
      let m: RegExpExecArray | null;
      while ((m = re.exec(text)) !== null) {
        matches.push({ start: m.index, end: m.index + m[0].length, text: m[1] });
      }
      return matches;
    }, [text]);

    return (
      <div className="config-field">
        <label className="config-field__label">
          {field.label}
          {field.required && <span className="config-field__required">*</span>}
        </label>
        <textarea
          className="config-field__textarea"
          value={text}
          placeholder={field.placeholder}
          rows={3}
          onChange={(e) => handleChange(e.target.value)}
        />
        {varMatches.length > 0 && (
          <div className="config-field__var-preview">
            <span className="config-field__var-preview-label">检测到变量引用：</span>
            {varMatches.map((m, i) => (
              <span key={i} className="config-field__var-tag">
                {`{${m.text}}`}
              </span>
            ))}
          </div>
        )}
      </div>
    );
  }

  // number
  if (field.fieldType === 'number') {
    return (
      <div className="config-field">
        <label className="config-field__label">
          {field.label}
          {field.required && <span className="config-field__required">*</span>}
        </label>
        <input
          type="number"
          className="config-field__input"
          value={currentValue === '' ? '' : Number(currentValue)}
          placeholder={field.placeholder}
          onChange={(e) => {
            const val = e.target.value;
            handleChange(val === '' ? '' : Number(val));
          }}
        />
      </div>
    );
  }

  // select
  if (field.fieldType === 'select') {
    return (
      <div className="config-field">
        <label className="config-field__label">
          {field.label}
          {field.required && <span className="config-field__required">*</span>}
        </label>
        <select
          className="config-field__select"
          value={String(currentValue)}
          onChange={(e) => handleChange(e.target.value)}
        >
          {field.options?.map((opt) => (
            <option key={opt} value={opt}>
              {opt}
            </option>
          ))}
        </select>
      </div>
    );
  }

  return null;
}

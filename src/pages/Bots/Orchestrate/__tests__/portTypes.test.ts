import { describe, it, expect } from 'vitest';
import { canConnectTypes, getPortType, PORT_TYPES } from '../data/portTypes';

describe('canConnectTypes', () => {
  describe('相同类型可连接', () => {
    it('string ↔ string 允许', () => {
      expect(canConnectTypes('string', 'string')).toBe(true);
    });

    it('number ↔ number 允许', () => {
      expect(canConnectTypes('number', 'number')).toBe(true);
    });

    it('boolean ↔ boolean 允许', () => {
      expect(canConnectTypes('boolean', 'boolean')).toBe(true);
    });

    it('chatHistory ↔ chatHistory 允许', () => {
      expect(canConnectTypes('chatHistory', 'chatHistory')).toBe(true);
    });

    it('knowledgeRef ↔ knowledgeRef 允许', () => {
      expect(canConnectTypes('knowledgeRef', 'knowledgeRef')).toBe(true);
    });

    it('property ↔ property 允许', () => {
      expect(canConnectTypes('property', 'property')).toBe(true);
    });

    it('any ↔ any 允许', () => {
      expect(canConnectTypes('any', 'any')).toBe(true);
    });
  });

  describe('any 可连接任意类型', () => {
    it('any → string 允许（源为 any）', () => {
      expect(canConnectTypes('any', 'string')).toBe(true);
    });

    it('string → any 允许（目标为 any）', () => {
      expect(canConnectTypes('string', 'any')).toBe(true);
    });

    it('any → number 允许', () => {
      expect(canConnectTypes('any', 'number')).toBe(true);
    });

    it('number → any 允许', () => {
      expect(canConnectTypes('number', 'any')).toBe(true);
    });

    it('any → boolean 允许', () => {
      expect(canConnectTypes('any', 'boolean')).toBe(true);
    });

    it('boolean → any 允许', () => {
      expect(canConnectTypes('boolean', 'any')).toBe(true);
    });

    it('any → chatHistory 允许', () => {
      expect(canConnectTypes('any', 'chatHistory')).toBe(true);
    });

    it('any → knowledgeRef 允许', () => {
      expect(canConnectTypes('any', 'knowledgeRef')).toBe(true);
    });

    it('any → property 允许', () => {
      expect(canConnectTypes('any', 'property')).toBe(true);
    });
  });

  describe('不同类型不可连接', () => {
    it('string → number 不允许', () => {
      expect(canConnectTypes('string', 'number')).toBe(false);
    });

    it('number → string 不允许', () => {
      expect(canConnectTypes('number', 'string')).toBe(false);
    });

    it('boolean → string 不允许', () => {
      expect(canConnectTypes('boolean', 'string')).toBe(false);
    });

    it('chatHistory → string 不允许', () => {
      expect(canConnectTypes('chatHistory', 'string')).toBe(false);
    });

    it('knowledgeRef → chatHistory 不允许', () => {
      expect(canConnectTypes('knowledgeRef', 'chatHistory')).toBe(false);
    });

    it('property → boolean 不允许', () => {
      expect(canConnectTypes('property', 'boolean')).toBe(false);
    });

    it('number → chatHistory 不允许', () => {
      expect(canConnectTypes('number', 'chatHistory')).toBe(false);
    });
  });
});

describe('getPortType', () => {
  it('返回已知类型的正确信息', () => {
    const info = getPortType('string');
    expect(info).toEqual(PORT_TYPES.string);
    expect(info.label).toBe('字符串');
    expect(info.color).toBe('#3b82f6');
  });

  it('未知类型回退到 any', () => {
    const info = getPortType('unknown_type');
    expect(info).toEqual(PORT_TYPES.any);
    expect(info.label).toBe('任意');
    expect(info.color).toBe('#eab308');
  });
});

describe('PORT_TYPES', () => {
  it('包含全部 7 种端口类型', () => {
    const keys = Object.keys(PORT_TYPES);
    expect(keys).toHaveLength(7);
    expect(keys).toContain('string');
    expect(keys).toContain('number');
    expect(keys).toContain('boolean');
    expect(keys).toContain('chatHistory');
    expect(keys).toContain('knowledgeRef');
    expect(keys).toContain('any');
    expect(keys).toContain('property');
  });
});

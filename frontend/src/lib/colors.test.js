import { describe, it, expect } from 'vitest';
import { LABEL_COLORS, getLabelStyle } from './colors';

describe('Taxonomy Highlight Colors', () => {
  const expectedLabels = [
    'Claim',
    'Evidence',
    'Definition',
    'Method',
    'Result',
    'Problem',
    'Solution',
  ];

  it('defines distinct color styles for all taxonomy labels', () => {
    expectedLabels.forEach((label) => {
      const style = LABEL_COLORS[label];
      expect(style).toBeDefined();
      expect(style.bg).toMatch(/^#[0-9a-fA-F]{6}$/);
      expect(style.border).toMatch(/^#[0-9a-fA-F]{6}$/);
      expect(style.highlight).toMatch(/^#[0-9a-fA-F]{6}$/);
      expect(style.badge).toBeDefined();
    });
  });

  it('assigns unique background and border accents across labels', () => {
    const backgrounds = new Set(expectedLabels.map((l) => LABEL_COLORS[l].bg));
    const borders = new Set(expectedLabels.map((l) => LABEL_COLORS[l].border));

    // Every taxonomy label should have a unique distinct background tint and border
    expect(backgrounds.size).toBe(expectedLabels.length);
    expect(borders.size).toBe(expectedLabels.length);
  });

  it('returns default style for unknown or null label', () => {
    const defaultNull = getLabelStyle(null);
    expect(defaultNull).toBeDefined();
    expect(defaultNull.bg).toBe('#F3F4F6');

    const defaultUnknown = getLabelStyle('NonExistent');
    expect(defaultUnknown).toEqual(defaultNull);
  });
});


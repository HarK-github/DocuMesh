import { describe, it, expect } from 'vitest';
import {
  findTextOffsets,
  normalizeWhitespace,
  mapOffsetsToSpans,
  mapAnnotationToPages,
} from './offsets';

describe('offsets library', () => {
  const sampleCleanText =
    'Can machines think?\n\n' +
    'The new form of the problem can be described in terms of a game which we call the imitation game.\n\n' +
    'Digital computers can simulate any discrete state machine.';

  it('normalizes various whitespace configurations', () => {
    expect(normalizeWhitespace('  hello   \n\t  world  ')).toBe('hello world');
    expect(normalizeWhitespace('')).toBe('');
  });

  it('finds exact offsets for single-line selections', () => {
    const selection = 'Can machines think?';
    const result = findTextOffsets(sampleCleanText, selection);
    expect(result).not.toBeNull();
    expect(result.start).toBe(0);
    expect(result.end).toBe(19);
    expect(result.quote).toBe('Can machines think?');
    expect(sampleCleanText.slice(result.start, result.end)).toBe(result.quote);
  });

  it('finds offsets across line breaks and collapsed whitespace', () => {
    const multiLineSelection = 'terms of a game\nwhich we call';
    const result = findTextOffsets(sampleCleanText, multiLineSelection);
    expect(result).not.toBeNull();
    expect(result.quote).toContain('terms of a game');
    expect(result.quote).toContain('which we call');
    expect(sampleCleanText.slice(result.start, result.end)).toBe(result.quote);
  });

  it('returns null when selected text is not present in clean_text', () => {
    const result = findTextOffsets(sampleCleanText, 'Quantum teleporters are fast');
    expect(result).toBeNull();
  });

  it('maps an offset interval to multi-span highlights across multiple elements', () => {
    const spans = [
      { id: 's1', start: 0, end: 20, text: 'Can machines think? ' },
      { id: 's2', start: 20, end: 60, text: 'The new form of the problem can be ' },
      { id: 's3', start: 60, end: 120, text: 'described in terms of a game which we call.' },
    ];

    // Select text crossing s1 into s2
    const mapped = mapOffsetsToSpans(10, 40, spans);
    expect(mapped).toHaveLength(2);
    expect(mapped[0].spanId).toBe('s1');
    expect(mapped[0].localStart).toBe(10);
    expect(mapped[0].localEnd).toBe(20);
    expect(mapped[0].text).toBe('es think? ');

    expect(mapped[1].spanId).toBe('s2');
    expect(mapped[1].localStart).toBe(0);
    expect(mapped[1].localEnd).toBe(20);
    expect(mapped[1].text).toBe('The new form of the ');
  });

  it('maps annotation offsets to correct page boundaries', () => {
    const pages = [
      { page: 1, start: 0, end: 100 },
      { page: 2, start: 102, end: 250 },
    ];

    // Annotation completely inside page 1
    const p1Match = mapAnnotationToPages(10, 50, pages);
    expect(p1Match).toEqual([{ page: 1, start: 10, end: 50 }]);

    // Annotation spanning page 1 and page 2
    const crossMatch = mapAnnotationToPages(80, 150, pages);
    expect(crossMatch).toHaveLength(2);
    expect(crossMatch[0]).toEqual({ page: 1, start: 80, end: 100 });
    expect(crossMatch[1]).toEqual({ page: 2, start: 102, end: 150 });
  });
});

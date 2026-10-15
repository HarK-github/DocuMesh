import { describe, it, expect } from 'vitest';
import {
  findTextOffsets,
  normalizeWhitespace,
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
});


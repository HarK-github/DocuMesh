import { describe, it, expect } from 'vitest';
import {
  createSegments,
  splitSegmentsIntoParagraphs,
  computeSelectionOffsetsFromDom,
} from './segments';

describe('createSegments', () => {
  it('returns empty array for empty or null text', () => {
    expect(createSegments('')).toEqual([]);
    expect(createSegments(null)).toEqual([]);
    expect(createSegments(undefined)).toEqual([]);
  });

  it('returns a single unchanged segment when there are no annotations or suggestions', () => {
    const text = 'Hello world, this is a plain document.';
    const segments = createSegments(text, [], []);
    expect(segments).toHaveLength(1);
    expect(segments[0]).toMatchObject({
      start: 0,
      end: text.length,
      text: text,
      annotationIds: [],
      suggestionIds: [],
    });
  });

  it('handles edges at 0 and at text length', () => {
    const text = 'Start to Middle to End';
    // 'Start' is [0, 5], 'End' is [19, 22]
    const annotations = [
      { id: 'a1', start: 0, end: 5, label: 'Claim' },
      { id: 'a2', start: 19, end: 22, label: 'Evidence' },
    ];
    const segments = createSegments(text, annotations, []);

    expect(segments).toHaveLength(3);
    expect(segments[0]).toMatchObject({
      start: 0,
      end: 5,
      text: 'Start',
      annotationIds: ['a1'],
      suggestionIds: [],
    });
    expect(segments[1]).toMatchObject({
      start: 5,
      end: 19,
      text: ' to Middle to ',
      annotationIds: [],
      suggestionIds: [],
    });
    expect(segments[2]).toMatchObject({
      start: 19,
      end: 22,
      text: 'End',
      annotationIds: ['a2'],
      suggestionIds: [],
    });

    const reconstructed = segments.map((s) => s.text).join('');
    expect(reconstructed).toBe(text);
  });

  it('handles adjacent ranges without gaps or overlaps', () => {
    const text = 'FirstSecondThird';
    const annotations = [
      { id: 'a1', start: 0, end: 5, label: 'Claim' },
      { id: 'a2', start: 5, end: 11, label: 'Method' },
    ];
    const segments = createSegments(text, annotations, []);

    expect(segments).toHaveLength(3);
    expect(segments[0].text).toBe('First');
    expect(segments[0].annotationIds).toEqual(['a1']);
    expect(segments[1].text).toBe('Second');
    expect(segments[1].annotationIds).toEqual(['a2']);
    expect(segments[2].text).toBe('Third');
    expect(segments[2].annotationIds).toEqual([]);
    expect(segments.map((s) => s.text).join('')).toBe(text);
  });

  it('handles overlapping ranges correctly', () => {
    const text = 'The quick brown fox jumps over the lazy dog';
    // 'quick brown' is [4, 15]
    // 'brown fox' is [10, 19]
    const annotations = [
      { id: 'a1', start: 4, end: 15, label: 'Claim' },
      { id: 'a2', start: 10, end: 19, label: 'Evidence' },
    ];
    const segments = createSegments(text, annotations, []);

    // Cut points: 0, 4, 10, 15, 19, 43
    expect(segments).toHaveLength(5);
    expect(segments[0]).toMatchObject({ start: 0, end: 4, text: 'The ', annotationIds: [] });
    expect(segments[1]).toMatchObject({ start: 4, end: 10, text: 'quick ', annotationIds: ['a1'] });
    expect(segments[2]).toMatchObject({ start: 10, end: 15, text: 'brown', annotationIds: ['a1', 'a2'] });
    expect(segments[3]).toMatchObject({ start: 15, end: 19, text: ' fox', annotationIds: ['a2'] });
    expect(segments[4]).toMatchObject({ start: 19, end: 43, text: ' jumps over the lazy dog', annotationIds: [] });
    expect(segments.map((s) => s.text).join('')).toBe(text);
  });

  it('handles nested ranges correctly', () => {
    const text = 'Machines can simulate any discrete state machine.';
    // Outer: 'simulate any discrete state machine' [13, 48]
    // Inner: 'discrete state' [26, 40]
    const annotations = [
      { id: 'outer', start: 13, end: 48, label: 'Claim' },
      { id: 'inner', start: 26, end: 40, label: 'Definition' },
    ];
    const segments = createSegments(text, annotations, []);

    // Cut points: 0, 13, 26, 40, 48, 49
    expect(segments).toHaveLength(5);
    expect(segments[0].text).toBe('Machines can ');
    expect(segments[0].annotationIds).toEqual([]);

    expect(segments[1].text).toBe('simulate any ');
    expect(segments[1].annotationIds).toEqual(['outer']);

    expect(segments[2].text).toBe('discrete state');
    expect(segments[2].annotationIds).toEqual(['outer', 'inner']);

    expect(segments[3].text).toBe(' machine');
    expect(segments[3].annotationIds).toEqual(['outer']);

    expect(segments[4].text).toBe('.');
    expect(segments[4].annotationIds).toEqual([]);
    expect(segments.map((s) => s.text).join('')).toBe(text);
  });

  it('handles annotations and suggestions coexisting and overlapping', () => {
    const text = 'Testing pending suggestions alongside confirmed annotations.';
    const annotations = [
      { id: 'a1', start: 8, end: 27 }, // 'pending suggestions'
    ];
    const suggestions = [
      { id: 's1', start: 16, end: 37 }, // 'suggestions alongside'
    ];
    const segments = createSegments(text, annotations, suggestions);

    expect(segments).toHaveLength(5);
    expect(segments[0].text).toBe('Testing ');
    expect(segments[1].text).toBe('pending ');
    expect(segments[1].annotationIds).toEqual(['a1']);
    expect(segments[1].suggestionIds).toEqual([]);

    expect(segments[2].text).toBe('suggestions');
    expect(segments[2].annotationIds).toEqual(['a1']);
    expect(segments[2].suggestionIds).toEqual(['s1']);

    expect(segments[3].text).toBe(' alongside');
    expect(segments[3].annotationIds).toEqual([]);
    expect(segments[3].suggestionIds).toEqual(['s1']);

    expect(segments.map((s) => s.text).join('')).toBe(text);
  });
});

describe('splitSegmentsIntoParagraphs', () => {
  it('splits segments on double newlines while preserving correct offsets', () => {
    const text = 'Paragraph one.\n\nParagraph two is here.\n\nParagraph three.';
    const annotations = [
      { id: 'a1', start: 0, end: 9, label: 'Claim' }, // 'Paragraph'
      { id: 'a2', start: 16, end: 29, label: 'Evidence' }, // 'Paragraph two'
    ];
    const segments = createSegments(text, annotations, []);
    const paragraphs = splitSegmentsIntoParagraphs(segments);

    expect(paragraphs).toHaveLength(3);
    // Paragraph 1
    expect(paragraphs[0][0].text).toBe('Paragraph');
    expect(paragraphs[0][0].start).toBe(0);
    expect(paragraphs[0][0].end).toBe(9);
    expect(paragraphs[0][1].text).toBe(' one.');
    expect(paragraphs[0][1].start).toBe(9);
    expect(paragraphs[0][1].end).toBe(14);

    // Paragraph 2
    expect(paragraphs[1][0].text).toBe('Paragraph two');
    expect(paragraphs[1][0].start).toBe(16);
    expect(paragraphs[1][0].end).toBe(29);
    expect(paragraphs[1][1].text).toBe(' is here.');

    // Paragraph 3
    expect(paragraphs[2][0].text).toBe('Paragraph three.');
  });
});

describe('computeSelectionOffsetsFromDom', () => {
  function createMockDomElement(dataStart, textContent) {
    const el = {
      dataset: { start: String(dataStart) },
      getAttribute: (attr) => (attr === 'data-start' ? String(dataStart) : null),
      textContent: textContent,
      closest: (sel) => (sel === '[data-start]' ? el : null),
    };
    const textNode = {
      nodeType: 3,
      textContent: textContent,
      parentElement: el,
      previousSibling: null,
    };
    el.childNodes = [textNode];
    return { el, textNode };
  }

  const cleanText =
    'The imitation game is played with three people.\n\n' +
    'Digital computers are discrete state machines.';

  it('computes selection offsets inside one segment', () => {
    // Inside first segment: start=0, text='The imitation game is played with three people.'
    const { textNode } = createMockDomElement(0, 'The imitation game is played with three people.');
    // User selects 'imitation' -> offset 4 to 13
    const mockRange = {
      startContainer: textNode,
      startOffset: 4,
      endContainer: textNode,
      endOffset: 13,
    };

    const res = computeSelectionOffsetsFromDom(mockRange, cleanText);
    expect(res).not.toBeNull();
    expect(res.start).toBe(4);
    expect(res.end).toBe(13);
    expect(res.quote).toBe('imitation');
  });

  it('computes selection offsets across several segments', () => {
    // Segment 1: start=0, 'The '
    // Segment 2: start=4, 'imitation '
    // Segment 3: start=14, 'game'
    const seg1 = createMockDomElement(0, 'The ');
    const seg2 = createMockDomElement(4, 'imitation ');
    const seg3 = createMockDomElement(14, 'game');

    // Select from index 1 of seg1 ('he ') through index 2 of seg3 ('ga')
    const mockRange = {
      startContainer: seg1.textNode,
      startOffset: 1, // 'he ' -> abs 1
      endContainer: seg3.textNode,
      endOffset: 2,   // 'ga' -> abs 14 + 2 = 16
    };

    const res = computeSelectionOffsetsFromDom(mockRange, cleanText);
    expect(res).not.toBeNull();
    expect(res.start).toBe(1);
    expect(res.end).toBe(16);
    expect(res.quote).toBe(cleanText.slice(1, 16));
  });

  it('computes selection offsets across paragraph breaks', () => {
    // Para 1 end segment: start=34, text='three people.'
    // Para 2 start segment: start=49, text='Digital computers'
    const segP1 = createMockDomElement(34, 'three people.');
    const segP2 = createMockDomElement(49, 'Digital computers');

    // Selection starts in 'people.' (offset 6) and ends in 'computers' (offset 7)
    // 34 + 6 = 40 ('people.\n\nDigital')
    // 49 + 7 = 56
    const mockRange = {
      startContainer: segP1.textNode,
      startOffset: 6,
      endContainer: segP2.textNode,
      endOffset: 7,
    };

    const res = computeSelectionOffsetsFromDom(mockRange, cleanText);
    expect(res).not.toBeNull();
    expect(res.start).toBe(40);
    expect(res.end).toBe(56);
    expect(res.quote).toBe(cleanText.slice(40, 56));
  });

  it('handles reversed selection bounds safely', () => {
    const { textNode } = createMockDomElement(0, 'The imitation game');
    const mockRange = {
      startContainer: textNode,
      startOffset: 13,
      endContainer: textNode,
      endOffset: 4,
    };

    const res = computeSelectionOffsetsFromDom(mockRange, cleanText);
    expect(res).not.toBeNull();
    expect(res.start).toBe(4);
    expect(res.end).toBe(13);
    expect(res.quote).toBe('imitation');
  });

  it('returns null if selection is collapsed or outside data-start elements', () => {
    const mockRange = {
      startContainer: { nodeType: 1, closest: () => null },
      startOffset: 0,
      endContainer: { nodeType: 1, closest: () => null },
      endOffset: 0,
    };
    expect(computeSelectionOffsetsFromDom(mockRange, cleanText)).toBeNull();
  });
});

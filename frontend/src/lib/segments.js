/**
 * Segment helper for rendering inline highlights over clean_text.
 *
 * Given cleanText, annotations, and pending suggestions, produces an ordered
 * list of non-overlapping text segments covering the entire text.
 */

/**
 * Creates an ordered list of non-overlapping text segments.
 *
 * @param {string} cleanText - The raw document clean text.
 * @param {Array<{ id: string|number, start: number, end: number }>} [annotations=[]]
 * @param {Array<{ id: string|number, start: number, end: number }>} [suggestions=[]]
 * @returns {Array<{
 *   start: number,
 *   end: number,
 *   text: string,
 *   annotationIds: Array<string|number>,
 *   suggestionIds: Array<string|number>,
 *   annotations: Array<object>,
 *   suggestions: Array<object>
 * }>}
 */
export function createSegments(cleanText, annotations = [], suggestions = []) {
  if (!cleanText || typeof cleanText !== 'string' || cleanText.length === 0) {
    return [];
  }

  const length = cleanText.length;
  const cuts = new Set([0, length]);

  const validAnnotations = (annotations || []).filter(
    (a) => a && typeof a.start === 'number' && typeof a.end === 'number' && a.start < a.end
  );

  const validSuggestions = (suggestions || []).filter(
    (s) => s && typeof s.start === 'number' && typeof s.end === 'number' && s.start < s.end
  );

  // Add boundary points for all annotations and suggestions clamped to [0, length]
  for (const ann of validAnnotations) {
    const s = Math.max(0, Math.min(length, ann.start));
    const e = Math.max(0, Math.min(length, ann.end));
    if (s < e) {
      cuts.add(s);
      cuts.add(e);
    }
  }

  for (const sug of validSuggestions) {
    const s = Math.max(0, Math.min(length, sug.start));
    const e = Math.max(0, Math.min(length, sug.end));
    if (s < e) {
      cuts.add(s);
      cuts.add(e);
    }
  }

  const sortedCuts = Array.from(cuts).sort((a, b) => a - b);
  const segments = [];

  for (let i = 0; i < sortedCuts.length - 1; i++) {
    const segStart = sortedCuts[i];
    const segEnd = sortedCuts[i + 1];
    if (segStart >= segEnd) continue;

    const coveringAnns = validAnnotations.filter(
      (a) => a.start <= segStart && a.end >= segEnd
    );
    const coveringSugs = validSuggestions.filter(
      (s) => s.start <= segStart && s.end >= segEnd
    );

    segments.push({
      start: segStart,
      end: segEnd,
      text: cleanText.slice(segStart, segEnd),
      annotationIds: coveringAnns.map((a) => a.id),
      suggestionIds: coveringSugs.map((s) => s.id),
      annotations: coveringAnns,
      suggestions: coveringSugs,
    });
  }

  return segments;
}

/**
 * Splits segments into paragraphs based on blank lines (\n\n or \r\n\r\n) in cleanText.
 * Preserves exact start and end offsets on all child segments.
 *
 * @param {Array} segments - Output of createSegments
 * @returns {Array<Array<object>>} - Array of paragraphs, each containing an array of segments
 */
export function splitSegmentsIntoParagraphs(segments) {
  if (!segments || segments.length === 0) return [];

  const paragraphs = [];
  let currentParagraph = [];

  for (const seg of segments) {
    const text = seg.text;
    // Check if the segment contains paragraph breaks (two or more newlines)
    const parts = text.split(/(\r?\n\s*\r?\n+)/);

    if (parts.length === 1) {
      currentParagraph.push(seg);
    } else {
      let offset = seg.start;
      for (let pIdx = 0; pIdx < parts.length; pIdx++) {
        const partText = parts[pIdx];
        const partStart = offset;
        const partEnd = offset + partText.length;
        offset = partEnd;

        if (!partText) continue;

        const isBreak = /^\r?\n\s*\r?\n+$/.test(partText);
        if (isBreak) {
          if (currentParagraph.length > 0) {
            paragraphs.push(currentParagraph);
            currentParagraph = [];
          }
        } else {
          currentParagraph.push({
            ...seg,
            start: partStart,
            end: partEnd,
            text: partText,
          });
        }
      }
    }
  }

  if (currentParagraph.length > 0) {
    paragraphs.push(currentParagraph);
  }

  return paragraphs.length > 0 ? paragraphs : [[]];
}

/**
 * Computes character offset within an enclosing element by summing text lengths
 * of preceding siblings of the container node.
 */
export function getOffsetWithinSegment(container, offset) {
  if (!container) return 0;
  // Node.TEXT_NODE = 3
  if (container.nodeType === 3) {
    let current = container.previousSibling;
    let charsBefore = 0;
    while (current) {
      charsBefore += current.textContent ? current.textContent.length : 0;
      current = current.previousSibling;
    }
    return charsBefore + (offset || 0);
  }

  // If container is an Element
  let charsBefore = 0;
  if (container.childNodes) {
    for (let i = 0; i < offset && i < container.childNodes.length; i++) {
      charsBefore += container.childNodes[i].textContent?.length || 0;
    }
  }
  return charsBefore;
}

/**
 * Computes exact start and end offsets in cleanText from a DOM Selection Range
 * using `data-start` attributes on segment elements.
 *
 * @param {Range} range - DOM Selection Range
 * @param {string} cleanText - Canonical clean text of document
 * @returns {{ start: number, end: number, quote: string } | null}
 */
export function computeSelectionOffsetsFromDom(range, cleanText) {
  if (!range || !cleanText) return null;

  const getElement = (node) => {
    if (!node) return null;
    return node.nodeType === 3 ? node.parentElement : node;
  };

  const startContainerEl = getElement(range.startContainer);
  const endContainerEl = getElement(range.endContainer);

  const startEl = startContainerEl?.closest ? startContainerEl.closest('[data-start]') : null;
  const endEl = endContainerEl?.closest ? endContainerEl.closest('[data-start]') : null;

  if (!startEl || !endEl) {
    return null;
  }

  const startAttr = startEl.getAttribute ? startEl.getAttribute('data-start') : startEl.dataset?.start;
  const endAttr = endEl.getAttribute ? endEl.getAttribute('data-start') : endEl.dataset?.start;

  if (startAttr === null || startAttr === undefined || endAttr === null || endAttr === undefined) {
    return null;
  }

  const startBase = parseInt(startAttr, 10);
  const endBase = parseInt(endAttr, 10);

  if (Number.isNaN(startBase) || Number.isNaN(endBase)) {
    return null;
  }

  const startLocal = getOffsetWithinSegment(range.startContainer, range.startOffset);
  const endLocal = getOffsetWithinSegment(range.endContainer, range.endOffset);

  let start = startBase + startLocal;
  let end = endBase + endLocal;

  if (start > end) {
    const tmp = start;
    start = end;
    end = tmp;
  }

  if (start >= end) return null;

  const clampedStart = Math.max(0, Math.min(cleanText.length, start));
  const clampedEnd = Math.max(0, Math.min(cleanText.length, end));

  if (clampedStart >= clampedEnd) return null;

  return {
    start: clampedStart,
    end: clampedEnd,
    quote: cleanText.slice(clampedStart, clampedEnd),
  };
}

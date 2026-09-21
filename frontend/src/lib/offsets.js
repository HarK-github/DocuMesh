/**
 * Utility functions for mapping text selections to character offsets in clean_text
 * and mapping stored offsets back to highlight spans and pages.
 */

/**
 * Normalize whitespace by collapsing multiple spaces and linebreaks to single space.
 */
export function normalizeWhitespace(str) {
  if (!str) return '';
  return str.replace(/\s+/g, ' ').trim();
}

/**
 * Find exact character start and end offsets in cleanText for a user selection.
 * Handles exact matches as well as selections across linebreaks/varying whitespace.
 *
 * @param {string} cleanText - The document's canonical clean text.
 * @param {string} selectionText - The raw selected text string.
 * @param {number} hintOffset - Optional start index to prefer local matches.
 * @returns {{ start: number, end: number, quote: string } | null}
 */
export function findTextOffsets(cleanText, selectionText, hintOffset = 0) {
  if (!cleanText || !selectionText) return null;

  const rawTrimmed = selectionText.trim();
  if (!rawTrimmed) return null;

  // 1. Try exact match from hint offset
  let exactIdx = cleanText.indexOf(rawTrimmed, hintOffset);
  if (exactIdx === -1 && hintOffset > 0) {
    exactIdx = cleanText.indexOf(rawTrimmed);
  }

  if (exactIdx !== -1) {
    const end = exactIdx + rawTrimmed.length;
    return {
      start: exactIdx,
      end,
      quote: cleanText.slice(exactIdx, end),
    };
  }

  // 2. Fuzzy whitespace match for multi-line or whitespace-mismatched selections
  const normalizedSelection = normalizeWhitespace(rawTrimmed);
  // Build a regex matching the words separated by arbitrary whitespace
  const words = normalizedSelection
    .split(' ')
    .filter(Boolean)
    .map((w) => w.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'));

  if (words.length === 0) return null;

  const pattern = new RegExp(words.join('\\s+'), 'g');
  pattern.lastIndex = Math.max(0, hintOffset - 50);

  let match = pattern.exec(cleanText);
  if (!match) {
    pattern.lastIndex = 0;
    match = pattern.exec(cleanText);
  }

  if (match) {
    const start = match.index;
    const end = start + match[0].length;
    return {
      start,
      end,
      quote: cleanText.slice(start, end),
    };
  }

  return null;
}

/**
 * Map document character offsets [start, end] onto a collection of text spans.
 * Useful for rendering multi-span highlights across paragraphs, lines, or elements.
 *
 * @param {number} start - Target start offset in document.
 * @param {number} end - Target end offset in document.
 * @param {Array<{ id: string|number, start: number, end: number, text: string }>} spans - Spans list.
 * @returns {Array<{ spanId: string|number, localStart: number, localEnd: number, text: string }>}
 */
export function mapOffsetsToSpans(start, end, spans) {
  if (start >= end || !Array.isArray(spans)) return [];

  const results = [];
  for (const span of spans) {
    // Check if interval [start, end] intersects [span.start, span.end]
    const overlapStart = Math.max(start, span.start);
    const overlapEnd = Math.min(end, span.end);

    if (overlapStart < overlapEnd) {
      results.push({
        spanId: span.id,
        localStart: overlapStart - span.start,
        localEnd: overlapEnd - span.start,
        text: span.text.slice(overlapStart - span.start, overlapEnd - span.start),
      });
    }
  }

  return results;
}

/**
 * Determine which pages contain portions of an offset range and compute local page offsets.
 *
 * @param {number} start - Absolute start offset.
 * @param {number} end - Absolute end offset.
 * @param {Array<{ page: number, start: number, end: number }>} pages - Page offset ranges.
 * @returns {Array<{ page: number, start: number, end: number }>}
 */
export function mapAnnotationToPages(start, end, pages) {
  if (!pages || !pages.length) return [];
  const matched = [];

  for (const p of pages) {
    if (start < p.end && end > p.start) {
      matched.push({
        page: p.page,
        start: Math.max(start, p.start),
        end: Math.min(end, p.end),
      });
    }
  }

  return matched;
}

// Named frontend constants for smart highlight behavior

export const CATEGORY_SCOPE_ANNOTATION_THRESHOLD = 3;

/**
 * Determine the default suggestion scope.
 * Defaults to "category" when the label already has at least 3 annotations,
 * and to "passage" otherwise.
 *
 * @param {string} label
 * @param {Array<object>} annotations
 * @param {number} threshold
 * @returns {'passage' | 'category'}
 */
export function getDefaultSuggestionScope(
  label,
  annotations = [],
  threshold = CATEGORY_SCOPE_ANNOTATION_THRESHOLD
) {
  if (!label) return 'passage';
  const count = (annotations || []).filter((a) => a.label === label).length;
  return count >= threshold ? 'category' : 'passage';
}

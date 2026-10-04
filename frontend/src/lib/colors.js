/**
 * Unified taxonomy color configuration for DocuMesh.
 * Used across ReaderView, GraphView, and Annotation panels.
 */

export const LABEL_COLORS = {
  Claim: {
    bg: '#eff6ff',
    border: '#60a5fa',
    text: '#1e40af',
    badge: '#dbeafe',
  },
  Evidence: {
    bg: '#ecfdf5',
    border: '#34d399',
    text: '#065f46',
    badge: '#d1fae5',
  },
  Definition: {
    bg: '#fefce8',
    border: '#facc15',
    text: '#854d0e',
    badge: '#fef9c3',
  },
  Method: {
    bg: '#f5f3ff',
    border: '#a78bfa',
    text: '#5b21b6',
    badge: '#ede9fe',
  },
  Result: {
    bg: '#fff1f2',
    border: '#fb7185',
    text: '#9f1239',
    badge: '#ffe4e6',
  },
  Problem: {
    bg: '#fef2f2',
    border: '#f87171',
    text: '#991b1b',
    badge: '#fee2e2',
  },
  Solution: {
    bg: '#f0fdfa',
    border: '#2dd4bf',
    text: '#115e59',
    badge: '#ccfbf1',
  },
};

const DEFAULT_LABEL_COLOR = {
  bg: '#f8fafc',
  border: '#94a3b8',
  text: '#334155',
  badge: '#e2e8f0',
};

export function getLabelStyle(label) {
  if (!label) return DEFAULT_LABEL_COLOR;
  return LABEL_COLORS[label] || DEFAULT_LABEL_COLOR;
}

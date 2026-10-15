/**
 * Minimalist Monochrome Taxonomy Configuration for DocuMesh.
 * Adheres strictly to the pure black & white (#000000, #FFFFFF, #525252, #E5E5E5) palette.
 * Distinguishes labels through editorial typography, line weights, and contrasting badge fills.
 */

export const LABEL_COLORS = {
  Claim: {
    bg: '#FFF9C4',
    border: '#F59E0B',
    highlight: '#F59E0B',
    text: '#000000',
    badge: '#F59E0B',
    badgeText: '#000000',
    borderWidth: '2px',
    borderStyle: 'solid',
  },
  Evidence: {
    bg: '#E0F2FE',
    border: '#0284C7',
    highlight: '#0284C7',
    text: '#000000',
    badge: '#0284C7',
    badgeText: '#ffffff',
    borderWidth: '2px',
    borderStyle: 'solid',
  },
  Definition: {
    bg: '#F3E8FF',
    border: '#7E22CE',
    highlight: '#7E22CE',
    text: '#000000',
    badge: '#7E22CE',
    badgeText: '#ffffff',
    borderWidth: '2px',
    borderStyle: 'solid',
  },
  Method: {
    bg: '#DCFCE7',
    border: '#15803D',
    highlight: '#15803D',
    text: '#000000',
    badge: '#15803D',
    badgeText: '#ffffff',
    borderWidth: '2px',
    borderStyle: 'solid',
  },
  Result: {
    bg: '#FFEDD5',
    border: '#C2410C',
    highlight: '#C2410C',
    text: '#000000',
    badge: '#C2410C',
    badgeText: '#ffffff',
    borderWidth: '2px',
    borderStyle: 'solid',
  },
  Problem: {
    bg: '#FEE2E2',
    border: '#B91C1C',
    highlight: '#B91C1C',
    text: '#000000',
    badge: '#B91C1C',
    badgeText: '#ffffff',
    borderWidth: '2px',
    borderStyle: 'solid',
  },
  Solution: {
    bg: '#CCFBF1',
    border: '#0F766E',
    highlight: '#0F766E',
    text: '#000000',
    badge: '#0F766E',
    badgeText: '#ffffff',
    borderWidth: '2px',
    borderStyle: 'solid',
  },
};

const DEFAULT_LABEL_COLOR = {
  bg: '#F3F4F6',
  border: '#4B5563',
  highlight: '#4B5563',
  text: '#000000',
  badge: '#4B5563',
  badgeText: '#ffffff',
  borderWidth: '2px',
  borderStyle: 'solid',
};

export function getLabelStyle(label) {
  if (!label) return DEFAULT_LABEL_COLOR;
  return LABEL_COLORS[label] || DEFAULT_LABEL_COLOR;
}

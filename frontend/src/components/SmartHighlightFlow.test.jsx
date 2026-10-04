import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import { getDefaultSuggestionScope, CATEGORY_SCOPE_ANNOTATION_THRESHOLD } from '../config';
import ReaderView, { SelectionPopover } from './ReaderView';
import SuggestionList from './SuggestionList';

describe('Part E: Smart Highlight Flow and Controls', () => {
  describe('Scope default logic (config.js)', () => {
    it('uses threshold of 3', () => {
      expect(CATEGORY_SCOPE_ANNOTATION_THRESHOLD).toBe(3);
    });

    it('defaults to "passage" when label has fewer than 3 annotations', () => {
      const annotations = [
        { id: 1, label: 'Claim' },
        { id: 2, label: 'Claim' },
        { id: 3, label: 'Evidence' },
      ];
      expect(getDefaultSuggestionScope('Claim', annotations)).toBe('passage');
    });

    it('defaults to "category" when label has 3 or more annotations', () => {
      const annotations = [
        { id: 1, label: 'Claim' },
        { id: 2, label: 'Claim' },
        { id: 3, label: 'Claim' },
      ];
      expect(getDefaultSuggestionScope('Claim', annotations)).toBe('category');
    });

    it('defaults to "passage" for null, undefined, or empty labels', () => {
      expect(getDefaultSuggestionScope('', [])).toBe('passage');
      expect(getDefaultSuggestionScope(null, [])).toBe('passage');
    });
  });

  describe('SelectionPopover component', () => {
    const defaultProps = {
      popoverPos: { top: 120, left: 80 },
      selectionRange: { start: 10, end: 45, quote: 'Important statement in text' },
      selectedLabel: 'Claim',
      onLabelChange: vi.fn(),
      scope: 'passage',
      onScopeChange: vi.fn(),
      note: 'My note',
      onNoteChange: vi.fn(),
      taxonomy: { labels: ['Claim', 'Evidence', 'Method'] },
      isMutating: false,
      onSave: vi.fn(),
      onSaveAndFindMore: vi.fn(),
      onClose: vi.fn(),
    };

    it('renders category dropdown, note input, scope toggle, and action buttons', () => {
      const html = renderToStaticMarkup(<SelectionPopover {...defaultProps} />);

      expect(html).toContain('New Annotation');
      expect(html).toContain('Category');
      expect(html).toContain('Claim');
      expect(html).toContain('Evidence');
      expect(html).toContain('Note (optional)');
      expect(html).toContain('This passage');
      expect(html).toContain('This category');
      expect(html).toContain('Save');
      expect(html).toContain('Save + find more like this');
    });

    it('disables save buttons when isMutating is true', () => {
      const html = renderToStaticMarkup(<SelectionPopover {...defaultProps} isMutating={true} />);

      expect(html).toContain('disabled');
      expect(html).toContain('opacity:0.6');
    });

    it('calls onSave and onSaveAndFindMore handlers when buttons are clicked', () => {
      const onSave = vi.fn();
      const onSaveAndFindMore = vi.fn();

      const element = SelectionPopover({
        ...defaultProps,
        onSave,
        onSaveAndFindMore,
      });

      // Find form and buttons
      const form = element.props.children[1];
      const buttonContainer = form.props.children[form.props.children.length - 1];
      const [saveBtn, saveAndFindBtn] = buttonContainer.props.children;

      saveBtn.props.onClick();
      expect(onSave).toHaveBeenCalled();

      saveAndFindBtn.props.onClick();
      expect(onSaveAndFindMore).toHaveBeenCalled();
    });

    it('calls onScopeChange when scope buttons are clicked', () => {
      const onScopeChange = vi.fn();
      const element = SelectionPopover({
        ...defaultProps,
        onScopeChange,
      });

      const form = element.props.children[1];
      const scopeGroup = form.props.children[2];
      const [passageBtn, categoryBtn] = scopeGroup.props.children[1].props.children;

      passageBtn.props.onClick();
      expect(onScopeChange).toHaveBeenCalledWith('passage');

      categoryBtn.props.onClick();
      expect(onScopeChange).toHaveBeenCalledWith('category');
    });
  });

  describe('ReaderView "Accept all shown"', () => {
    it('renders "Accept all shown" button when pending suggestions exist with visible count', () => {
      const onAcceptAllSuggestions = vi.fn();
      const suggestions = [
        { id: 101, status: 'pending', start: 0, end: 10, quote: 'First', score: 0.8 },
        { id: 102, status: 'pending', start: 20, end: 30, quote: 'Second', score: 0.75 },
        { id: 103, status: 'accepted', start: 40, end: 50, quote: 'Third', score: 0.9 },
      ];

      const html = renderToStaticMarkup(
        <ReaderView
          documentId={1}
          cleanText="First sentence. Second sentence. Third sentence."
          annotations={[]}
          suggestions={suggestions}
          onAcceptAllSuggestions={onAcceptAllSuggestions}
        />
      );

      expect(html).toContain('data-testid="reader-accept-all-btn"');
      expect(html).toContain('Accept all shown (2)');
    });
  });

  describe('SuggestionList controls, empty state, and pending-cap alert', () => {
    it('renders clear empty state message when no pending suggestions exist', () => {
      const html = renderToStaticMarkup(
        <SuggestionList suggestions={[]} onAccept={() => {}} onReject={() => {}} />
      );

      expect(html).toContain('No more similar passages found');
      expect(html).toContain('Select text to create an annotation');
    });

    it('renders pending cap alert when message is returned or pending reaches cap', () => {
      const capMessage =
        'Maximum pending suggestions reached for this seed (10). Please accept or reject existing suggestions.';
      const suggestionsWithMsg = [
        {
          id: 1,
          status: 'pending',
          score: 0.85,
          quote: 'Sample passage',
          message: capMessage,
        },
      ];

      const html = renderToStaticMarkup(
        <SuggestionList
          suggestions={suggestionsWithMsg}
          onAccept={() => {}}
          onReject={() => {}}
        />
      );

      expect(html).toContain('Maximum pending suggestions reached');
      expect(html).toContain(capMessage);
    });

    it('renders "Accept all shown" button and calls onAcceptAll with pending IDs only', () => {
      const onAcceptAll = vi.fn();
      const suggestions = [
        { id: 11, status: 'pending', score: 0.88, quote: 'Pending 1' },
        { id: 12, status: 'pending', score: 0.82, quote: 'Pending 2' },
        { id: 13, status: 'rejected', score: 0.65, quote: 'Rejected 1' },
      ];

      const element = SuggestionList({
        suggestions,
        onAcceptAll,
      });

      // Header is first child
      const header = element.props.children[0];
      const headerActions = header.props.children[1];
      const acceptAllBtn = headerActions.props.children[0];

      expect(acceptAllBtn.props['data-testid']).toBe('accept-all-shown-btn');
      acceptAllBtn.props.onClick();

      expect(onAcceptAll).toHaveBeenCalledWith([11, 12]);
    });
  });
});

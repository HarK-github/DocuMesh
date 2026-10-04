import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import { CitationChip } from './ChatPanel';

describe('CitationChip component', () => {
  it('renders a sentence citation chip with [s...] badge and annotate button', () => {
    const citation = { type: 'sentence', id: 42, start: 10, end: 50 };
    const html = renderToStaticMarkup(
      <CitationChip
        citation={citation}
        onJumpToRange={() => {}}
        onSaveSentenceAnnotation={() => {}}
      />
    );

    expect(html).toContain('[s42] Sentence');
    expect(html).toContain('Annotate');
  });

  it('renders an annotation citation chip with [a...] badge', () => {
    const citation = { type: 'annotation', id: 7, start: 100, end: 150 };
    const html = renderToStaticMarkup(
      <CitationChip
        citation={citation}
        onSelectAnnotation={() => {}}
      />
    );

    expect(html).toContain('[a7] Annotation');
    // Does not offer annotate button for annotations
    expect(html).not.toContain('Annotate');
  });

  it('renders a relation citation chip with [r...] badge', () => {
    const citation = { type: 'relation', id: 15 };
    const html = renderToStaticMarkup(
      <CitationChip
        citation={citation}
        onSelectRelation={() => {}}
      />
    );

    expect(html).toContain('[r15] Relation');
  });

  it('triggers jump and select callbacks when clicked', () => {
    const onSelectAnnotation = vi.fn();
    const onJumpToRange = vi.fn();
    const citation = { type: 'annotation', id: 12, start: 50, end: 80 };

    // Instantiate element and simulate click by executing onClick handler
    const element = CitationChip({
      citation,
      onSelectAnnotation,
      onJumpToRange,
    });

    // Find the main button child
    const mainButton = element.props.children[0];
    mainButton.props.onClick();

    expect(onSelectAnnotation).toHaveBeenCalledWith(12);
    expect(onJumpToRange).toHaveBeenCalledWith({ start: 50, end: 80 });
  });

  it('triggers save sentence annotation callback when save button is clicked', () => {
    const onSaveSentenceAnnotation = vi.fn();
    const citation = { type: 'sentence', id: 99, start: 0, end: 25 };

    const element = CitationChip({
      citation,
      onSaveSentenceAnnotation,
    });

    const saveButton = element.props.children[1];
    saveButton.props.onClick({ stopPropagation: () => {} });

    expect(onSaveSentenceAnnotation).toHaveBeenCalledWith(citation);
  });
});

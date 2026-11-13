import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import { CitationChip, renderMessageWithCitations } from './ChatPanel';

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

  it('triggers jump and select callbacks for relation citation with evidence range', () => {
    const onSelectRelation = vi.fn();
    const onJumpToRange = vi.fn();
    const citation = { type: 'relation', id: 5, start: 120, end: 180 };

    const element = CitationChip({
      citation,
      onSelectRelation,
      onJumpToRange,
    });

    const mainButton = element.props.children[0];
    mainButton.props.onClick();

    expect(onSelectRelation).toHaveBeenCalledWith(5);
    expect(onJumpToRange).toHaveBeenCalledWith({ start: 120, end: 180 });
  });

  it('renders a chunk citation chip with [c...] badge and triggers jump callback', () => {
    const onJumpToRange = vi.fn();
    const citation = { type: 'chunk', id: 124, start: 200, end: 400 };

    const html = renderToStaticMarkup(
      <CitationChip
        citation={citation}
        onJumpToRange={onJumpToRange}
      />
    );

    expect(html).toContain('[c124] Chunk');

    const element = CitationChip({
      citation,
      onJumpToRange,
    });
    const mainButton = element.props.children[0];
    mainButton.props.onClick();

    expect(onJumpToRange).toHaveBeenCalledWith({ start: 200, end: 400 });
  });
});

describe('renderMessageWithCitations', () => {
  it('parses inline citations and renders clickable buttons without converting filenames into links', () => {
    const content = 'The imitation game is defined here [c124] and replaces original question [a89]. See chat_context.py for details.';
    const citations = [
      { type: 'chunk', id: 124, start: 0, end: 200 },
      { type: 'annotation', id: 89, start: 50, end: 120 },
    ];
    const elements = renderMessageWithCitations(content, citations, {});
    const html = renderToStaticMarkup(<span>{elements}</span>);

    expect(html).toContain('[c124]');
    expect(html).toContain('[a89]');
    expect(html).toContain('chat_context.py');
    // chat_context.py is pure text, NOT inside a button or anchor
    expect(html).not.toContain('<a href="chat_context.py"');
    expect(html).not.toContain('<button>chat_context.py</button>');
  });
});

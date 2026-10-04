import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import PdfViewer from './PdfViewer';

describe('PdfViewer component', () => {
  it('renders "No document selected." when documentId is missing', () => {
    const html = renderToStaticMarkup(<PdfViewer documentId={null} />);
    expect(html).toContain('No document selected.');
  });

  it('renders toolbar with highlights toggle, zoom controls, and export links', () => {
    const html = renderToStaticMarkup(
      <PdfViewer
        documentId={1}
        annotationsCount={3}
        cleanText="This is test text."
        taxonomy={{ labels: ['Problem', 'Solution', 'Claim'] }}
      />
    );

    expect(html).toContain('PDF Document');
    expect(html).toContain('Highlights: ON (3)');
    expect(html).toContain('Zoom In');
    expect(html).toContain('Zoom Out');
    expect(html).toContain('Download');
    expect(html).toContain('Open in Tab');
  });

  it('renders with custom annotations and mutation callbacks without crashing', () => {
    const onCreateAnnotation = vi.fn();
    const onSaveAndFindMore = vi.fn();

    const html = renderToStaticMarkup(
      <PdfViewer
        documentId={2}
        annotationsCount={5}
        cleanText="Some clean document text here"
        annotations={[{ id: 1, label: 'Problem', quote: 'clean document' }]}
        taxonomy={{ labels: ['Problem', 'Solution'] }}
        onCreateAnnotation={onCreateAnnotation}
        onSaveAndFindMore={onSaveAndFindMore}
      />
    );

    expect(html).toContain('Highlights: ON (5)');
  });
});

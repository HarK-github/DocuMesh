import React, { useState, useEffect, useRef } from 'react';
import {
  FileText,
  ExternalLink,
  Download,
  Highlighter,
  ZoomIn,
  ZoomOut,
  RotateCcw,
  AlertCircle,
  Loader2,
  Bookmark,
} from 'lucide-react';
import { pdfjsLib } from '../lib/pdfjs';
import { API_BASE } from '../api/client';
import { findTextOffsets } from '../lib/offsets';
import { getDefaultSuggestionScope } from '../config';
import SelectionPopover from './SelectionPopover';

function PdfPage({ pdfDoc, pageNumber, scale }) {
  const canvasRef = useRef(null);
  const textLayerRef = useRef(null);
  const renderTaskRef = useRef(null);
  const [pageSize, setPageSize] = useState(null);

  useEffect(() => {
    let cancelled = false;

    async function renderPage() {
      if (!pdfDoc) return;
      try {
        const page = await pdfDoc.getPage(pageNumber);
        if (cancelled) return;

        const viewport = page.getViewport({ scale });
        setPageSize({
          width: Math.floor(viewport.width),
          height: Math.floor(viewport.height),
        });

        const canvas = canvasRef.current;
        if (!canvas || !canvas.getContext) return;

        const pixelRatio = typeof window !== 'undefined' ? window.devicePixelRatio || 1 : 1;
        canvas.width = Math.floor(viewport.width * pixelRatio);
        canvas.height = Math.floor(viewport.height * pixelRatio);
        canvas.style.width = `${Math.floor(viewport.width)}px`;
        canvas.style.height = `${Math.floor(viewport.height)}px`;

        const ctx = canvas.getContext('2d');
        if (renderTaskRef.current) {
          renderTaskRef.current.cancel();
        }

        const renderContext = {
          canvasContext: ctx,
          viewport: viewport,
          transform: pixelRatio !== 1 ? [pixelRatio, 0, 0, pixelRatio, 0, 0] : null,
        };

        const task = page.render(renderContext);
        renderTaskRef.current = task;
        await task.promise;
        if (cancelled) return;

        // Render text layer
        const textLayerDiv = textLayerRef.current;
        if (textLayerDiv && pdfjsLib.TextLayer) {
          textLayerDiv.innerHTML = '';
          textLayerDiv.style.width = `${Math.floor(viewport.width)}px`;
          textLayerDiv.style.height = `${Math.floor(viewport.height)}px`;
          textLayerDiv.style.setProperty('--scale-factor', `${scale}`);
          textLayerDiv.style.setProperty('--total-scale-factor', `${scale}`);

          const textContent = await page.getTextContent();
          if (cancelled) return;

          const textLayer = new pdfjsLib.TextLayer({
            textContentSource: textContent,
            container: textLayerDiv,
            viewport: viewport,
          });
          await textLayer.render();
        }
      } catch (err) {
        if (err?.name !== 'RenderingCancelledException') {
          console.error(`Page ${pageNumber} rendering error:`, err);
        }
      }
    }

    renderPage();

    return () => {
      cancelled = true;
      if (renderTaskRef.current) {
        renderTaskRef.current.cancel();
      }
    };
  }, [pdfDoc, pageNumber, scale]);

  return (
    <div
      id={`pdf-page-${pageNumber}`}
      data-page-number={pageNumber}
      className="page"
      style={{
        position: 'relative',
        margin: '0 auto 24px auto',
        boxShadow: 'none',
        background: '#ffffff',
        borderRadius: 0,
        border: '1px solid #000000',
        overflow: 'hidden',
        width: pageSize ? `${pageSize.width}px` : 'fit-content',
        height: pageSize ? `${pageSize.height}px` : 'auto',
        '--scale-factor': `${scale}`,
        '--total-scale-factor': `${scale}`,
      }}
    >
      <canvas ref={canvasRef} style={{ display: 'block' }} />
      <div
        ref={textLayerRef}
        className="textLayer"
        style={{
          position: 'absolute',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          pointerEvents: 'auto',
          userSelect: 'text',
          WebkitUserSelect: 'text',
          '--scale-factor': `${scale}`,
          '--total-scale-factor': `${scale}`,
        }}
      />
    </div>
  );
}

export default function PdfViewer({
  documentId,
  annotationsCount = 0,
  cleanText = '',
  annotations = [],
  suggestions = [],
  taxonomy = { labels: [] },
  selectedAnnotationId = null,
  onSelectAnnotation = () => {},
  onCreateAnnotation = () => {},
  onSaveAndFindMore = () => {},
  onAcceptSuggestion = () => {},
  onRejectSuggestion = () => {},
  onAcceptAllSuggestions = () => {},
  scrollToAnnotationId = null,
  isMutating = false,
}) {
  const [pdfDoc, setPdfDoc] = useState(null);
  const [numPages, setNumPages] = useState(0);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState(null);
  const [scale, setScale] = useState(1.15);
  const [showHighlights, setShowHighlights] = useState(true);

  // Selection & Popover state
  const containerRef = useRef(null);
  const popoverRef = useRef(null);
  const [selectionRange, setSelectionRange] = useState(null);
  const [selectedLabel, setSelectedLabel] = useState('');
  const [scope, setScope] = useState('passage');
  const [note, setNote] = useState('');
  const [popoverPos, setPopoverPos] = useState(null);

  // Set default selected label when taxonomy loads
  useEffect(() => {
    if (taxonomy?.labels?.length && !selectedLabel) {
      const initial = taxonomy.labels[0];
      setSelectedLabel(initial);
      setScope(getDefaultSuggestionScope(initial, annotations));
    }
  }, [taxonomy, selectedLabel, annotations]);

  // Close popup on Escape or click outside
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') {
        clearSelection();
      }
    };
    const handleClickOutside = (e) => {
      if (popoverRef.current && !popoverRef.current.contains(e.target)) {
        clearSelection();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    document.addEventListener('mousedown', handleClickOutside);
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, []);

  // Fetch and load PDF bytes via PDF.js
  useEffect(() => {
    if (!documentId) {
      setPdfDoc(null);
      setNumPages(0);
      return;
    }

    let active = true;
    setLoading(true);
    setLoadError(null);

    const pdfUrl = `${API_BASE}/documents/${documentId}/pdf?annotated=${showHighlights}&v=${annotationsCount}`;

    async function loadPdf() {
      try {
        const resp = await fetch(pdfUrl);
        if (!resp.ok) {
          throw new Error(`Failed to load PDF (${resp.status})`);
        }
        const data = await resp.arrayBuffer();
        if (!active) return;

        const loadingTask = pdfjsLib.getDocument({
          data,
          cMapUrl: 'https://cdn.jsdelivr.net/npm/pdfjs-dist@5.6.205/cmaps/',
          cMapPacked: true,
        });

        const doc = await loadingTask.promise;
        if (!active) return;

        setPdfDoc(doc);
        setNumPages(doc.numPages);
        setLoading(false);
      } catch (err) {
        if (!active) return;
        console.error('PDF loading error:', err);
        setLoadError(err.message || 'Error loading PDF document');
        setLoading(false);
      }
    }

    loadPdf();

    return () => {
      active = false;
    };
  }, [documentId, showHighlights, annotationsCount]);

  // Scroll to annotation when clicked in Graph
  useEffect(() => {
    if (!scrollToAnnotationId || !annotations?.length || !pdfDoc) return;
    const targetAnn = annotations.find((a) => a.id === scrollToAnnotationId);
    if (!targetAnn || !targetAnn.quote) return;

    async function locatePage() {
      for (let p = 1; p <= pdfDoc.numPages; p++) {
        try {
          const page = await pdfDoc.getPage(p);
          const tc = await page.getTextContent();
          const pageText = tc.items.map((it) => it.str).join(' ');
          if (pageText.toLowerCase().includes(targetAnn.quote.trim().toLowerCase().slice(0, 30))) {
            const pageEl = document.getElementById(`pdf-page-${p}`);
            if (pageEl) {
              pageEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
            }
            break;
          }
        } catch {
          // ignore
        }
      }
    }
    locatePage();
  }, [scrollToAnnotationId, annotations, pdfDoc]);

  // Handle user mouse-up selection on the PDF text layer
  const handleMouseUp = (e) => {
    const selection = window.getSelection();
    if (!selection || selection.isCollapsed) return;

    const rawStr = selection.toString().trim();
    if (!rawStr || rawStr.length < 1) return;

    let matched = cleanText ? findTextOffsets(cleanText, rawStr) : null;
    if (!matched) {
      matched = { start: 0, end: rawStr.length, quote: rawStr };
    }

    const range = selection.rangeCount > 0 ? selection.getRangeAt(0) : null;
    if (!range) return;

    let rect = range.getBoundingClientRect();
    if (!rect || (rect.width === 0 && rect.height === 0)) {
      const clientRects = range.getClientRects();
      if (clientRects.length > 0) {
        rect = clientRects[0];
      }
    }

    const containerRect = containerRef.current?.getBoundingClientRect() || {
      top: 0,
      left: 0,
      width: 800,
      height: 600,
    };

    const scrollTop = containerRef.current ? containerRef.current.scrollTop : 0;
    const scrollLeft = containerRef.current ? containerRef.current.scrollLeft : 0;

    const activeLabel = selectedLabel || taxonomy?.labels?.[0] || 'Claim';
    if (!selectedLabel) {
      setSelectedLabel(activeLabel);
    }

    const clientX = rect && rect.width > 0 ? rect.left + rect.width / 2 : (e?.clientX || containerRect.left + containerRect.width / 2);
    const clientY = rect && rect.bottom > 0 ? rect.bottom : (e?.clientY || containerRect.top + 100);

    setSelectionRange(matched);
    setScope(getDefaultSuggestionScope(activeLabel, annotations));
    setPopoverPos({
      top: clientY - containerRect.top + scrollTop + 8,
      left: Math.max(
        10,
        Math.min(
          clientX - containerRect.left + scrollLeft - 155,
          (containerRect.width || 800) - 325
        )
      ),
    });
  };

  const handleLabelChange = (newLabel) => {
    setSelectedLabel(newLabel);
    setScope(getDefaultSuggestionScope(newLabel, annotations));
  };

  const clearSelection = () => {
    setSelectionRange(null);
    setPopoverPos(null);
    setNote('');
    if (window.getSelection) {
      window.getSelection().removeAllRanges();
    }
  };

  const handleSave = (e) => {
    if (e) e.preventDefault();
    const activeLabel = selectedLabel || taxonomy?.labels?.[0] || 'Claim';
    if (!selectionRange || !activeLabel || isMutating) return;

    let range = selectionRange;
    if (cleanText) {
      const rematch = findTextOffsets(cleanText, selectionRange.quote);
      if (rematch) range = rematch;
    }

    onCreateAnnotation({
      start: range.start,
      end: range.end,
      quote: range.quote,
      label: activeLabel,
      note: note.trim() || null,
      x: 200 + Math.random() * 50,
      y: 150 + Math.random() * 50,
    });
    clearSelection();
  };

  const handleSaveAndFindMore = (e) => {
    if (e) e.preventDefault();
    const activeLabel = selectedLabel || taxonomy?.labels?.[0] || 'Claim';
    if (!selectionRange || !activeLabel || isMutating) return;

    let range = selectionRange;
    if (cleanText) {
      const rematch = findTextOffsets(cleanText, selectionRange.quote);
      if (rematch) range = rematch;
    }

    onSaveAndFindMore({
      start: range.start,
      end: range.end,
      quote: range.quote,
      label: activeLabel,
      note: note.trim() || null,
      scope: scope,
      x: 200 + Math.random() * 50,
      y: 150 + Math.random() * 50,
    });
    clearSelection();
  };

  const zoomIn = () => setScale((s) => Math.min(2.5, Math.round((s + 0.15) * 100) / 100));
  const zoomOut = () => setScale((s) => Math.max(0.7, Math.round((s - 0.15) * 100) / 100));
  const zoomReset = () => setScale(1.15);

  if (!documentId) {
    return (
      <div
        style={{
          height: '100%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          background: '#ffffff',
          borderRadius: 0,
          border: '1px solid #000000',
          color: '#525252',
          fontFamily: '"Source Serif 4", Georgia, serif',
          fontStyle: 'italic',
        }}
      >
        No document selected.
      </div>
    );
  }

  const pdfUrl = `${API_BASE}/documents/${documentId}/pdf?annotated=${showHighlights}&v=${annotationsCount}`;
  const downloadUrl = `${API_BASE}/documents/${documentId}/pdf?annotated=${showHighlights}`;

  return (
    <div
      style={{
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        background: '#ffffff',
        borderRadius: 0,
        border: '1px solid #000000',
        overflow: 'hidden',
        position: 'relative',
        boxShadow: 'none',
      }}
    >
      {/* Header Toolbar */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '10px 16px',
          borderBottom: '2px solid #000000',
          background: '#ffffff',
          fontSize: '0.8rem',
          color: '#000000',
          flexShrink: 0,
          gap: '10px',
          flexWrap: 'wrap',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              fontFamily: '"Playfair Display", Georgia, serif',
              fontWeight: 700,
              fontSize: '0.95rem',
            }}
          >
            <FileText size={15} strokeWidth={1.5} color="#000000" /> PDF Document
          </span>
          <button
            type="button"
            onClick={() => setShowHighlights((prev) => !prev)}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '4px',
              padding: '3px 8px',
              borderRadius: 0,
              fontSize: '0.7rem',
              fontWeight: 600,
              fontFamily: '"JetBrains Mono", monospace',
              cursor: 'pointer',
              border: '1px solid #000000',
              background: showHighlights ? '#000000' : '#ffffff',
              color: showHighlights ? '#ffffff' : '#000000',
              transition: 'none',
              textTransform: 'uppercase',
              letterSpacing: '0.04em',
            }}
            title={
              showHighlights
                ? 'Click to show raw unannotated PDF'
                : 'Click to show highlighted annotations on PDF'
            }
          >
            <Highlighter size={12} strokeWidth={1.5} color={showHighlights ? '#ffffff' : '#000000'} />
            {showHighlights
              ? `Highlights: ON (${annotationsCount})`
              : 'Highlights: OFF'}
          </button>
          {numPages > 0 && (
            <span
              style={{
                fontFamily: '"JetBrains Mono", monospace',
                fontSize: '0.7rem',
                color: '#000000',
                background: '#ffffff',
                padding: '2px 6px',
                borderRadius: 0,
                border: '1px solid #000000',
                textTransform: 'uppercase',
              }}
            >
              {numPages} {numPages === 1 ? 'page' : 'pages'}
            </span>
          )}
        </div>

        {/* Zoom & Action Controls */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              background: '#ffffff',
              border: '1px solid #000000',
              borderRadius: 0,
            }}
          >
            <button
              type="button"
              onClick={zoomOut}
              style={{
                border: 'none',
                background: 'transparent',
                cursor: 'pointer',
                color: '#000000',
                padding: '3px 6px',
                display: 'flex',
                alignItems: 'center',
              }}
              title="Zoom Out"
            >
              <ZoomOut size={13} strokeWidth={1.5} />
            </button>
            <span
              style={{
                fontFamily: '"JetBrains Mono", monospace',
                fontSize: '0.72rem',
                minWidth: '38px',
                textAlign: 'center',
                fontWeight: 600,
                color: '#000000',
                borderLeft: '1px solid #000000',
                borderRight: '1px solid #000000',
                padding: '2px 4px',
              }}
            >
              {Math.round(scale * 100)}%
            </span>
            <button
              type="button"
              onClick={zoomIn}
              style={{
                border: 'none',
                background: 'transparent',
                cursor: 'pointer',
                color: '#000000',
                padding: '3px 6px',
                display: 'flex',
                alignItems: 'center',
              }}
              title="Zoom In"
            >
              <ZoomIn size={13} strokeWidth={1.5} />
            </button>
            <button
              type="button"
              onClick={zoomReset}
              style={{
                border: 'none',
                borderLeft: '1px solid #000000',
                background: 'transparent',
                cursor: 'pointer',
                color: '#000000',
                padding: '3px 6px',
                display: 'flex',
                alignItems: 'center',
              }}
              title="Reset Zoom (Fit)"
            >
              <RotateCcw size={12} strokeWidth={1.5} />
            </button>
          </div>

          <a
            href={downloadUrl}
            download
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
              color: '#000000',
              textDecoration: 'none',
              fontFamily: '"JetBrains Mono", monospace',
              fontWeight: 600,
              fontSize: '0.72rem',
              textTransform: 'uppercase',
              letterSpacing: '0.04em',
              padding: '4px 8px',
              border: '1px solid #000000',
            }}
            title="Download PDF file"
          >
            <Download size={12} strokeWidth={1.5} />
            <span>Download</span>
          </a>
          <a
            href={pdfUrl}
            target="_blank"
            rel="noopener noreferrer"
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
              color: '#ffffff',
              background: '#000000',
              textDecoration: 'none',
              fontFamily: '"JetBrains Mono", monospace',
              fontWeight: 600,
              fontSize: '0.72rem',
              textTransform: 'uppercase',
              letterSpacing: '0.04em',
              padding: '4px 8px',
              border: '1px solid #000000',
            }}
            title="Open in new browser tab"
          >
            <span>Open in Tab</span>
            <ExternalLink size={12} strokeWidth={1.5} color="#ffffff" />
          </a>
        </div>
      </div>

      {/* Main PDF Scroll Container */}
      <div
        ref={containerRef}
        onMouseUp={handleMouseUp}
        style={{
          flex: 1,
          overflowY: 'auto',
          overflowX: 'auto',
          background: '#f5f5f5',
          padding: '24px 16px',
          position: 'relative',
        }}
      >
        {loading && (
          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              padding: '60px 0',
              color: '#000000',
              gap: '10px',
              fontFamily: '"JetBrains Mono", monospace',
            }}
          >
            <Loader2 size={24} className="spin" color="#000000" />
            <span style={{ fontSize: '0.8rem', letterSpacing: '0.04em' }}>LOADING INTERACTIVE PDF PAGES...</span>
          </div>
        )}

        {loadError && (
          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              padding: '40px 20px',
              color: '#000000',
              gap: '8px',
              fontFamily: '"JetBrains Mono", monospace',
            }}
          >
            <AlertCircle size={24} color="#000000" />
            <span style={{ fontSize: '0.85rem', fontWeight: 600 }}>{loadError}</span>
          </div>
        )}

        {!loading && !loadError && pdfDoc && (
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
            {Array.from({ length: numPages }, (_, i) => i + 1).map((pageNum) => (
              <PdfPage
                key={`${documentId}-p${pageNum}-s${scale}-h${showHighlights}-v${annotationsCount}`}
                pdfDoc={pdfDoc}
                pageNumber={pageNum}
                scale={scale}
              />
            ))}
          </div>
        )}

        {/* Floating Popover on direct PDF text selection */}
        {popoverPos && selectionRange && (
          <SelectionPopover
            popoverRef={popoverRef}
            popoverPos={popoverPos}
            selectionRange={selectionRange}
            selectedLabel={selectedLabel}
            onLabelChange={handleLabelChange}
            scope={scope}
            onScopeChange={setScope}
            note={note}
            onNoteChange={setNote}
            taxonomy={taxonomy}
            isMutating={isMutating}
            onSave={handleSave}
            onSaveAndFindMore={handleSaveAndFindMore}
            onClose={clearSelection}
          />
        )}
      </div>
    </div>
  );
}

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

  useEffect(() => {
    let cancelled = false;

    async function renderPage() {
      if (!pdfDoc) return;
      try {
        const page = await pdfDoc.getPage(pageNumber);
        if (cancelled) return;

        const viewport = page.getViewport({ scale });
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
      style={{
        position: 'relative',
        margin: '0 auto 20px auto',
        boxShadow: '0 4px 12px rgba(0,0,0,0.08), 0 1px 3px rgba(0,0,0,0.05)',
        background: '#ffffff',
        borderRadius: '4px',
        overflow: 'hidden',
        width: 'fit-content',
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
  const handleMouseUp = () => {
    const selection = window.getSelection();
    if (!selection || selection.isCollapsed) return;

    const rawStr = selection.toString().trim();
    if (!rawStr || rawStr.length < 2) return;

    let matched = cleanText ? findTextOffsets(cleanText, rawStr) : null;
    if (!matched) {
      matched = { start: 0, end: rawStr.length, quote: rawStr };
    }

    const range = selection.getRangeAt(0);
    const rect = range.getBoundingClientRect();
    const containerRect = containerRef.current?.getBoundingClientRect() || {
      top: 0,
      left: 0,
      width: 800,
    };

    const scrollTop = containerRef.current ? containerRef.current.scrollTop : 0;
    const scrollLeft = containerRef.current ? containerRef.current.scrollLeft : 0;

    setSelectionRange(matched);
    setScope(getDefaultSuggestionScope(selectedLabel, annotations));
    setPopoverPos({
      top: rect.bottom - containerRect.top + scrollTop + 8,
      left: Math.max(
        10,
        Math.min(
          rect.left - containerRect.left + scrollLeft + rect.width / 2 - 145,
          (containerRect.width || 800) - 310
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
    if (!selectionRange || !selectedLabel || isMutating) return;

    onCreateAnnotation({
      start: selectionRange.start,
      end: selectionRange.end,
      quote: selectionRange.quote,
      label: selectedLabel,
      note: note.trim() || null,
      x: 200 + Math.random() * 50,
      y: 150 + Math.random() * 50,
    });
    clearSelection();
  };

  const handleSaveAndFindMore = (e) => {
    if (e) e.preventDefault();
    if (!selectionRange || !selectedLabel || isMutating) return;

    onSaveAndFindMore({
      start: selectionRange.start,
      end: selectionRange.end,
      quote: selectionRange.quote,
      label: selectedLabel,
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
          borderRadius: '12px',
          border: '1px solid #e2e8f0',
          color: '#94a3b8',
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
        borderRadius: '12px',
        border: '1px solid #e2e8f0',
        overflow: 'hidden',
        position: 'relative',
      }}
    >
      {/* Header Toolbar */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '8px 16px',
          borderBottom: '1px solid #e2e8f0',
          background: '#f8fafc',
          fontSize: '0.8rem',
          color: '#475569',
          flexShrink: 0,
          gap: '8px',
          flexWrap: 'wrap',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{ display: 'flex', alignItems: 'center', gap: '6px', fontWeight: 600 }}>
            <FileText size={15} color="#2563eb" /> PDF Document
          </span>
          <button
            type="button"
            onClick={() => setShowHighlights((prev) => !prev)}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '4px',
              padding: '2px 8px',
              borderRadius: '9999px',
              fontSize: '0.72rem',
              fontWeight: 600,
              cursor: 'pointer',
              border: showHighlights ? '1px solid #bfdbfe' : '1px solid #cbd5e1',
              background: showHighlights ? '#eff6ff' : '#f1f5f9',
              color: showHighlights ? '#2563eb' : '#64748b',
              transition: 'all 0.15s ease',
            }}
            title={
              showHighlights
                ? 'Click to show raw unannotated PDF'
                : 'Click to show highlighted annotations on PDF'
            }
          >
            <Highlighter size={12} />
            {showHighlights
              ? `Highlights: ON (${annotationsCount})`
              : 'Highlights: OFF'}
          </button>
          {numPages > 0 && (
            <span
              style={{
                fontSize: '0.72rem',
                color: '#64748b',
                background: '#f1f5f9',
                padding: '2px 6px',
                borderRadius: '4px',
                border: '1px solid #e2e8f0',
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
              gap: '2px',
              background: '#ffffff',
              border: '1px solid #cbd5e1',
              borderRadius: '6px',
              padding: '2px',
            }}
          >
            <button
              type="button"
              onClick={zoomOut}
              style={{
                border: 'none',
                background: 'transparent',
                cursor: 'pointer',
                color: '#475569',
                padding: '2px 4px',
                display: 'flex',
                alignItems: 'center',
              }}
              title="Zoom Out"
            >
              <ZoomOut size={13} />
            </button>
            <span
              style={{
                fontSize: '0.72rem',
                minWidth: '34px',
                textAlign: 'center',
                fontWeight: 600,
                color: '#334155',
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
                color: '#475569',
                padding: '2px 4px',
                display: 'flex',
                alignItems: 'center',
              }}
              title="Zoom In"
            >
              <ZoomIn size={13} />
            </button>
            <button
              type="button"
              onClick={zoomReset}
              style={{
                border: 'none',
                background: 'transparent',
                cursor: 'pointer',
                color: '#64748b',
                padding: '2px 4px',
                display: 'flex',
                alignItems: 'center',
              }}
              title="Reset Zoom (Fit)"
            >
              <RotateCcw size={12} />
            </button>
          </div>

          <a
            href={downloadUrl}
            download
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
              color: '#64748b',
              textDecoration: 'none',
              fontWeight: 500,
              fontSize: '0.75rem',
            }}
            title="Download PDF file"
          >
            <Download size={13} />
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
              color: '#2563eb',
              textDecoration: 'none',
              fontWeight: 500,
              fontSize: '0.75rem',
            }}
            title="Open in new browser tab"
          >
            <span>Open in Tab</span>
            <ExternalLink size={12} />
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
          background: '#f1f5f9',
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
              color: '#64748b',
              gap: '8px',
            }}
          >
            <Loader2 size={24} className="spin" color="#2563eb" />
            <span style={{ fontSize: '0.85rem' }}>Loading interactive PDF pages...</span>
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
              color: '#ef4444',
              gap: '8px',
            }}
          >
            <AlertCircle size={24} />
            <span style={{ fontSize: '0.85rem', fontWeight: 500 }}>{loadError}</span>
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

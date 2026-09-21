import React, { useState, useRef, useEffect, useMemo } from 'react';
import { findTextOffsets } from '../lib/offsets';
import { Bookmark, Sparkles, Check, X, Tag, FileText } from 'lucide-react';

const LABEL_COLORS = {
  Claim: { bg: '#dbeafe', text: '#1e40af', border: '#93c5fd' },
  Evidence: { bg: '#dcfce7', text: '#15803d', border: '#86efac' },
  Definition: { bg: '#fef3c7', text: '#b45309', border: '#fcd34d' },
  Method: { bg: '#f3e8ff', text: '#6b21a8', border: '#d8b4fe' },
  Result: { bg: '#ffe4e6', text: '#be123c', border: '#fda4af' },
  Problem: { bg: '#fee2e2', text: '#b91c1c', border: '#fca5a5' },
  Solution: { bg: '#ccfbf1', text: '#0f766e', border: '#5eead4' },
};

function getLabelStyle(label) {
  return LABEL_COLORS[label] || { bg: '#f1f5f9', text: '#334155', border: '#cbd5e1' };
}

export default function PdfViewer({
  documentId,
  cleanText = '',
  annotations = [],
  suggestions = [],
  taxonomy = { labels: [] },
  selectedAnnotationId = null,
  onSelectAnnotation = () => {},
  onCreateAnnotation = () => {},
  onAcceptSuggestion = () => {},
  onRejectSuggestion = () => {},
  scrollToAnnotationId = null,
}) {
  const containerRef = useRef(null);
  const [selectionRange, setSelectionRange] = useState(null);
  const [selectedLabel, setSelectedLabel] = useState('');
  const [note, setNote] = useState('');
  const [popoverPos, setPopoverPos] = useState(null);

  // Set default selected label when taxonomy loads
  useEffect(() => {
    if (taxonomy?.labels?.length && !selectedLabel) {
      setSelectedLabel(taxonomy.labels[0]);
    }
  }, [taxonomy, selectedLabel]);

  // Handle user mouse-up selection
  const handleMouseUp = () => {
    const selection = window.getSelection();
    if (!selection || selection.isCollapsed) {
      return;
    }

    const selectedStr = selection.toString().trim();
    if (!selectedStr || selectedStr.length < 2) return;

    const matched = findTextOffsets(cleanText, selectedStr);
    if (matched) {
      const range = selection.getRangeAt(0);
      const rect = range.getBoundingClientRect();
      const containerRect = containerRef.current?.getBoundingClientRect() || { top: 0, left: 0 };

      setSelectionRange(matched);
      setPopoverPos({
        top: rect.bottom - containerRect.top + 8,
        left: Math.max(10, rect.left - containerRect.left + rect.width / 2 - 140),
      });
    }
  };

  const clearSelection = () => {
    setSelectionRange(null);
    setPopoverPos(null);
    setNote('');
    if (window.getSelection) {
      window.getSelection().removeAllRanges();
    }
  };

  const handleSaveAnnotation = (e) => {
    e.preventDefault();
    if (!selectionRange || !selectedLabel) return;

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

  // Scroll to selected annotation
  useEffect(() => {
    if (scrollToAnnotationId && containerRef.current) {
      const el = containerRef.current.querySelector(`[data-annotation-id="${scrollToAnnotationId}"]`);
      if (el) {
        el.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
    }
  }, [scrollToAnnotationId]);

  // Construct segmented text spans with inline highlights
  const renderedContent = useMemo(() => {
    if (!cleanText) return null;

    // Combine confirmed annotations and pending suggestions as highlight intervals
    const intervals = [];

    annotations.forEach((ann) => {
      intervals.push({
        type: 'annotation',
        id: ann.id,
        start: ann.start,
        end: ann.end,
        label: ann.label,
        note: ann.note,
        isSelected: ann.id === selectedAnnotationId,
      });
    });

    suggestions
      .filter((s) => s.status === 'pending')
      .forEach((s) => {
        intervals.push({
          type: 'suggestion',
          id: s.id,
          start: s.start,
          end: s.end,
          score: s.score,
          quote: s.quote,
        });
      });

    // Sort intervals by start ascending
    intervals.sort((a, b) => a.start - b.start);

    // Build non-overlapping text segments
    const elements = [];
    let cursor = 0;

    intervals.forEach((item, idx) => {
      // If interval starts beyond current cursor, push plain text segment
      if (item.start > cursor) {
        elements.push(
          <span key={`text-${cursor}`}>{cleanText.slice(cursor, item.start)}</span>
        );
        cursor = item.start;
      }

      // Avoid inverted intervals
      if (item.end <= cursor) return;

      const segmentText = cleanText.slice(cursor, item.end);
      cursor = item.end;

      if (item.type === 'annotation') {
        const style = getLabelStyle(item.label);
        elements.push(
          <mark
            key={`ann-${item.id}-${idx}`}
            data-annotation-id={item.id}
            onClick={() => onSelectAnnotation(item.id)}
            style={{
              backgroundColor: style.bg,
              color: style.text,
              borderBottom: `2px solid ${style.border}`,
              padding: '2px 4px',
              borderRadius: '4px',
              margin: '0 1px',
              cursor: 'pointer',
              fontWeight: item.isSelected ? '700' : '500',
              outline: item.isSelected ? '2px solid #2563eb' : 'none',
              transition: 'all 0.15s ease',
            }}
            title={`${item.label}${item.note ? `: ${item.note}` : ''}`}
          >
            {segmentText}
            <span
              style={{
                fontSize: '0.65rem',
                textTransform: 'uppercase',
                padding: '1px 4px',
                marginLeft: '4px',
                borderRadius: '3px',
                background: style.border,
                color: style.text,
                verticalAlign: 'middle',
              }}
            >
              {item.label}
            </span>
          </mark>
        );
      } else if (item.type === 'suggestion') {
        elements.push(
          <span
            key={`sug-${item.id}-${idx}`}
            style={{
              backgroundColor: '#fef08a40',
              border: '1px dashed #ca8a04',
              padding: '2px 4px',
              borderRadius: '4px',
              position: 'relative',
              display: 'inline',
            }}
            title={`Suggested highlight (score: ${(item.score * 100).toFixed(0)}%)`}
          >
            {segmentText}
            <span
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '2px',
                marginLeft: '4px',
                fontSize: '0.7rem',
                background: '#fef9c3',
                padding: '1px 6px',
                borderRadius: '4px',
                border: '1px solid #fde047',
              }}
            >
              <Sparkles size={11} color="#ca8a04" />
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  onAcceptSuggestion(item.id);
                }}
                style={{
                  border: 'none',
                  background: 'transparent',
                  cursor: 'pointer',
                  color: '#16a34a',
                  padding: '1px',
                }}
                title="Accept suggestion"
              >
                <Check size={12} />
              </button>
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  onRejectSuggestion(item.id);
                }}
                style={{
                  border: 'none',
                  background: 'transparent',
                  cursor: 'pointer',
                  color: '#dc2626',
                  padding: '1px',
                }}
                title="Reject suggestion"
              >
                <X size={12} />
              </button>
            </span>
          </span>
        );
      }
    });

    if (cursor < cleanText.length) {
      elements.push(
        <span key={`text-end-${cursor}`}>{cleanText.slice(cursor)}</span>
      );
    }

    return elements;
  }, [cleanText, annotations, suggestions, selectedAnnotationId, onSelectAnnotation, onAcceptSuggestion, onRejectSuggestion]);

  return (
    <div
      ref={containerRef}
      onMouseUp={handleMouseUp}
      style={{
        position: 'relative',
        height: '100%',
        overflowY: 'auto',
        background: '#ffffff',
        padding: '2rem 2.5rem',
        borderRadius: '12px',
        border: '1px solid #e2e8f0',
        boxShadow: '0 1px 3px rgba(0,0,0,0.05)',
        lineHeight: 1.8,
        fontSize: '1.05rem',
        color: '#1e293b',
        whiteSpace: 'pre-wrap',
        fontFamily: "'Inter', system-ui, sans-serif",
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '1.5rem', borderBottom: '1px solid #f1f5f9', paddingBottom: '0.75rem' }}>
        <FileText size={18} color="#64748b" />
        <span style={{ fontSize: '0.9rem', fontWeight: 600, color: '#475569', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
          Document Text Layer
        </span>
        <span style={{ marginLeft: 'auto', fontSize: '0.8rem', color: '#94a3b8' }}>
          Select any text passage to annotate
        </span>
      </div>

      <div style={{ userSelect: 'text' }}>
        {renderedContent || <p style={{ color: '#94a3b8' }}>No text available to display.</p>}
      </div>

      {/* Floating Annotation Popover on text selection */}
      {popoverPos && selectionRange && (
        <div
          style={{
            position: 'absolute',
            top: `${popoverPos.top}px`,
            left: `${popoverPos.left}px`,
            zIndex: 50,
            background: '#ffffff',
            borderRadius: '10px',
            boxShadow: '0 10px 25px -5px rgba(0,0,0,0.15), 0 8px 10px -6px rgba(0,0,0,0.1)',
            border: '1px solid #e2e8f0',
            padding: '12px 14px',
            width: '280px',
            animation: 'fadeIn 0.15s ease-out',
          }}
          onMouseDown={(e) => e.stopPropagation()}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
            <span style={{ fontSize: '0.8rem', fontWeight: 600, color: '#334155', display: 'flex', alignItems: 'center', gap: '4px' }}>
              <Bookmark size={13} color="#2563eb" /> New Annotation
            </span>
            <button
              onClick={clearSelection}
              type="button"
              style={{ border: 'none', background: 'transparent', cursor: 'pointer', color: '#94a3b8' }}
            >
              <X size={14} />
            </button>
          </div>

          <form onSubmit={handleSaveAnnotation}>
            <div style={{ marginBottom: '8px' }}>
              <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: 500, color: '#64748b', marginBottom: '3px' }}>
                Label
              </label>
              <select
                value={selectedLabel}
                onChange={(e) => setSelectedLabel(e.target.value)}
                style={{
                  width: '100%',
                  padding: '5px 8px',
                  borderRadius: '6px',
                  border: '1px solid #cbd5e1',
                  fontSize: '0.85rem',
                  background: '#f8fafc',
                }}
              >
                {taxonomy?.labels?.map((lbl) => (
                  <option key={lbl} value={lbl}>
                    {lbl}
                  </option>
                ))}
              </select>
            </div>

            <div style={{ marginBottom: '10px' }}>
              <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: 500, color: '#64748b', marginBottom: '3px' }}>
                Note (optional)
              </label>
              <input
                type="text"
                value={note}
                onChange={(e) => setNote(e.target.value)}
                placeholder="Brief explanation..."
                style={{
                  width: '100%',
                  padding: '5px 8px',
                  borderRadius: '6px',
                  border: '1px solid #cbd5e1',
                  fontSize: '0.85rem',
                  boxSizing: 'border-box',
                }}
              />
            </div>

            <div style={{ display: 'flex', gap: '6px', justifyContent: 'flex-end' }}>
              <button
                type="button"
                onClick={clearSelection}
                style={{
                  padding: '5px 10px',
                  borderRadius: '6px',
                  border: '1px solid #e2e8f0',
                  background: '#ffffff',
                  fontSize: '0.8rem',
                  cursor: 'pointer',
                  color: '#64748b',
                }}
              >
                Cancel
              </button>
              <button
                type="submit"
                style={{
                  padding: '5px 12px',
                  borderRadius: '6px',
                  border: 'none',
                  background: '#2563eb',
                  color: '#ffffff',
                  fontSize: '0.8rem',
                  fontWeight: 500,
                  cursor: 'pointer',
                }}
              >
                Save
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}

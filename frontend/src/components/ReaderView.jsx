import React, { useState, useRef, useEffect, useMemo } from 'react';
import {
  Bookmark,
  Sparkles,
  Check,
  X,
  FileText,
  Layers,
} from 'lucide-react';
import {
  createSegments,
  splitSegmentsIntoParagraphs,
  computeSelectionOffsetsFromDom,
} from '../lib/segments';
import { findTextOffsets } from '../lib/offsets';
import { getLabelStyle } from '../lib/colors';
import { getDefaultSuggestionScope } from '../config';
import SelectionPopover from './SelectionPopover';

export default function ReaderView({
  documentId,
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
  flashRange = null,
  isMutating = false,
}) {
  const containerRef = useRef(null);
  const popoverRef = useRef(null);
  const [selectionRange, setSelectionRange] = useState(null);
  const [selectedLabel, setSelectedLabel] = useState('');
  const [scope, setScope] = useState('passage');
  const [note, setNote] = useState('');
  const [popoverPos, setPopoverPos] = useState(null);
  const [activeFlashId, setActiveFlashId] = useState(null);
  const [activeFlashRange, setActiveFlashRange] = useState(null);

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

  // Handle graph selection -> scroll and flash in Reader
  useEffect(() => {
    if (!scrollToAnnotationId || !containerRef.current) return;

    setActiveFlashId(scrollToAnnotationId);
    const timer = setTimeout(() => setActiveFlashId(null), 1800);

    const el = containerRef.current.querySelector(
      `[data-annotation-id="${scrollToAnnotationId}"], [data-suggestion-id="${scrollToAnnotationId}"]`
    );
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }

    return () => clearTimeout(timer);
  }, [scrollToAnnotationId]);

  // Handle flashRange from citation clicks
  useEffect(() => {
    if (!flashRange || !containerRef.current) return;

    setActiveFlashRange(flashRange);
    const timer = setTimeout(() => setActiveFlashRange(null), 1800);

    // Find the first segment element that intersects flashRange
    const segEls = containerRef.current.querySelectorAll('[data-start]');
    for (const el of segEls) {
      const segStart = parseInt(el.getAttribute('data-start'), 10);
      const segEnd = parseInt(el.getAttribute('data-end'), 10);
      if (segStart < flashRange.end && segEnd > flashRange.start) {
        el.scrollIntoView({ behavior: 'smooth', block: 'center' });
        break;
      }
    }

    return () => clearTimeout(timer);
  }, [flashRange]);

  // Handle user mouse-up selection
  const handleMouseUp = () => {
    const selection = window.getSelection();
    if (!selection || selection.isCollapsed) return;

    const selectedStr = selection.toString().trim();
    if (!selectedStr || selectedStr.length < 2) return;

    const range = selection.getRangeAt(0);
    // 1. Try DOM data-start based computation
    let matched = computeSelectionOffsetsFromDom(range, cleanText);

    // 2. Fallback to text offset finder if DOM traversal failed
    if (!matched) {
      matched = findTextOffsets(cleanText, selectedStr);
    }

    if (matched) {
      const rect = range.getBoundingClientRect();
      const containerRect = containerRef.current?.getBoundingClientRect() || {
        top: 0,
        left: 0,
      };

      setSelectionRange(matched);
      setScope(getDefaultSuggestionScope(selectedLabel, annotations));
      setPopoverPos({
        top: rect.bottom - containerRect.top + 8,
        left: Math.max(10, rect.left - containerRect.left + rect.width / 2 - 140),
      });
    }
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

  const handleSaveAnnotation = (e) => {
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

  // Filter pending suggestions
  const pendingSuggestions = useMemo(() => {
    return (suggestions || []).filter((s) => s.status === 'pending');
  }, [suggestions]);

  // Build segmented paragraphs
  const paragraphs = useMemo(() => {
    if (!cleanText) return [];
    const segments = createSegments(cleanText, annotations, pendingSuggestions);
    return splitSegmentsIntoParagraphs(segments);
  }, [cleanText, annotations, pendingSuggestions]);

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
        lineHeight: 1.85,
        fontSize: '1.02rem',
        color: '#1e293b',
        fontFamily: "'Inter', system-ui, -apple-system, sans-serif",
      }}
    >
      {/* Header bar */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          marginBottom: '1.5rem',
          borderBottom: '1px solid #f1f5f9',
          paddingBottom: '0.75rem',
          userSelect: 'none',
        }}
      >
        <FileText size={18} color="#2563eb" />
        <span
          style={{
            fontSize: '0.85rem',
            fontWeight: 700,
            color: '#1e293b',
            textTransform: 'uppercase',
            letterSpacing: '0.05em',
          }}
        >
          Reader View
        </span>
        <span style={{ fontSize: '0.8rem', color: '#64748b', marginLeft: '6px' }}>
          • Inline Highlights
        </span>
        {pendingSuggestions.length > 0 ? (
          <button
            type="button"
            data-testid="reader-accept-all-btn"
            onClick={() => onAcceptAllSuggestions(pendingSuggestions.map((s) => s.id))}
            disabled={isMutating}
            style={{
              marginLeft: 'auto',
              display: 'inline-flex',
              alignItems: 'center',
              gap: '4px',
              padding: '3px 8px',
              borderRadius: '5px',
              border: 'none',
              background: '#16a34a',
              color: '#ffffff',
              fontSize: '0.75rem',
              fontWeight: 600,
              cursor: isMutating ? 'not-allowed' : 'pointer',
              opacity: isMutating ? 0.6 : 1,
            }}
            title="Accept all visible pending suggestions"
          >
            <Check size={11} />
            Accept all shown ({pendingSuggestions.length})
          </button>
        ) : (
          <span style={{ marginLeft: 'auto', fontSize: '0.8rem', color: '#94a3b8' }}>
            Select any text to annotate
          </span>
        )}
      </div>

      {/* Document content */}
      <div style={{ userSelect: 'text' }}>
        {paragraphs.length === 0 ? (
          <p style={{ color: '#94a3b8' }}>No text available to display.</p>
        ) : (
          paragraphs.map((para, pIdx) => (
            <p
              key={`p-${pIdx}`}
              className="reader-paragraph"
              style={{
                marginBottom: '1.25rem',
                marginBlockStart: 0,
                marginBlockEnd: '1.25rem',
                textAlign: 'justify',
              }}
            >
              {para.map((seg, sIdx) => {
                const hasAnns = seg.annotationIds && seg.annotationIds.length > 0;
                const hasSugs = seg.suggestionIds && seg.suggestionIds.length > 0;
                const isSelected =
                  hasAnns &&
                  seg.annotationIds.some((id) => id === selectedAnnotationId);
                const isFlashing =
                  (hasAnns &&
                    seg.annotationIds.some((id) => id === activeFlashId)) ||
                  (activeFlashRange &&
                    seg.start < activeFlashRange.end &&
                    seg.end > activeFlashRange.start);

                // 1. Plain text segment
                if (!hasAnns && !hasSugs) {
                  return (
                    <span
                      key={`s-${pIdx}-${sIdx}`}
                      data-start={seg.start}
                      data-end={seg.end}
                      className={isFlashing ? 'flash-highlight' : ''}
                      style={{
                        borderRadius: isFlashing ? '3px' : '0',
                        transition: 'background-color 0.2s ease',
                      }}
                    >
                      {seg.text}
                    </span>
                  );
                }

                // 2. Annotation highlight
                if (hasAnns) {
                  // Select the innermost (smallest) annotation for click handling
                  const sortedAnns = [...seg.annotations].sort(
                    (a, b) => (a.end - a.start) - (b.end - b.start)
                  );
                  const primaryAnn = sortedAnns[0];
                  const isMulti = seg.annotations.length > 1;
                  const labelStyle = getLabelStyle(primaryAnn?.label);

                  return (
                    <mark
                      key={`ann-${pIdx}-${sIdx}`}
                      data-start={seg.start}
                      data-end={seg.end}
                      data-annotation-id={primaryAnn?.id}
                      onClick={() => onSelectAnnotation(primaryAnn?.id)}
                      className={isFlashing ? 'flash-highlight' : ''}
                      style={{
                        backgroundColor: isMulti ? '#fef3c7' : labelStyle.bg,
                        color: isMulti ? '#78350f' : labelStyle.text,
                        borderBottom: isMulti
                          ? '3px double #d97706'
                          : `2px solid ${labelStyle.border}`,
                        padding: '1px 3px',
                        borderRadius: '4px',
                        margin: '0 1px',
                        cursor: 'pointer',
                        fontWeight: isSelected ? 700 : 500,
                        outline: isSelected ? '2px solid #2563eb' : 'none',
                        outlineOffset: '1px',
                        display: 'inline',
                        transition: 'all 0.15s ease',
                      }}
                      title={
                        isMulti
                          ? `Overlapping annotations: ${seg.annotations
                              .map((a) => `${a.label}${a.note ? ` (${a.note})` : ''}`)
                              .join(' | ')}`
                          : `${primaryAnn.label}${
                              primaryAnn.note ? `: ${primaryAnn.note}` : ''
                            }`
                      }
                    >
                      {seg.text}
                      {isMulti ? (
                        <span
                          style={{
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '2px',
                            fontSize: '0.62rem',
                            fontWeight: 700,
                            padding: '1px 4px',
                            marginLeft: '3px',
                            borderRadius: '3px',
                            background: '#fde68a',
                            color: '#92400e',
                            verticalAlign: 'middle',
                            userSelect: 'none',
                          }}
                        >
                          <Layers size={9} />
                          {seg.annotations.length}
                        </span>
                      ) : (
                        <span
                          style={{
                            fontSize: '0.62rem',
                            fontWeight: 700,
                            textTransform: 'uppercase',
                            padding: '1px 4px',
                            marginLeft: '3px',
                            borderRadius: '3px',
                            background: labelStyle.badge,
                            color: labelStyle.text,
                            verticalAlign: 'middle',
                            userSelect: 'none',
                          }}
                        >
                          {primaryAnn.label}
                        </span>
                      )}
                    </mark>
                  );
                }

                // 3. Pending suggestion
                if (hasSugs) {
                  const sug = seg.suggestions[0];
                  const isSugSelected = selectedAnnotationId === sug?.id;
                  return (
                    <mark
                      key={`sug-${pIdx}-${sIdx}`}
                      data-start={seg.start}
                      data-end={seg.end}
                      data-suggestion-id={sug?.id}
                      onClick={() => onSelectAnnotation(sug?.id)}
                      className={isFlashing ? 'flash-highlight' : ''}
                      style={{
                        backgroundColor: isSugSelected ? '#fef08a' : '#fef9c388',
                        color: '#713f12',
                        borderBottom: isSugSelected ? '2px solid #ca8a04' : '2px dashed #ca8a04',
                        padding: '1px 3px',
                        borderRadius: '4px',
                        margin: '0 1px',
                        display: 'inline',
                        cursor: 'pointer',
                        outline: isSugSelected ? '2px solid #ca8a04' : 'none',
                        outlineOffset: '1px',
                        transition: 'all 0.15s ease',
                      }}
                      title={`Suggested highlight (relevance: ${(
                        (sug?.score || 0) * 100
                      ).toFixed(0)}%)`}
                    >
                      {seg.text}
                      <span
                        style={{
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '2px',
                          marginLeft: '4px',
                          fontSize: '0.68rem',
                          background: '#fef9c3',
                          padding: '1px 5px',
                          borderRadius: '4px',
                          border: '1px solid #fde047',
                          verticalAlign: 'middle',
                          userSelect: 'none',
                        }}
                      >
                        <Sparkles size={10} color="#ca8a04" />
                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation();
                            onAcceptSuggestion(sug.id);
                          }}
                          style={{
                            border: 'none',
                            background: 'transparent',
                            cursor: 'pointer',
                            color: '#16a34a',
                            padding: '1px',
                            display: 'flex',
                          }}
                          title="Accept suggestion"
                        >
                          <Check size={11} />
                        </button>
                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation();
                            onRejectSuggestion(sug.id);
                          }}
                          style={{
                            border: 'none',
                            background: 'transparent',
                            cursor: 'pointer',
                            color: '#dc2626',
                            padding: '1px',
                            display: 'flex',
                          }}
                          title="Reject suggestion"
                        >
                          <X size={11} />
                        </button>
                      </span>
                    </mark>
                  );
                }

                return null;
              })}
            </p>
          ))
        )}
      </div>

      {/* Floating Popover on selection */}
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
          onSave={handleSaveAnnotation}
          onSaveAndFindMore={handleSaveAndFindMore}
          onClose={clearSelection}
        />
      )}
    </div>
  );
}

export { SelectionPopover };


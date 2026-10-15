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
  const handleMouseUp = (e) => {
    const selection = window.getSelection();
    if (!selection || selection.isCollapsed) return;

    const selectedStr = selection.toString().trim();
    if (!selectedStr || selectedStr.length < 1) return;

    const range = selection.rangeCount > 0 ? selection.getRangeAt(0) : null;
    if (!range) return;

    let matched = computeSelectionOffsetsFromDom(range, cleanText);
    if (!matched) {
      matched = findTextOffsets(cleanText, selectedStr);
    }

    if (matched) {
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
    const activeLabel = selectedLabel || taxonomy?.labels?.[0] || 'Claim';
    if (!selectionRange || !activeLabel || isMutating) return;

    onCreateAnnotation({
      start: selectionRange.start,
      end: selectionRange.end,
      quote: selectionRange.quote,
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

    onSaveAndFindMore({
      start: selectionRange.start,
      end: selectionRange.end,
      quote: selectionRange.quote,
      label: activeLabel,
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
        padding: '2.5rem 3.5rem',
        borderRadius: 0,
        border: '1px solid #000000',
        boxShadow: 'none',
        lineHeight: 1.85,
        fontSize: '1.05rem',
        color: '#000000',
        fontFamily: '"Source Serif 4", Georgia, serif',
      }}
    >
      {/* Header bar */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '10px',
          marginBottom: '2rem',
          borderBottom: '2px solid #000000',
          paddingBottom: '1rem',
          userSelect: 'none',
        }}
      >
        <FileText size={16} strokeWidth={1.5} color="#000000" />
        <span
          style={{
            fontFamily: '"Playfair Display", Georgia, serif',
            fontSize: '1rem',
            fontWeight: 700,
            color: '#000000',
            letterSpacing: '-0.01em',
          }}
        >
          Reader View
        </span>
        <span
          style={{
            fontFamily: '"JetBrains Mono", monospace',
            fontSize: '0.72rem',
            color: '#525252',
            letterSpacing: '0.04em',
            textTransform: 'uppercase',
          }}
        >
          • Inline Editorial Annotations
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
              gap: '6px',
              padding: '4px 10px',
              borderRadius: 0,
              border: '1px solid #000000',
              background: '#000000',
              color: '#ffffff',
              fontFamily: '"JetBrains Mono", monospace',
              fontSize: '0.72rem',
              fontWeight: 600,
              textTransform: 'uppercase',
              letterSpacing: '0.05em',
              cursor: isMutating ? 'not-allowed' : 'pointer',
              opacity: isMutating ? 0.6 : 1,
              transition: 'none',
            }}
            title="Accept all visible pending suggestions"
          >
            <Check size={12} strokeWidth={1.5} color="#ffffff" />
            Accept all shown ({pendingSuggestions.length})
          </button>
        ) : (
          <span
            style={{
              marginLeft: 'auto',
              fontFamily: '"JetBrains Mono", monospace',
              fontSize: '0.72rem',
              color: '#525252',
              textTransform: 'uppercase',
              letterSpacing: '0.04em',
            }}
          >
            Select text to annotate
          </span>
        )}
      </div>

      {/* Document content */}
      <div style={{ userSelect: 'text' }}>
        {paragraphs.length === 0 ? (
          <p
            style={{
              color: '#525252',
              fontStyle: 'italic',
              textAlign: 'center',
              padding: '3rem 0',
            }}
          >
            No text available to display.
          </p>
        ) : (
          paragraphs.map((para, pIdx) => (
            <p
              key={`p-${pIdx}`}
              className={`reader-paragraph ${pIdx === 0 ? 'reader-first-para' : ''}`}
              style={{
                marginBottom: '1.6rem',
                marginBlockStart: 0,
                marginBlockEnd: '1.6rem',
                textAlign: 'justify',
                textJustify: 'inter-word',
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
                        transition: 'none',
                      }}
                    >
                      {seg.text}
                    </span>
                  );
                }

                // 2. Annotation highlight
                if (hasAnns) {
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
                        backgroundColor: isSelected
                          ? '#000000'
                          : isMulti
                          ? '#f5f5f5'
                          : (labelStyle.bg || '#FFF9C4'),
                        color: isSelected ? '#ffffff' : '#000000',
                        borderBottom: isMulti
                          ? '3px double #000000'
                          : isSelected
                          ? '2px solid #000000'
                          : `2px solid ${labelStyle.border || '#000000'}`,
                        borderLeft: `3px solid ${labelStyle.border || '#000000'}`,
                        padding: '1px 4px',
                        borderRadius: 0,
                        margin: '0 1px',
                        cursor: 'pointer',
                        fontWeight: isSelected ? 700 : 500,
                        outline: isSelected ? '2px solid #000000' : 'none',
                        outlineOffset: '2px',
                        display: 'inline',
                        transition: 'none',
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
                            fontFamily: '"JetBrains Mono", monospace',
                            fontSize: '0.62rem',
                            fontWeight: 700,
                            padding: '1px 4px',
                            marginLeft: '4px',
                            borderRadius: 0,
                            border: '1px solid #000000',
                            background: isSelected ? '#ffffff' : '#000000',
                            color: isSelected ? '#000000' : '#ffffff',
                            verticalAlign: 'middle',
                            userSelect: 'none',
                          }}
                        >
                          <Layers size={9} strokeWidth={1.5} />
                          {seg.annotations.length}
                        </span>
                      ) : (
                        <span
                          style={{
                            fontFamily: '"JetBrains Mono", monospace',
                            fontSize: '0.62rem',
                            fontWeight: 700,
                            textTransform: 'uppercase',
                            letterSpacing: '0.05em',
                            padding: '1px 4px',
                            marginLeft: '4px',
                            borderRadius: 0,
                            border: '1px solid #000000',
                            background: isSelected ? '#ffffff' : (labelStyle.badge || '#000000'),
                            color: isSelected ? '#000000' : (labelStyle.badgeText || '#ffffff'),
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
                        backgroundColor: '#ffffff',
                        color: '#000000',
                        borderBottom: isSugSelected ? '2px solid #000000' : '1.5px dashed #000000',
                        padding: '1px 3px',
                        borderRadius: 0,
                        margin: '0 1px',
                        display: 'inline',
                        cursor: 'pointer',
                        outline: isSugSelected ? '2px solid #000000' : 'none',
                        outlineOffset: '2px',
                        transition: 'none',
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
                          gap: '3px',
                          marginLeft: '4px',
                          fontSize: '0.68rem',
                          fontFamily: '"JetBrains Mono", monospace',
                          background: '#ffffff',
                          padding: '1px 4px',
                          borderRadius: 0,
                          border: '1px solid #000000',
                          verticalAlign: 'middle',
                          userSelect: 'none',
                        }}
                      >
                        <Sparkles size={9} strokeWidth={1.5} color="#000000" />
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
                            color: '#000000',
                            padding: '1px',
                            display: 'flex',
                          }}
                          title="Accept suggestion"
                        >
                          <Check size={11} strokeWidth={1.5} />
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
                            color: '#000000',
                            padding: '1px',
                            display: 'flex',
                          }}
                          title="Reject suggestion"
                        >
                          <X size={11} strokeWidth={1.5} />
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

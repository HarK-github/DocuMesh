import React, { useState } from 'react';
import { Tag, Edit2, Trash2, Check, X, AlertCircle, Bookmark, Layers, Sparkles } from 'lucide-react';
import { getDefaultSuggestionScope } from '../config';
import { getLabelStyle } from '../lib/colors';

export default function AnnotationPanel({
  annotations = [],
  taxonomy = { labels: [] },
  selectedId = null,
  onSelect = () => {},
  onUpdate = () => {},
  onDelete = () => {},
  onFindMore = () => {},
  isFindingMore = false,
}) {
  const [editingId, setEditingId] = useState(null);
  const [editLabel, setEditLabel] = useState('');
  const [editNote, setEditNote] = useState('');
  const [staleError, setStaleError] = useState(null);
  const [findMoreScopes, setFindMoreScopes] = useState({});

  const startEdit = (ann, e) => {
    e.stopPropagation();
    setEditingId(ann.id);
    setEditLabel(ann.label);
    setEditNote(ann.note || '');
    setStaleError(null);
  };

  const cancelEdit = (e) => {
    if (e) e.stopPropagation();
    setEditingId(null);
    setStaleError(null);
  };

  const saveEdit = async (ann, e) => {
    e.stopPropagation();
    try {
      await onUpdate({
        id: ann.id,
        data: {
          label: editLabel,
          note: editNote.trim() || null,
          version: ann.version,
        },
      });
      setEditingId(null);
      setStaleError(null);
    } catch (err) {
      if (err?.status === 409) {
        setStaleError('This was changed elsewhere. Refetched latest version.');
      } else {
        setStaleError(err?.message || 'Failed to update annotation');
      }
    }
  };

  const handleDelete = (id, e) => {
    e.stopPropagation();
    onDelete(id);
  };

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        background: '#ffffff',
        borderRadius: 0,
        border: '1px solid #000000',
        boxShadow: 'none',
        overflow: 'hidden',
      }}
    >
      <div
        style={{
          padding: '12px 16px',
          borderBottom: '2px solid #000000',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          background: '#ffffff',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Bookmark size={16} strokeWidth={1.5} color="#000000" />
          <h3
            style={{
              margin: 0,
              fontFamily: '"Playfair Display", Georgia, serif',
              fontSize: '1rem',
              fontWeight: 700,
              color: '#000000',
              letterSpacing: '-0.01em',
            }}
          >
            Annotations ({annotations.length})
          </h3>
        </div>
      </div>

      {staleError && (
        <div
          style={{
            margin: '8px 12px',
            padding: '8px 12px',
            borderRadius: 0,
            background: '#000000',
            color: '#ffffff',
            border: '1px solid #000000',
            fontFamily: '"JetBrains Mono", monospace',
            fontSize: '0.75rem',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
          }}
        >
          <AlertCircle size={14} strokeWidth={1.5} />
          <span>{staleError}</span>
        </div>
      )}

      <div
        style={{
          flex: 1,
          overflowY: 'auto',
          padding: '12px 14px',
          display: 'flex',
          flexDirection: 'column',
          gap: '10px',
        }}
      >
        {annotations.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '2.5rem 1rem', color: '#525252' }}>
            <p
              style={{
                margin: 0,
                fontFamily: '"Playfair Display", Georgia, serif',
                fontSize: '1rem',
                fontWeight: 600,
                color: '#000000',
              }}
            >
              No annotations yet.
            </p>
            <p
              style={{
                margin: '6px 0 0 0',
                fontSize: '0.82rem',
                fontFamily: '"Source Serif 4", Georgia, serif',
                color: '#525252',
              }}
            >
              Highlight any text in the document viewer to create one.
            </p>
          </div>
        ) : (
          annotations.map((ann) => {
            const isSelected = ann.id === selectedId;
            const isEditing = ann.id === editingId;
            const style = getLabelStyle(ann.label);

            return (
              <div
                key={ann.id}
                onClick={() => onSelect(ann.id)}
                style={{
                  padding: '12px',
                  borderRadius: 0,
                  border: isSelected ? '2.5px solid #000000' : '1px solid #000000',
                  background: '#ffffff',
                  cursor: 'pointer',
                  transition: 'background-color 100ms linear',
                  boxShadow: 'none',
                }}
              >
                {isEditing ? (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                    <div>
                      <label
                        style={{
                          display: 'block',
                          fontFamily: '"JetBrains Mono", monospace',
                          fontSize: '0.68rem',
                          fontWeight: 600,
                          textTransform: 'uppercase',
                          color: '#525252',
                          marginBottom: '2px',
                        }}
                      >
                        Label
                      </label>
                      <select
                        value={editLabel}
                        onChange={(e) => setEditLabel(e.target.value)}
                        style={{
                          width: '100%',
                          padding: '5px 8px',
                          borderRadius: 0,
                          border: '1.5px solid #000000',
                          fontSize: '0.8rem',
                          fontFamily: '"JetBrains Mono", monospace',
                          background: '#ffffff',
                          color: '#000000',
                        }}
                      >
                        {taxonomy?.labels?.map((lbl) => (
                          <option key={lbl} value={lbl}>
                            {lbl}
                          </option>
                        ))}
                      </select>
                    </div>

                    <div>
                      <label
                        style={{
                          display: 'block',
                          fontFamily: '"JetBrains Mono", monospace',
                          fontSize: '0.68rem',
                          fontWeight: 600,
                          textTransform: 'uppercase',
                          color: '#525252',
                          marginBottom: '2px',
                        }}
                      >
                        Note
                      </label>
                      <input
                        type="text"
                        value={editNote}
                        onChange={(e) => setEditNote(e.target.value)}
                        placeholder="Add a note..."
                        style={{
                          width: '100%',
                          padding: '5px 8px',
                          borderRadius: 0,
                          border: '1.5px solid #000000',
                          fontSize: '0.8rem',
                          fontFamily: '"Source Serif 4", Georgia, serif',
                          boxSizing: 'border-box',
                          background: '#ffffff',
                          color: '#000000',
                        }}
                      />
                    </div>

                    <div style={{ display: 'flex', gap: '6px', justifyContent: 'flex-end', marginTop: '4px' }}>
                      <button
                        type="button"
                        onClick={cancelEdit}
                        style={{
                          padding: '4px 8px',
                          borderRadius: 0,
                          border: '1px solid #000000',
                          background: '#ffffff',
                          color: '#000000',
                          cursor: 'pointer',
                          fontSize: '0.75rem',
                        }}
                      >
                        <X size={12} strokeWidth={1.5} />
                      </button>
                      <button
                        type="button"
                        onClick={(e) => saveEdit(ann, e)}
                        style={{
                          padding: '4px 8px',
                          borderRadius: 0,
                          border: '1px solid #000000',
                          background: '#000000',
                          color: '#ffffff',
                          cursor: 'pointer',
                          fontSize: '0.75rem',
                        }}
                      >
                        <Check size={12} strokeWidth={1.5} />
                      </button>
                    </div>
                  </div>
                ) : (
                  <>
                    <div
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        marginBottom: '8px',
                      }}
                    >
                      <span
                        style={{
                          fontFamily: '"JetBrains Mono", monospace',
                          fontSize: '0.68rem',
                          fontWeight: 700,
                          letterSpacing: '0.06em',
                          textTransform: 'uppercase',
                          padding: '2px 6px',
                          borderRadius: 0,
                          border: '1px solid #000000',
                          backgroundColor: style.badge,
                          color: style.badgeText || '#000000',
                        }}
                      >
                        {ann.label}
                      </span>

                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <span
                          style={{
                            fontFamily: '"JetBrains Mono", monospace',
                            fontSize: '0.68rem',
                            color: '#525252',
                          }}
                          title="Optimistic version"
                        >
                          v{ann.version}
                        </span>
                        <button
                          type="button"
                          onClick={(e) => startEdit(ann, e)}
                          style={{
                            border: 'none',
                            background: 'transparent',
                            cursor: 'pointer',
                            color: '#000000',
                            padding: '2px',
                          }}
                          title="Edit annotation"
                        >
                          <Edit2 size={13} strokeWidth={1.5} />
                        </button>
                        <button
                          type="button"
                          onClick={(e) => handleDelete(ann.id, e)}
                          style={{
                            border: 'none',
                            background: 'transparent',
                            cursor: 'pointer',
                            color: '#000000',
                            padding: '2px',
                          }}
                          title="Delete annotation"
                        >
                          <Trash2 size={13} strokeWidth={1.5} />
                        </button>
                      </div>
                    </div>

                    <p
                      style={{
                        margin: '0 0 6px 0',
                        fontFamily: '"Source Serif 4", Georgia, serif',
                        fontSize: '0.88rem',
                        lineHeight: 1.45,
                        color: '#000000',
                        fontStyle: 'italic',
                        display: '-webkit-box',
                        WebkitLineClamp: 3,
                        WebkitBoxOrient: 'vertical',
                        overflow: 'hidden',
                      }}
                    >
                      "{ann.quote}"
                    </p>

                    {ann.note && (
                      <p
                        style={{
                          margin: '4px 0 0 0',
                          fontFamily: '"Source Serif 4", Georgia, serif',
                          fontSize: '0.78rem',
                          color: '#525252',
                        }}
                      >
                        <span style={{ fontWeight: 600, fontFamily: '"JetBrains Mono", monospace' }}>NOTE:</span>{' '}
                        {ann.note}
                      </p>
                    )}

                    {/* Adjust Boundaries & Overlapping Layers for selected annotation */}
                    {isSelected && (
                      <div style={{ marginTop: '10px', paddingTop: '10px', borderTop: '1px solid #000000' }}>
                        {/* Adjust Controls */}
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', marginBottom: '8px' }}>
                          <span
                            style={{
                              fontFamily: '"JetBrains Mono", monospace',
                              fontSize: '0.68rem',
                              fontWeight: 600,
                              textTransform: 'uppercase',
                              letterSpacing: '0.05em',
                              color: '#525252',
                            }}
                          >
                            Adjust Boundaries:
                          </span>
                          <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
                            <div
                              style={{
                                display: 'flex',
                                alignItems: 'center',
                                gap: '4px',
                                fontFamily: '"JetBrains Mono", monospace',
                                fontSize: '0.72rem',
                                color: '#000000',
                              }}
                            >
                              <span>Start ({ann.start}):</span>
                              <button
                                type="button"
                                title="Nudge start left"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  onUpdate({ id: ann.id, data: { start: Math.max(0, ann.start - 1), version: ann.version } });
                                }}
                                style={{
                                  padding: '1px 6px',
                                  fontSize: '0.75rem',
                                  borderRadius: 0,
                                  border: '1px solid #000000',
                                  background: '#ffffff',
                                  color: '#000000',
                                  cursor: 'pointer',
                                }}
                              >
                                -
                              </button>
                              <button
                                type="button"
                                title="Nudge start right"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  if (ann.start + 1 < ann.end) {
                                    onUpdate({ id: ann.id, data: { start: ann.start + 1, version: ann.version } });
                                  }
                                }}
                                style={{
                                  padding: '1px 6px',
                                  fontSize: '0.75rem',
                                  borderRadius: 0,
                                  border: '1px solid #000000',
                                  background: '#ffffff',
                                  color: '#000000',
                                  cursor: 'pointer',
                                }}
                              >
                                +
                              </button>
                            </div>
                            <div
                              style={{
                                display: 'flex',
                                alignItems: 'center',
                                gap: '4px',
                                fontFamily: '"JetBrains Mono", monospace',
                                fontSize: '0.72rem',
                                color: '#000000',
                              }}
                            >
                              <span>End ({ann.end}):</span>
                              <button
                                type="button"
                                title="Nudge end left"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  if (ann.end - 1 > ann.start) {
                                    onUpdate({ id: ann.id, data: { end: ann.end - 1, version: ann.version } });
                                  }
                                }}
                                style={{
                                  padding: '1px 6px',
                                  fontSize: '0.75rem',
                                  borderRadius: 0,
                                  border: '1px solid #000000',
                                  background: '#ffffff',
                                  color: '#000000',
                                  cursor: 'pointer',
                                }}
                              >
                                -
                              </button>
                              <button
                                type="button"
                                title="Nudge end right"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  onUpdate({ id: ann.id, data: { end: ann.end + 1, version: ann.version } });
                                }}
                                style={{
                                  padding: '1px 6px',
                                  fontSize: '0.75rem',
                                  borderRadius: 0,
                                  border: '1px solid #000000',
                                  background: '#ffffff',
                                  color: '#000000',
                                  cursor: 'pointer',
                                }}
                              >
                                +
                              </button>
                            </div>
                          </div>
                        </div>

                        {/* Overlapping layers */}
                        {(() => {
                          const overlapping = annotations.filter(
                            (other) =>
                              other.id !== ann.id &&
                              Math.max(other.start, ann.start) < Math.min(other.end, ann.end)
                          );
                          if (overlapping.length === 0) return null;
                          return (
                            <div
                              style={{
                                marginTop: '6px',
                                padding: '6px 8px',
                                background: '#f5f5f5',
                                borderRadius: 0,
                                border: '1px solid #000000',
                              }}
                            >
                              <div
                                style={{
                                  fontFamily: '"JetBrains Mono", monospace',
                                  fontSize: '0.68rem',
                                  color: '#525252',
                                  fontWeight: 600,
                                  textTransform: 'uppercase',
                                  marginBottom: '4px',
                                  display: 'flex',
                                  alignItems: 'center',
                                  gap: '4px',
                                }}
                              >
                                <Layers size={10} strokeWidth={1.5} />
                                <span>Other overlapping layers ({overlapping.length}):</span>
                              </div>
                              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
                                {overlapping.map((oa) => (
                                  <button
                                    key={oa.id}
                                    type="button"
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      onSelect(oa.id);
                                    }}
                                    style={{
                                      padding: '2px 6px',
                                      fontFamily: '"JetBrains Mono", monospace',
                                      fontSize: '0.68rem',
                                      borderRadius: 0,
                                      border: '1px solid #000000',
                                      background: '#ffffff',
                                      cursor: 'pointer',
                                      color: '#000000',
                                      fontWeight: 600,
                                    }}
                                  >
                                    {oa.label} (#{oa.id})
                                  </button>
                                ))}
                              </div>
                            </div>
                          );
                        })()}

                        {/* Find more like this */}
                        {(() => {
                          const defaultScope = getDefaultSuggestionScope(ann.label, annotations);
                          const currentScope = findMoreScopes[ann.id] || defaultScope;
                          return (
                            <div style={{ marginTop: '10px', paddingTop: '10px', borderTop: '1px dashed #000000' }}>
                              <div
                                style={{
                                  display: 'flex',
                                  alignItems: 'center',
                                  justifyContent: 'space-between',
                                  marginBottom: '6px',
                                }}
                              >
                                <span
                                  style={{
                                    fontFamily: '"JetBrains Mono", monospace',
                                    fontSize: '0.68rem',
                                    fontWeight: 600,
                                    textTransform: 'uppercase',
                                    letterSpacing: '0.05em',
                                    color: '#525252',
                                  }}
                                >
                                  Find Similar Passages:
                                </span>
                                <div style={{ display: 'flex', border: '1px solid #000000' }}>
                                  <button
                                    type="button"
                                    data-testid={`panel-scope-passage-${ann.id}`}
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      setFindMoreScopes((prev) => ({ ...prev, [ann.id]: 'passage' }));
                                    }}
                                    style={{
                                      padding: '2px 6px',
                                      fontFamily: '"JetBrains Mono", monospace',
                                      fontSize: '0.68rem',
                                      fontWeight: currentScope === 'passage' ? 700 : 400,
                                      borderRadius: 0,
                                      border: 'none',
                                      background: currentScope === 'passage' ? '#000000' : '#ffffff',
                                      color: currentScope === 'passage' ? '#ffffff' : '#000000',
                                      cursor: 'pointer',
                                    }}
                                  >
                                    Passage
                                  </button>
                                  <button
                                    type="button"
                                    data-testid={`panel-scope-category-${ann.id}`}
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      setFindMoreScopes((prev) => ({ ...prev, [ann.id]: 'category' }));
                                    }}
                                    style={{
                                      padding: '2px 6px',
                                      fontFamily: '"JetBrains Mono", monospace',
                                      fontSize: '0.68rem',
                                      fontWeight: currentScope === 'category' ? 700 : 400,
                                      borderRadius: 0,
                                      border: 'none',
                                      borderLeft: '1px solid #000000',
                                      background: currentScope === 'category' ? '#000000' : '#ffffff',
                                      color: currentScope === 'category' ? '#ffffff' : '#000000',
                                      cursor: 'pointer',
                                    }}
                                  >
                                    Category
                                  </button>
                                </div>
                              </div>
                              <button
                                type="button"
                                data-testid={`find-more-btn-${ann.id}`}
                                disabled={isFindingMore}
                                onClick={(e) => {
                                  e.stopPropagation();
                                  onFindMore({ seed_annotation_id: ann.id, scope: currentScope });
                                }}
                                style={{
                                  width: '100%',
                                  display: 'inline-flex',
                                  alignItems: 'center',
                                  justifyContent: 'center',
                                  gap: '6px',
                                  padding: '6px 12px',
                                  borderRadius: 0,
                                  border: '1.5px solid #000000',
                                  background: '#000000',
                                  color: '#ffffff',
                                  fontFamily: '"JetBrains Mono", monospace',
                                  fontSize: '0.72rem',
                                  fontWeight: 600,
                                  textTransform: 'uppercase',
                                  letterSpacing: '0.06em',
                                  cursor: isFindingMore ? 'not-allowed' : 'pointer',
                                  opacity: isFindingMore ? 0.6 : 1,
                                  transition: 'none',
                                }}
                              >
                                <Sparkles size={12} strokeWidth={1.5} color="#ffffff" />
                                {isFindingMore ? 'Finding similar...' : 'Find more like this'}
                              </button>
                            </div>
                          );
                        })()}
                      </div>
                    )}
                  </>
                )}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}

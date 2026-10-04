import React, { useState } from 'react';
import { Tag, Edit2, Trash2, Check, X, AlertCircle, Bookmark, Layers, Sparkles } from 'lucide-react';
import { getDefaultSuggestionScope } from '../config';

const LABEL_BADGES = {
  Claim: { bg: '#eff6ff', text: '#1d4ed8' },
  Evidence: { bg: '#f0fdf4', text: '#15803d' },
  Definition: { bg: '#fefce8', text: '#a16207' },
  Method: { bg: '#faf5ff', text: '#7e22ce' },
  Result: { bg: '#fff1f2', text: '#be123c' },
  Problem: { bg: '#fef2f2', text: '#b91c1c' },
  Solution: { bg: '#f0fdfa', text: '#0f766e' },
};

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
        borderRadius: '12px',
        border: '1px solid #e2e8f0',
        boxShadow: '0 1px 3px rgba(0,0,0,0.05)',
        overflow: 'hidden',
      }}
    >
      <div
        style={{
          padding: '14px 18px',
          borderBottom: '1px solid #f1f5f9',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Bookmark size={18} color="#2563eb" />
          <h3 style={{ margin: 0, fontSize: '1rem', fontWeight: 600, color: '#1e293b' }}>
            Annotations ({annotations.length})
          </h3>
        </div>
      </div>

      {staleError && (
        <div
          style={{
            margin: '8px 14px',
            padding: '8px 12px',
            borderRadius: '6px',
            background: '#fff7ed',
            border: '1px solid #fed7aa',
            color: '#c2410c',
            fontSize: '0.8rem',
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
          }}
        >
          <AlertCircle size={14} />
          <span>{staleError}</span>
        </div>
      )}

      <div style={{ flex: 1, overflowY: 'auto', padding: '12px 14px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
        {annotations.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '2rem 1rem', color: '#94a3b8' }}>
            <p style={{ margin: 0, fontSize: '0.9rem' }}>No annotations yet.</p>
            <p style={{ margin: '4px 0 0 0', fontSize: '0.8rem' }}>Highlight any text in the document viewer to create one.</p>
          </div>
        ) : (
          annotations.map((ann) => {
            const isSelected = ann.id === selectedId;
            const isEditing = ann.id === editingId;
            const badge = LABEL_BADGES[ann.label] || { bg: '#f1f5f9', text: '#475569' };

            return (
              <div
                key={ann.id}
                onClick={() => onSelect(ann.id)}
                style={{
                  padding: '10px 12px',
                  borderRadius: '8px',
                  border: isSelected ? '2px solid #2563eb' : '1px solid #e2e8f0',
                  background: isSelected ? '#f8fafc' : '#ffffff',
                  cursor: 'pointer',
                  transition: 'all 0.15s ease',
                  boxShadow: isSelected ? '0 2px 4px rgba(37,99,235,0.08)' : 'none',
                }}
              >
                {isEditing ? (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                    <div>
                      <label style={{ display: 'block', fontSize: '0.7rem', color: '#64748b', marginBottom: '2px' }}>Label</label>
                      <select
                        value={editLabel}
                        onChange={(e) => setEditLabel(e.target.value)}
                        style={{
                          width: '100%',
                          padding: '4px 8px',
                          borderRadius: '4px',
                          border: '1px solid #cbd5e1',
                          fontSize: '0.8rem',
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
                      <label style={{ display: 'block', fontSize: '0.7rem', color: '#64748b', marginBottom: '2px' }}>Note</label>
                      <input
                        type="text"
                        value={editNote}
                        onChange={(e) => setEditNote(e.target.value)}
                        placeholder="Add a note..."
                        style={{
                          width: '100%',
                          padding: '4px 8px',
                          borderRadius: '4px',
                          border: '1px solid #cbd5e1',
                          fontSize: '0.8rem',
                          boxSizing: 'border-box',
                        }}
                      />
                    </div>

                    <div style={{ display: 'flex', gap: '6px', justifyContent: 'flex-end', marginTop: '4px' }}>
                      <button
                        type="button"
                        onClick={cancelEdit}
                        style={{
                          padding: '4px 8px',
                          borderRadius: '4px',
                          border: '1px solid #e2e8f0',
                          background: '#fff',
                          cursor: 'pointer',
                          fontSize: '0.75rem',
                        }}
                      >
                        <X size={12} />
                      </button>
                      <button
                        type="button"
                        onClick={(e) => saveEdit(ann, e)}
                        style={{
                          padding: '4px 8px',
                          borderRadius: '4px',
                          border: 'none',
                          background: '#2563eb',
                          color: '#fff',
                          cursor: 'pointer',
                          fontSize: '0.75rem',
                        }}
                      >
                        <Check size={12} />
                      </button>
                    </div>
                  </div>
                ) : (
                  <>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '6px' }}>
                      <span
                        style={{
                          fontSize: '0.7rem',
                          fontWeight: 600,
                          padding: '2px 8px',
                          borderRadius: '4px',
                          backgroundColor: badge.bg,
                          color: badge.text,
                        }}
                      >
                        {ann.label}
                      </span>

                      <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                        <span style={{ fontSize: '0.7rem', color: '#94a3b8' }} title="Optimistic version">
                          v{ann.version}
                        </span>
                        <button
                          type="button"
                          onClick={(e) => startEdit(ann, e)}
                          style={{
                            border: 'none',
                            background: 'transparent',
                            cursor: 'pointer',
                            color: '#64748b',
                            padding: '2px',
                          }}
                          title="Edit annotation"
                        >
                          <Edit2 size={13} />
                        </button>
                        <button
                          type="button"
                          onClick={(e) => handleDelete(ann.id, e)}
                          style={{
                            border: 'none',
                            background: 'transparent',
                            cursor: 'pointer',
                            color: '#ef4444',
                            padding: '2px',
                          }}
                          title="Delete annotation"
                        >
                          <Trash2 size={13} />
                        </button>
                      </div>
                    </div>

                    <p
                      style={{
                        margin: '0 0 4px 0',
                        fontSize: '0.85rem',
                        color: '#1e293b',
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
                      <p style={{ margin: '4px 0 0 0', fontSize: '0.75rem', color: '#64748b' }}>
                        <span style={{ fontWeight: 500 }}>Note:</span> {ann.note}
                      </p>
                    )}

                    {/* Adjust Boundaries & Overlapping Layers for selected annotation */}
                    {isSelected && (
                      <div style={{ marginTop: '8px', paddingTop: '8px', borderTop: '1px dashed #e2e8f0' }}>
                        {/* Adjust Controls */}
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', marginBottom: '6px' }}>
                          <span style={{ fontSize: '0.7rem', fontWeight: 600, color: '#64748b' }}>
                            Adjust Boundaries:
                          </span>
                          <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '0.72rem', color: '#475569' }}>
                              <span>Start ({ann.start}):</span>
                              <button
                                type="button"
                                title="Nudge start left"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  onUpdate({ id: ann.id, data: { start: Math.max(0, ann.start - 1), version: ann.version } });
                                }}
                                style={{ padding: '1px 6px', fontSize: '0.75rem', borderRadius: '3px', border: '1px solid #cbd5e1', background: '#f8fafc', cursor: 'pointer' }}
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
                                style={{ padding: '1px 6px', fontSize: '0.75rem', borderRadius: '3px', border: '1px solid #cbd5e1', background: '#f8fafc', cursor: 'pointer' }}
                              >
                                +
                              </button>
                            </div>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '0.72rem', color: '#475569' }}>
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
                                style={{ padding: '1px 6px', fontSize: '0.75rem', borderRadius: '3px', border: '1px solid #cbd5e1', background: '#f8fafc', cursor: 'pointer' }}
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
                                style={{ padding: '1px 6px', fontSize: '0.75rem', borderRadius: '3px', border: '1px solid #cbd5e1', background: '#f8fafc', cursor: 'pointer' }}
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
                            <div style={{ marginTop: '6px', padding: '6px 8px', background: '#f8fafc', borderRadius: '6px', border: '1px solid #e2e8f0' }}>
                              <div style={{ fontSize: '0.68rem', color: '#64748b', fontWeight: 600, marginBottom: '4px', display: 'flex', alignItems: 'center', gap: '4px' }}>
                                <Layers size={10} />
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
                                      fontSize: '0.7rem',
                                      borderRadius: '4px',
                                      border: '1px solid #cbd5e1',
                                      background: '#ffffff',
                                      cursor: 'pointer',
                                      color: '#1e293b',
                                      fontWeight: 500,
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
                            <div style={{ marginTop: '8px', paddingTop: '8px', borderTop: '1px dashed #e2e8f0' }}>
                              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '6px' }}>
                                <span style={{ fontSize: '0.7rem', fontWeight: 600, color: '#64748b' }}>
                                  Find Similar Passages:
                                </span>
                                <div style={{ display: 'flex', gap: '2px', background: '#f1f5f9', padding: '2px', borderRadius: '4px' }}>
                                  <button
                                    type="button"
                                    data-testid={`panel-scope-passage-${ann.id}`}
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      setFindMoreScopes((prev) => ({ ...prev, [ann.id]: 'passage' }));
                                    }}
                                    style={{
                                      padding: '2px 6px',
                                      fontSize: '0.68rem',
                                      fontWeight: currentScope === 'passage' ? 600 : 400,
                                      borderRadius: '3px',
                                      border: 'none',
                                      background: currentScope === 'passage' ? '#ffffff' : 'transparent',
                                      color: currentScope === 'passage' ? '#1e293b' : '#64748b',
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
                                      fontSize: '0.68rem',
                                      fontWeight: currentScope === 'category' ? 600 : 400,
                                      borderRadius: '3px',
                                      border: 'none',
                                      background: currentScope === 'category' ? '#ffffff' : 'transparent',
                                      color: currentScope === 'category' ? '#1e293b' : '#64748b',
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
                                  gap: '4px',
                                  padding: '5px 10px',
                                  borderRadius: '6px',
                                  border: '1px solid #bfdbfe',
                                  background: '#eff6ff',
                                  color: '#1d4ed8',
                                  fontSize: '0.75rem',
                                  fontWeight: 600,
                                  cursor: isFindingMore ? 'not-allowed' : 'pointer',
                                  opacity: isFindingMore ? 0.6 : 1,
                                }}
                              >
                                <Sparkles size={12} />
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

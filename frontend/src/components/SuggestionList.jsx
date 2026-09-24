import React from 'react';
import { Sparkles, Check, X, RefreshCw } from 'lucide-react';

export default function SuggestionList({
  suggestions = [],
  isLoading = false,
  onAccept = () => {},
  onReject = () => {},
  onRefresh = () => {},
  onSelect = () => {},
}) {
  const pendingSuggestions = suggestions.filter((s) => s.status === 'pending');

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
          <Sparkles size={18} color="#eab308" />
          <h3 style={{ margin: 0, fontSize: '1rem', fontWeight: 600, color: '#1e293b' }}>
            Smart Highlights ({pendingSuggestions.length})
          </h3>
        </div>

        <button
          type="button"
          onClick={onRefresh}
          disabled={isLoading}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '4px',
            padding: '4px 8px',
            borderRadius: '6px',
            border: '1px solid #cbd5e1',
            background: '#ffffff',
            fontSize: '0.75rem',
            cursor: isLoading ? 'not-allowed' : 'pointer',
            color: '#475569',
          }}
          title="Compute and re-rank suggestions based on current annotations"
        >
          <RefreshCw size={12} className={isLoading ? 'spin' : ''} />
          <span>{isLoading ? 'Ranking...' : 'Re-rank'}</span>
        </button>
      </div>

      <div style={{ flex: 1, overflowY: 'auto', padding: '12px 14px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
        {pendingSuggestions.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '2rem 1rem', color: '#94a3b8' }}>
            <p style={{ margin: 0, fontSize: '0.9rem' }}>No pending suggestions.</p>
            <p style={{ margin: '4px 0 0 0', fontSize: '0.8rem' }}>
              Click "Re-rank" to discover similar passages based on your annotations.
            </p>
          </div>
        ) : (
          pendingSuggestions.map((sug) => {
            const scorePct = Math.min(100, Math.max(0, Math.round(sug.score * 100)));
            return (
              <div
                key={sug.id}
                onClick={() => onSelect(sug)}
                style={{
                  padding: '10px 12px',
                  borderRadius: '8px',
                  border: '1px solid #fef08a',
                  background: '#fefce8',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '6px',
                  cursor: 'pointer',
                  transition: 'box-shadow 0.15s ease',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <span
                      style={{
                        fontSize: '0.7rem',
                        fontWeight: 600,
                        padding: '1px 6px',
                        borderRadius: '4px',
                        background: '#fef08a',
                        color: '#854d0e',
                      }}
                    >
                      {scorePct}% match
                    </span>
                    <span style={{ fontSize: '0.7rem', color: '#a16207' }}>Page {sug.page}</span>
                  </div>

                  <div style={{ display: 'flex', gap: '4px' }}>
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        onAccept(sug.id);
                      }}
                      style={{
                        padding: '3px 8px',
                        borderRadius: '4px',
                        border: 'none',
                        background: '#16a34a',
                        color: '#ffffff',
                        fontSize: '0.75rem',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '2px',
                        cursor: 'pointer',
                      }}
                      title="Accept as annotation"
                    >
                      <Check size={12} /> Accept
                    </button>
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        onReject(sug.id);
                      }}
                      style={{
                        padding: '3px 8px',
                        borderRadius: '4px',
                        border: '1px solid #fca5a5',
                        background: '#ffffff',
                        color: '#dc2626',
                        fontSize: '0.75rem',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '2px',
                        cursor: 'pointer',
                      }}
                      title="Reject suggestion"
                    >
                      <X size={12} /> Reject
                    </button>
                  </div>
                </div>

                <p
                  style={{
                    margin: 0,
                    fontSize: '0.85rem',
                    color: '#713f12',
                    fontStyle: 'italic',
                    display: '-webkit-box',
                    WebkitLineClamp: 3,
                    WebkitBoxOrient: 'vertical',
                    overflow: 'hidden',
                  }}
                >
                  "{sug.quote}"
                </p>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}

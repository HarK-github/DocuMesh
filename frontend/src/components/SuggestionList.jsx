import React from 'react';
import { Sparkles, Check, X, RefreshCw, AlertCircle } from 'lucide-react';

export default function SuggestionList({
  suggestions = [],
  isLoading = false,
  pendingCapMessage = null,
  onAccept = () => {},
  onReject = () => {},
  onAcceptAll = () => {},
  onRefresh = () => {},
  onSelect = () => {},
}) {
  const pendingSuggestions = suggestions.filter((s) => s.status === 'pending');
  const capMsg =
    pendingCapMessage ||
    suggestions.find((s) => s.message)?.message ||
    (pendingSuggestions.length >= 10
      ? 'Maximum pending suggestions reached for this seed (10). Please accept or reject existing suggestions.'
      : null);

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
          <Sparkles size={16} strokeWidth={1.5} color="#000000" />
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
            Smart Highlights ({pendingSuggestions.length})
          </h3>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          {pendingSuggestions.length > 0 && (
            <button
              type="button"
              data-testid="accept-all-shown-btn"
              onClick={() => onAcceptAll(pendingSuggestions.map((s) => s.id))}
              disabled={isLoading}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '4px',
                padding: '4px 8px',
                borderRadius: 0,
                border: '1px solid #000000',
                background: '#000000',
                color: '#ffffff',
                fontFamily: '"JetBrains Mono", monospace',
                fontSize: '0.72rem',
                fontWeight: 600,
                textTransform: 'uppercase',
                letterSpacing: '0.05em',
                cursor: isLoading ? 'not-allowed' : 'pointer',
                opacity: isLoading ? 0.6 : 1,
                transition: 'none',
              }}
              title="Accept all currently shown suggestions"
            >
              <Check size={12} strokeWidth={1.5} />
              <span>Accept all shown</span>
            </button>
          )}

          <button
            type="button"
            onClick={onRefresh}
            disabled={isLoading}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
              padding: '4px 8px',
              borderRadius: 0,
              border: '1px solid #000000',
              background: '#ffffff',
              color: '#000000',
              fontFamily: '"JetBrains Mono", monospace',
              fontSize: '0.72rem',
              fontWeight: 600,
              textTransform: 'uppercase',
              letterSpacing: '0.05em',
              cursor: isLoading ? 'not-allowed' : 'pointer',
              transition: 'none',
            }}
            title="Compute and re-rank suggestions based on current annotations"
          >
            <RefreshCw size={12} strokeWidth={1.5} className={isLoading ? 'spin' : ''} />
            <span>{isLoading ? 'Ranking...' : 'Re-rank'}</span>
          </button>
        </div>
      </div>

      {capMsg && (
        <div
          data-testid="pending-cap-message"
          style={{
            margin: '8px 12px 0 12px',
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
          <span>{capMsg}</span>
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
        {pendingSuggestions.length === 0 ? (
          <div
            data-testid="empty-suggestions-state"
            style={{ textAlign: 'center', padding: '2.5rem 1rem', color: '#525252' }}
          >
            <p
              data-testid="empty-suggestions-message"
              style={{
                margin: 0,
                fontFamily: '"Playfair Display", Georgia, serif',
                fontSize: '1rem',
                fontWeight: 600,
                color: '#000000',
              }}
            >
              No more similar passages found
            </p>
            <p
              style={{
                margin: '6px 0 0 0',
                fontSize: '0.82rem',
                fontFamily: '"Source Serif 4", Georgia, serif',
                color: '#525252',
              }}
            >
              Select text to create an annotation, then click "Save + find more like this" to discover similar passages.
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
                  padding: '12px',
                  borderRadius: 0,
                  border: '1px solid #000000',
                  background: '#ffffff',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '8px',
                  cursor: 'pointer',
                  transition: 'background-color 100ms linear',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <span
                      style={{
                        fontFamily: '"JetBrains Mono", monospace',
                        fontSize: '0.7rem',
                        fontWeight: 600,
                        padding: '1px 6px',
                        borderRadius: 0,
                        background: '#000000',
                        color: '#ffffff',
                        letterSpacing: '0.05em',
                      }}
                    >
                      {scorePct}% match
                    </span>
                    <span
                      style={{
                        fontFamily: '"JetBrains Mono", monospace',
                        fontSize: '0.7rem',
                        color: '#525252',
                        letterSpacing: '0.05em',
                      }}
                    >
                      Page {sug.page}
                    </span>
                  </div>

                  <div style={{ display: 'flex', gap: '6px' }}>
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        onAccept(sug.id);
                      }}
                      style={{
                        padding: '3px 8px',
                        borderRadius: 0,
                        border: '1px solid #000000',
                        background: '#000000',
                        color: '#ffffff',
                        fontFamily: '"JetBrains Mono", monospace',
                        fontSize: '0.72rem',
                        fontWeight: 600,
                        display: 'flex',
                        alignItems: 'center',
                        gap: '2px',
                        cursor: 'pointer',
                        transition: 'none',
                      }}
                      title="Accept as annotation"
                    >
                      <Check size={12} strokeWidth={1.5} /> Accept
                    </button>
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        onReject(sug.id);
                      }}
                      style={{
                        padding: '3px 8px',
                        borderRadius: 0,
                        border: '1px solid #000000',
                        background: '#ffffff',
                        color: '#000000',
                        fontFamily: '"JetBrains Mono", monospace',
                        fontSize: '0.72rem',
                        fontWeight: 600,
                        display: 'flex',
                        alignItems: 'center',
                        gap: '2px',
                        cursor: 'pointer',
                        transition: 'none',
                      }}
                      title="Reject suggestion"
                    >
                      <X size={12} strokeWidth={1.5} /> Reject
                    </button>
                  </div>
                </div>

                <p
                  style={{
                    margin: 0,
                    fontFamily: '"Source Serif 4", Georgia, serif',
                    fontSize: '0.88rem',
                    color: '#000000',
                    fontStyle: 'italic',
                    lineHeight: 1.4,
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

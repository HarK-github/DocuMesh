import React from 'react';
import { Bookmark, Sparkles, X } from 'lucide-react';

export default function SelectionPopover({
  popoverRef,
  popoverPos,
  selectionRange,
  selectedLabel,
  onLabelChange = () => {},
  scope = 'passage',
  onScopeChange = () => {},
  note = '',
  onNoteChange = () => {},
  taxonomy = { labels: [] },
  isMutating = false,
  onSave = () => {},
  onSaveAndFindMore = () => {},
  onClose = () => {},
}) {
  return (
    <div
      ref={popoverRef}
      data-testid="selection-popover"
      style={{
        position: 'absolute',
        top: popoverPos ? `${popoverPos.top}px` : '0px',
        left: popoverPos ? `${popoverPos.left}px` : '0px',
        zIndex: 1000,
        background: '#ffffff',
        border: '2px solid #000000',
        padding: '14px 16px',
        width: '310px',
        boxShadow: 'none',
        borderRadius: 0,
      }}
      onMouseDown={(e) => e.stopPropagation()}
      onMouseUp={(e) => e.stopPropagation()}
      onClick={(e) => e.stopPropagation()}
    >
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: '12px',
          borderBottom: '1px solid #000000',
          paddingBottom: '8px',
        }}
      >
        <span
          style={{
            fontFamily: '"Playfair Display", Georgia, serif',
            fontSize: '0.9rem',
            fontWeight: 700,
            color: '#000000',
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            letterSpacing: '-0.01em',
          }}
        >
          <Bookmark size={14} strokeWidth={1.5} color="#000000" /> New Annotation
        </span>
        <button
          onClick={onClose}
          type="button"
          data-testid="popup-close-x"
          style={{
            border: 'none',
            background: 'transparent',
            cursor: 'pointer',
            color: '#000000',
            padding: '2px',
            display: 'flex',
            alignItems: 'center',
          }}
        >
          <X size={15} strokeWidth={1.5} />
        </button>
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          onSave(e);
        }}
      >
        <div style={{ marginBottom: '10px' }}>
          <label
            style={{
              display: 'block',
              fontFamily: '"JetBrains Mono", monospace',
              fontSize: '0.7rem',
              fontWeight: 600,
              textTransform: 'uppercase',
              letterSpacing: '0.05em',
              color: '#525252',
              marginBottom: '4px',
            }}
          >
            Category
          </label>
          <select
            data-testid="popup-category-select"
            value={selectedLabel}
            onChange={(e) => onLabelChange(e.target.value)}
            style={{
              width: '100%',
              padding: '6px 8px',
              border: '1.5px solid #000000',
              borderRadius: 0,
              fontSize: '0.82rem',
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

        <div style={{ marginBottom: '12px' }}>
          <label
            style={{
              display: 'block',
              fontFamily: '"JetBrains Mono", monospace',
              fontSize: '0.7rem',
              fontWeight: 600,
              textTransform: 'uppercase',
              letterSpacing: '0.05em',
              color: '#525252',
              marginBottom: '4px',
            }}
          >
            Note (optional)
          </label>
          <input
            type="text"
            data-testid="popup-note-input"
            value={note}
            onChange={(e) => onNoteChange(e.target.value)}
            placeholder="Brief editorial note..."
            style={{
              width: '100%',
              padding: '6px 8px',
              border: '1.5px solid #000000',
              borderRadius: 0,
              fontSize: '0.82rem',
              fontFamily: '"Source Serif 4", Georgia, serif',
              boxSizing: 'border-box',
              background: '#ffffff',
              color: '#000000',
            }}
          />
        </div>

        {/* Scope toggle for find more */}
        <div style={{ marginBottom: '14px' }}>
          <label
            style={{
              display: 'block',
              fontFamily: '"JetBrains Mono", monospace',
              fontSize: '0.7rem',
              fontWeight: 600,
              textTransform: 'uppercase',
              letterSpacing: '0.05em',
              color: '#525252',
              marginBottom: '4px',
            }}
          >
            Find More Scope
          </label>
          <div
            style={{
              display: 'flex',
              border: '1px solid #000000',
              background: '#ffffff',
            }}
          >
            <button
              type="button"
              data-testid="popup-scope-passage"
              onClick={() => onScopeChange('passage')}
              style={{
                flex: 1,
                padding: '6px 8px',
                fontFamily: '"JetBrains Mono", monospace',
                fontSize: '0.72rem',
                fontWeight: scope === 'passage' ? 700 : 400,
                border: 'none',
                borderRadius: 0,
                background: scope === 'passage' ? '#000000' : '#ffffff',
                color: scope === 'passage' ? '#ffffff' : '#000000',
                cursor: 'pointer',
                transition: 'none',
              }}
            >
              This passage
            </button>
            <button
              type="button"
              data-testid="popup-scope-category"
              onClick={() => onScopeChange('category')}
              style={{
                flex: 1,
                padding: '6px 8px',
                fontFamily: '"JetBrains Mono", monospace',
                fontSize: '0.72rem',
                fontWeight: scope === 'category' ? 700 : 400,
                border: 'none',
                borderLeft: '1px solid #000000',
                borderRadius: 0,
                background: scope === 'category' ? '#000000' : '#ffffff',
                color: scope === 'category' ? '#ffffff' : '#000000',
                cursor: 'pointer',
                transition: 'none',
              }}
            >
              This category
            </button>
          </div>
        </div>

        <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end', marginTop: '12px' }}>
          <button
            type="button"
            data-testid="popup-save-btn"
            disabled={isMutating}
            onClick={onSave}
            style={{
              padding: '6px 14px',
              borderRadius: 0,
              border: '1.5px solid #000000',
              background: '#ffffff',
              color: '#000000',
              fontFamily: '"JetBrains Mono", monospace',
              fontSize: '0.75rem',
              fontWeight: 600,
              textTransform: 'uppercase',
              letterSpacing: '0.05em',
              cursor: isMutating ? 'not-allowed' : 'pointer',
              opacity: isMutating ? 0.6 : 1,
              transition: 'none',
            }}
          >
            Save
          </button>
          <button
            type="button"
            data-testid="popup-save-find-btn"
            disabled={isMutating}
            onClick={onSaveAndFindMore}
            style={{
              padding: '6px 14px',
              borderRadius: 0,
              border: '1.5px solid #000000',
              background: '#000000',
              color: '#ffffff',
              fontFamily: '"JetBrains Mono", monospace',
              fontSize: '0.75rem',
              fontWeight: 600,
              textTransform: 'uppercase',
              letterSpacing: '0.05em',
              cursor: isMutating ? 'not-allowed' : 'pointer',
              opacity: isMutating ? 0.6 : 1,
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
              transition: 'none',
            }}
          >
            <Sparkles size={12} strokeWidth={1.5} color="#ffffff" />
            Save + find more like this
          </button>
        </div>
      </form>
    </div>
  );
}

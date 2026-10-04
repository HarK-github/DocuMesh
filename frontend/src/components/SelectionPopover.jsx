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
        zIndex: 50,
        background: '#ffffff',
        borderRadius: '10px',
        boxShadow:
          '0 10px 25px -5px rgba(0,0,0,0.15), 0 8px 10px -6px rgba(0,0,0,0.1)',
        border: '1px solid #e2e8f0',
        padding: '12px 14px',
        width: '290px',
        animation: 'fadeIn 0.15s ease-out',
      }}
      onMouseDown={(e) => e.stopPropagation()}
    >
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
            fontSize: '0.8rem',
            fontWeight: 600,
            color: '#334155',
            display: 'flex',
            alignItems: 'center',
            gap: '4px',
          }}
        >
          <Bookmark size={13} color="#2563eb" /> New Annotation
        </span>
        <button
          onClick={onClose}
          type="button"
          data-testid="popup-close-x"
          style={{
            border: 'none',
            background: 'transparent',
            cursor: 'pointer',
            color: '#94a3b8',
          }}
        >
          <X size={14} />
        </button>
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          onSave(e);
        }}
      >
        <div style={{ marginBottom: '8px' }}>
          <label
            style={{
              display: 'block',
              fontSize: '0.75rem',
              fontWeight: 500,
              color: '#64748b',
              marginBottom: '3px',
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
          <label
            style={{
              display: 'block',
              fontSize: '0.75rem',
              fontWeight: 500,
              color: '#64748b',
              marginBottom: '3px',
            }}
          >
            Note (optional)
          </label>
          <input
            type="text"
            data-testid="popup-note-input"
            value={note}
            onChange={(e) => onNoteChange(e.target.value)}
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

        {/* Scope toggle for find more */}
        <div style={{ marginBottom: '12px' }}>
          <label
            style={{
              display: 'block',
              fontSize: '0.72rem',
              fontWeight: 600,
              color: '#64748b',
              marginBottom: '4px',
            }}
          >
            Find More Scope
          </label>
          <div
            style={{
              display: 'flex',
              gap: '4px',
              background: '#f1f5f9',
              padding: '3px',
              borderRadius: '6px',
            }}
          >
            <button
              type="button"
              data-testid="popup-scope-passage"
              onClick={() => onScopeChange('passage')}
              style={{
                flex: 1,
                padding: '4px 6px',
                fontSize: '0.72rem',
                fontWeight: scope === 'passage' ? 600 : 400,
                borderRadius: '4px',
                border: 'none',
                background: scope === 'passage' ? '#ffffff' : 'transparent',
                color: scope === 'passage' ? '#1e293b' : '#64748b',
                boxShadow: scope === 'passage' ? '0 1px 2px rgba(0,0,0,0.06)' : 'none',
                cursor: 'pointer',
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
                padding: '4px 6px',
                fontSize: '0.72rem',
                fontWeight: scope === 'category' ? 600 : 400,
                borderRadius: '4px',
                border: 'none',
                background: scope === 'category' ? '#ffffff' : 'transparent',
                color: scope === 'category' ? '#1e293b' : '#64748b',
                boxShadow: scope === 'category' ? '0 1px 2px rgba(0,0,0,0.06)' : 'none',
                cursor: 'pointer',
              }}
            >
              This category
            </button>
          </div>
        </div>

        <div style={{ display: 'flex', gap: '6px', justifyContent: 'flex-end', marginTop: '10px' }}>
          <button
            type="button"
            data-testid="popup-save-btn"
            disabled={isMutating}
            onClick={onSave}
            style={{
              padding: '5px 12px',
              borderRadius: '6px',
              border: '1px solid #cbd5e1',
              background: '#ffffff',
              color: '#334155',
              fontSize: '0.78rem',
              fontWeight: 500,
              cursor: isMutating ? 'not-allowed' : 'pointer',
              opacity: isMutating ? 0.6 : 1,
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
              padding: '5px 12px',
              borderRadius: '6px',
              border: 'none',
              background: '#2563eb',
              color: '#ffffff',
              fontSize: '0.78rem',
              fontWeight: 600,
              cursor: isMutating ? 'not-allowed' : 'pointer',
              opacity: isMutating ? 0.6 : 1,
              display: 'inline-flex',
              alignItems: 'center',
              gap: '4px',
            }}
          >
            <Sparkles size={12} />
            Save + find more like this
          </button>
        </div>
      </form>
    </div>
  );
}

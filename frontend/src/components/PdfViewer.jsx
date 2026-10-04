import React, { useState } from 'react';
import { API_BASE } from '../api/client';
import { FileText, ExternalLink, Download, Highlighter } from 'lucide-react';

export default function PdfViewer({ documentId, annotationsCount = 0 }) {
  const [showHighlights, setShowHighlights] = useState(true);

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
      }}
    >
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
            title={showHighlights ? 'Click to show raw unannotated PDF' : 'Click to show highlighted annotations on PDF'}
          >
            <Highlighter size={12} />
            {showHighlights
              ? `Highlights: ON (${annotationsCount})`
              : 'Highlights: OFF'}
          </button>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
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
      <iframe
        key={pdfUrl}
        src={pdfUrl}
        title="PDF Viewer"
        style={{
          flex: 1,
          width: '100%',
          height: '100%',
          border: 'none',
        }}
      />
    </div>
  );
}

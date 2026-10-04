import React from 'react';
import { API_BASE } from '../api/client';
import { FileText, ExternalLink } from 'lucide-react';

export default function PdfViewer({ documentId }) {
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

  const pdfUrl = `${API_BASE}/documents/${documentId}/pdf`;

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
        <span style={{ display: 'flex', alignItems: 'center', gap: '6px', fontWeight: 600 }}>
          <FileText size={15} color="#2563eb" /> Original PDF
        </span>
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
          }}
        >
          <span>Open raw</span>
          <ExternalLink size={12} />
        </a>
      </div>
      <iframe
        src={pdfUrl}
        title="PDF Viewer"
        style={{
          flex: 1,
          width: '100%',
          border: 'none',
        }}
      />
    </div>
  );
}

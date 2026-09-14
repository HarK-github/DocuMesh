import React from 'react';
import { useHealth } from './hooks/useHealth';

export default function App() {
  const { data, isLoading, isError, error } = useHealth();

  return (
    <div style={{ fontFamily: 'Inter, system-ui, sans-serif', padding: '2rem', maxWidth: '800px', margin: '0 auto' }}>
      <h1>PDF Annotation &amp; Relationship Graph</h1>
      <p style={{ color: '#666' }}>Upload text PDFs, highlight passages, create relationship graphs, and smart annotate.</p>
      
      <div style={{ marginTop: '1.5rem', padding: '1rem', border: '1px solid #e2e8f0', borderRadius: '8px', background: '#f8fafc' }}>
        <h3 style={{ margin: '0 0 0.5rem 0', fontSize: '1.1rem' }}>Backend Connection Status</h3>
        {isLoading && <p style={{ color: '#64748b' }}>Checking backend health...</p>}
        {isError && (
          <p style={{ color: '#ef4444' }}>
            Backend unreachable ({error?.message || 'Error'}). Ensure FastAPI backend is running on <code>http://localhost:8000</code>.
          </p>
        )}
        {data && (
          <div style={{ color: '#16a34a', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <span style={{ height: '10px', width: '10px', borderRadius: '50%', background: '#22c55e', display: 'inline-block' }} />
            <span>Backend healthy: <code>{JSON.stringify(data)}</code></span>
          </div>
        )}
      </div>
    </div>
  );
}

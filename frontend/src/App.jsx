import React, { useState, useEffect } from 'react';
import {
  Upload,
  Sparkles,
  Network,
  BookOpen,
  CheckCircle2,
  AlertCircle,
  Loader2,
  PlusCircle,
} from 'lucide-react';
import { useQueryClient } from '@tanstack/react-query';
import {
  queryKeys,
  useDocument,
  useDocumentText,
  useAnnotations,
  useRelations,
  useGraph,
  useTaxonomy,
  useCreateAnnotation,
  useUpdateAnnotation,
  useDeleteAnnotation,
  useCreateRelation,
  useUpdateRelation,
  useDeleteRelation,
  useJob,
} from './hooks/useApi';
import { useHealth } from './hooks/useHealth';
import { api } from './api/client';
import ReaderView from './components/ReaderView';
import PdfViewer from './components/PdfViewer';
import GraphView from './components/GraphView';
import AnnotationPanel from './components/AnnotationPanel';
import SuggestionList from './components/SuggestionList';

export default function App() {
  const [selectedDocId, setSelectedDocId] = useState(1);
  const [activeTab, setActiveTab] = useState('both'); // 'viewer' | 'graph' | 'both'
  const [docViewMode, setDocViewMode] = useState('reader'); // 'reader' | 'pdf'
  const [selectedAnnotationId, setSelectedAnnotationId] = useState(null);
  const [scrollToId, setScrollToId] = useState(null);
  const [flashRange, setFlashRange] = useState(null);
  const [activeJobId, setActiveJobId] = useState(null);
  const [jobDescription, setJobDescription] = useState('');
  const [uploadError, setUploadError] = useState(null);
  const [suggestions, setSuggestions] = useState([]);
  const [isSuggestingHighlights, setIsSuggestingHighlights] = useState(false);
  const queryClient = useQueryClient();

  // Health and taxonomy
  const { data: healthData, isError: healthError } = useHealth();
  const { data: taxonomy } = useTaxonomy();

  // Document queries
  const { data: docData, isLoading: docLoading } = useDocument(selectedDocId);
  const { data: textData } = useDocumentText(selectedDocId);
  const { data: annotations = [] } = useAnnotations(selectedDocId);
  const { data: relations = [] } = useRelations(selectedDocId);

  // Job tracking
  const { data: jobData } = useJob(activeJobId);

  // Mutations
  const createAnnotationMutation = useCreateAnnotation(selectedDocId);
  const updateAnnotationMutation = useUpdateAnnotation(selectedDocId);
  const deleteAnnotationMutation = useDeleteAnnotation(selectedDocId);
  const createRelationMutation = useCreateRelation(selectedDocId);
  const updateRelationMutation = useUpdateRelation(selectedDocId);
  const deleteRelationMutation = useDeleteRelation(selectedDocId);

  // Clear completed job after a delay and invalidate queries
  useEffect(() => {
    if (jobData?.status === 'done' || jobData?.status === 'failed') {
      if (jobData?.status === 'done' && selectedDocId) {
        queryClient.invalidateQueries({ queryKey: queryKeys.relations(selectedDocId) });
        queryClient.invalidateQueries({ queryKey: queryKeys.annotations(selectedDocId) });
        queryClient.invalidateQueries({ queryKey: queryKeys.graph(selectedDocId) });
        queryClient.invalidateQueries({ queryKey: queryKeys.suggestions(selectedDocId) });
      }
      const timer = setTimeout(() => {
        if (jobData?.status === 'done') {
          setActiveJobId(null);
        }
      }, 3500);
      return () => clearTimeout(timer);
    }
  }, [jobData?.status, selectedDocId, queryClient]);

  // Load existing suggestions for document
  const fetchSuggestions = async () => {
    if (!selectedDocId) return;
    try {
      const res = await api.get(`/documents/${selectedDocId}/suggestions`);
      setSuggestions(res || []);
    } catch {
      // Ignored
    }
  };

  useEffect(() => {
    fetchSuggestions();
  }, [selectedDocId]);

  // Handle document file upload
  const handleFileUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploadError(null);

    const formData = new FormData();
    formData.append('file', file);

    try {
      setJobDescription(`Uploading & processing ${file.name}...`);
      const res = await api.upload('/documents', formData);
      setSelectedDocId(res.document_id);
      if (res.job_id) {
        setActiveJobId(res.job_id);
      }
    } catch (err) {
      setUploadError(err?.message || 'Failed to upload document');
    }
  };

  // Generate smart highlights
  const handleGenerateHighlights = async () => {
    if (!selectedDocId) return;
    setIsSuggestingHighlights(true);
    try {
      const res = await api.post(`/documents/${selectedDocId}/suggest-highlights`);
      setSuggestions(res || []);
    } catch (err) {
      alert(`Could not suggest highlights: ${err.message}`);
    } finally {
      setIsSuggestingHighlights(false);
    }
  };

  // Accept smart highlight
  const handleAcceptSuggestion = async (sugId) => {
    try {
      await api.post(`/suggestions/${sugId}/accept`);
      await fetchSuggestions();
      queryClient.invalidateQueries({ queryKey: queryKeys.annotations(selectedDocId) });
      queryClient.invalidateQueries({ queryKey: queryKeys.graph(selectedDocId) });
      queryClient.invalidateQueries({ queryKey: queryKeys.suggestions(selectedDocId) });
    } catch (err) {
      alert(`Failed to accept suggestion: ${err.message}`);
    }
  };

  // Reject smart highlight
  const handleRejectSuggestion = async (sugId) => {
    try {
      await api.post(`/suggestions/${sugId}/reject`);
      await fetchSuggestions();
    } catch (err) {
      alert(`Failed to reject suggestion: ${err.message}`);
    }
  };

  // Trigger LLM relation inference
  const handleSuggestRelations = async () => {
    if (!selectedDocId) return;
    try {
      setJobDescription('Analyzing annotation pairs with AI...');
      const res = await api.post(`/documents/${selectedDocId}/suggest-relations`);
      if (res.job_id) {
        setActiveJobId(res.job_id);
      }
    } catch (err) {
      alert(`Failed to trigger relation discovery: ${err.message}`);
    }
  };

  const handleSelectAnnotation = (id) => {
    setSelectedAnnotationId(id);
    setScrollToId(id);
  };

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        height: '100vh',
        width: '100vw',
        overflow: 'hidden',
        background: '#f1f5f9',
        fontFamily: "'Inter', system-ui, -apple-system, sans-serif",
      }}
    >
      {/* Top Header */}
      <header
        style={{
          height: '60px',
          background: '#ffffff',
          borderBottom: '1px solid #e2e8f0',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '0 20px',
          flexShrink: 0,
          boxShadow: '0 1px 2px rgba(0,0,0,0.03)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div
            style={{
              width: '32px',
              height: '32px',
              borderRadius: '8px',
              background: 'linear-gradient(135deg, #2563eb, #3b82f6)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#fff',
            }}
          >
            <Network size={18} />
          </div>
          <div>
            <h1 style={{ margin: 0, fontSize: '1.05rem', fontWeight: 700, color: '#0f172a' }}>
              DocuMesh
            </h1>
            <span style={{ fontSize: '0.7rem', color: '#64748b' }}>
              Interactive Document &amp; Relationship Mesh
            </span>
          </div>
        </div>

        {/* Center: View Switcher */}
        <div
          style={{
            display: 'flex',
            background: '#f1f5f9',
            padding: '3px',
            borderRadius: '8px',
            gap: '2px',
          }}
        >
          <button
            type="button"
            onClick={() => setActiveTab('viewer')}
            style={{
              padding: '5px 12px',
              borderRadius: '6px',
              border: 'none',
              fontSize: '0.8rem',
              fontWeight: 500,
              cursor: 'pointer',
              background: activeTab === 'viewer' ? '#ffffff' : 'transparent',
              color: activeTab === 'viewer' ? '#2563eb' : '#64748b',
              boxShadow: activeTab === 'viewer' ? '0 1px 3px rgba(0,0,0,0.1)' : 'none',
            }}
          >
            Document View
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('both')}
            style={{
              padding: '5px 12px',
              borderRadius: '6px',
              border: 'none',
              fontSize: '0.8rem',
              fontWeight: 500,
              cursor: 'pointer',
              background: activeTab === 'both' ? '#ffffff' : 'transparent',
              color: activeTab === 'both' ? '#2563eb' : '#64748b',
              boxShadow: activeTab === 'both' ? '0 1px 3px rgba(0,0,0,0.1)' : 'none',
            }}
          >
            Split View
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('graph')}
            style={{
              padding: '5px 12px',
              borderRadius: '6px',
              border: 'none',
              fontSize: '0.8rem',
              fontWeight: 500,
              cursor: 'pointer',
              background: activeTab === 'graph' ? '#ffffff' : 'transparent',
              color: activeTab === 'graph' ? '#2563eb' : '#64748b',
              boxShadow: activeTab === 'graph' ? '0 1px 3px rgba(0,0,0,0.1)' : 'none',
            }}
          >
            Graph View
          </button>
        </div>

        {/* Right Action Bar */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <button
            type="button"
            onClick={handleSuggestRelations}
            disabled={annotations.length < 2 || activeJobId !== null}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '6px 12px',
              borderRadius: '6px',
              border: '1px solid #dbeafe',
              background: '#eff6ff',
              color: '#1d4ed8',
              fontSize: '0.8rem',
              fontWeight: 600,
              cursor: annotations.length < 2 ? 'not-allowed' : 'pointer',
              opacity: annotations.length < 2 ? 0.6 : 1,
            }}
            title="Infer typed relationships between annotations using AI"
          >
            <Sparkles size={14} />
            <span>Discover Relations</span>
          </button>

          <label
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '6px 14px',
              borderRadius: '6px',
              background: '#2563eb',
              color: '#ffffff',
              fontSize: '0.8rem',
              fontWeight: 500,
              cursor: 'pointer',
              boxShadow: '0 1px 2px rgba(37,99,235,0.2)',
            }}
          >
            <Upload size={14} />
            <span>Upload PDF</span>
            <input
              type="file"
              accept="application/pdf"
              onChange={handleFileUpload}
              style={{ display: 'none' }}
            />
          </label>

          {/* Backend Status indicator */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '4px 8px',
              borderRadius: '16px',
              background: healthError ? '#fee2e2' : '#f0fdf4',
              color: healthError ? '#b91c1c' : '#15803d',
              fontSize: '0.75rem',
            }}
          >
            <span
              style={{
                width: '7px',
                height: '7px',
                borderRadius: '50%',
                background: healthError ? '#ef4444' : '#22c55e',
              }}
            />
            <span>{healthError ? 'API Offline' : 'Connected'}</span>
          </div>
        </div>
      </header>

      {/* Background Job Progress Notification Banner */}
      {activeJobId && jobData && (
        <div
          style={{
            background: jobData.status === 'failed' ? '#fef2f2' : '#eff6ff',
            borderBottom: `1px solid ${jobData.status === 'failed' ? '#fca5a5' : '#bfdbfe'}`,
            padding: '8px 20px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            fontSize: '0.82rem',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            {jobData.status === 'done' ? (
              <CheckCircle2 size={16} color="#16a34a" />
            ) : jobData.status === 'failed' ? (
              <AlertCircle size={16} color="#dc2626" />
            ) : (
              <Loader2 size={16} color="#2563eb" className="spin" />
            )}
            <span style={{ fontWeight: 600 }}>
              {jobDescription || `Job ${jobData.type}`} ({jobData.status})
            </span>
            {jobData.status === 'failed' && (
              <span style={{ color: '#b91c1c' }}>: {jobData.error}</span>
            )}
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <div
              style={{
                width: '120px',
                height: '6px',
                borderRadius: '3px',
                background: '#e2e8f0',
                overflow: 'hidden',
              }}
            >
              <div
                style={{
                  height: '100%',
                  width: `${jobData.progress}%`,
                  background: jobData.status === 'failed' ? '#ef4444' : '#2563eb',
                  transition: 'width 0.3s ease',
                }}
              />
            </div>
            <span style={{ fontSize: '0.75rem', color: '#64748b' }}>{jobData.progress}%</span>
          </div>
        </div>
      )}

      {/* Main Workspace Layout */}
      <div
        style={{
          display: 'flex',
          flex: 1,
          overflow: 'hidden',
          padding: '12px',
          gap: '12px',
        }}
      >
        {/* Left Column: Reader / Document View */}
        {(activeTab === 'viewer' || activeTab === 'both') && (
          <div
            style={{
              flex: activeTab === 'both' ? 5 : 1,
              height: '100%',
              display: 'flex',
              flexDirection: 'column',
              overflow: 'hidden',
              gap: '6px',
            }}
          >
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '0 4px',
              }}
            >
              <div
                style={{
                  display: 'inline-flex',
                  background: '#e2e8f0',
                  padding: '2px',
                  borderRadius: '6px',
                  gap: '2px',
                }}
              >
                <button
                  type="button"
                  onClick={() => setDocViewMode('reader')}
                  style={{
                    padding: '3px 10px',
                    borderRadius: '4px',
                    border: 'none',
                    fontSize: '0.75rem',
                    fontWeight: 600,
                    cursor: 'pointer',
                    background: docViewMode === 'reader' ? '#ffffff' : 'transparent',
                    color: docViewMode === 'reader' ? '#2563eb' : '#64748b',
                    boxShadow: docViewMode === 'reader' ? '0 1px 2px rgba(0,0,0,0.05)' : 'none',
                  }}
                >
                  Reader View
                </button>
                <button
                  type="button"
                  onClick={() => setDocViewMode('pdf')}
                  style={{
                    padding: '3px 10px',
                    borderRadius: '4px',
                    border: 'none',
                    fontSize: '0.75rem',
                    fontWeight: 600,
                    cursor: 'pointer',
                    background: docViewMode === 'pdf' ? '#ffffff' : 'transparent',
                    color: docViewMode === 'pdf' ? '#2563eb' : '#64748b',
                    boxShadow: docViewMode === 'pdf' ? '0 1px 2px rgba(0,0,0,0.05)' : 'none',
                  }}
                >
                  Raw PDF
                </button>
              </div>
            </div>

            <div style={{ flex: 1, height: '100%', overflow: 'hidden' }}>
              {docViewMode === 'reader' ? (
                <ReaderView
                  documentId={selectedDocId}
                  cleanText={textData?.clean_text || ''}
                  annotations={annotations}
                  suggestions={suggestions}
                  taxonomy={taxonomy}
                  selectedAnnotationId={selectedAnnotationId}
                  onSelectAnnotation={handleSelectAnnotation}
                  onCreateAnnotation={(payload) => createAnnotationMutation.mutate(payload)}
                  onAcceptSuggestion={handleAcceptSuggestion}
                  onRejectSuggestion={handleRejectSuggestion}
                  scrollToAnnotationId={scrollToId}
                  flashRange={flashRange}
                />
              ) : (
                <PdfViewer documentId={selectedDocId} />
              )}
            </div>
          </div>
        )}

        {/* Center Column: Knowledge Graph */}
        {(activeTab === 'graph' || activeTab === 'both') && (
          <div
            style={{
              flex: activeTab === 'both' ? 5 : 1,
              height: '100%',
              overflow: 'clip',
              minWidth: 0,
              minHeight: 0,
            }}
          >
            <GraphView
              annotations={annotations}
              relations={relations}
              taxonomy={taxonomy}
              selectedAnnotationId={selectedAnnotationId}
              onSelectAnnotation={handleSelectAnnotation}
              onCreateRelation={(payload) => createRelationMutation.mutate(payload)}
              onUpdateRelation={(id, data) => updateRelationMutation.mutate({ id, data })}
              onSaveNodePosition={(id, data) => updateAnnotationMutation.mutate({ id, data })}
              onDeleteRelation={(id) => deleteRelationMutation.mutate(id)}
            />
          </div>
        )}

        {/* Right Sidebar: Annotations & Suggestions */}
        <div
          style={{
            width: '340px',
            flexShrink: 0,
            display: 'flex',
            flexDirection: 'column',
            gap: '12px',
            height: '100%',
            overflow: 'hidden',
          }}
        >
          {/* Top Panel: Annotations */}
          <div style={{ flex: 6, minHeight: 0 }}>
            <AnnotationPanel
              annotations={annotations}
              taxonomy={taxonomy}
              selectedId={selectedAnnotationId}
              onSelect={handleSelectAnnotation}
              onUpdate={({ id, data }) => updateAnnotationMutation.mutateAsync({ id, data })}
              onDelete={(id) => deleteAnnotationMutation.mutate(id)}
            />
          </div>

          {/* Bottom Panel: Smart Highlights Suggestions */}
          <div style={{ flex: 4, minHeight: 0 }}>
            <SuggestionList
              suggestions={suggestions}
              isLoading={isSuggestingHighlights}
              onAccept={handleAcceptSuggestion}
              onReject={handleRejectSuggestion}
              onRefresh={handleGenerateHighlights}
              onSelect={(sug) => {
                setScrollToId(null);
                // Highlight corresponding area
              }}
            />
          </div>
        </div>
      </div>
    </div>
  );
}

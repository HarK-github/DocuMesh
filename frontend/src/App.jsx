import React, { useState, useEffect } from 'react';
import {
  Upload,
  Sparkles,
  Network,
  CheckCircle2,
  AlertCircle,
  Loader2,
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
  useSuggestions,
  useSuggestHighlights,
  useAcceptSuggestion,
  useRejectSuggestion,
  useAcceptAllSuggestions,
  useAutoHighlight,
} from './hooks/useApi';
import { useHealth } from './hooks/useHealth';
import { api } from './api/client';
import ReaderView from './components/ReaderView';
import PdfViewer from './components/PdfViewer';
import GraphView from './components/GraphView';
import AnnotationPanel from './components/AnnotationPanel';
import SuggestionList from './components/SuggestionList';
import ChatPanel from './components/ChatPanel';

export default function App() {
  const [selectedDocId, setSelectedDocId] = useState(1);
  const [activeTab, setActiveTab] = useState('both'); // 'viewer' | 'graph' | 'both'
  const [docViewMode, setDocViewMode] = useState('pdf'); // 'pdf' | 'reader'
  const [sidebarTab, setSidebarTab] = useState('chat'); // 'inspector' | 'chat'
  const [selectedAnnotationId, setSelectedAnnotationId] = useState(null);
  const [selectedRelationId, setSelectedRelationId] = useState(null);
  const [scrollToId, setScrollToId] = useState(null);
  const [flashRange, setFlashRange] = useState(null);
  const [activeJobId, setActiveJobId] = useState(null);
  const [jobDescription, setJobDescription] = useState('');
  const [uploadError, setUploadError] = useState(null);
  const [autoHighlightMode, setAutoHighlightMode] = useState('llm');
  const queryClient = useQueryClient();

  // Health, taxonomy, and live server connection
  const { isOnline, isReconnecting, reconnect } = useHealth();
  const { data: taxonomy } = useTaxonomy();

  // Document queries
  const { data: textData } = useDocumentText(selectedDocId);
  const { data: annotations = [] } = useAnnotations(selectedDocId);
  const { data: relations = [] } = useRelations(selectedDocId);
  const { data: graphData } = useGraph(selectedDocId);
  const { data: suggestions = [] } = useSuggestions(selectedDocId);

  // Job tracking
  const { data: jobData } = useJob(activeJobId);

  // Mutations
  const createAnnotationMutation = useCreateAnnotation(selectedDocId);
  const updateAnnotationMutation = useUpdateAnnotation(selectedDocId);
  const deleteAnnotationMutation = useDeleteAnnotation(selectedDocId);
  const createRelationMutation = useCreateRelation(selectedDocId);
  const updateRelationMutation = useUpdateRelation(selectedDocId);
  const deleteRelationMutation = useDeleteRelation(selectedDocId);
  const suggestHighlightsMutation = useSuggestHighlights(selectedDocId);
  const acceptSuggestionMutation = useAcceptSuggestion(selectedDocId);
  const rejectSuggestionMutation = useRejectSuggestion(selectedDocId);
  const acceptAllSuggestionsMutation = useAcceptAllSuggestions(selectedDocId);
  const autoHighlightMutation = useAutoHighlight(selectedDocId);

  const isAutoHighlighting =
    autoHighlightMutation.isPending ||
    (jobData?.type === 'auto_highlight' && jobData?.status === 'running');

  const handleAutoHighlight = async (mode = 'llm') => {
    if (!selectedDocId || isAutoHighlighting) return;
    try {
      setJobDescription(`Auto-highlighting full document (${mode.toUpperCase()} mode)...`);
      const res = await autoHighlightMutation.mutateAsync({ mode });
      if (res?.id) {
        setActiveJobId(res.id);
      }
    } catch (err) {
      console.error('Failed to trigger auto-highlight:', err);
    }
  };

  // Clear completed job after a delay and invalidate queries
  useEffect(() => {
    if (jobData?.status === 'done' || jobData?.status === 'failed') {
      if (jobData?.status === 'done' && selectedDocId) {
        queryClient.invalidateQueries({ queryKey: queryKeys.document(selectedDocId) });
        queryClient.invalidateQueries({ queryKey: queryKeys.documentText(selectedDocId) });
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

  // Generate smart highlights (default re-rank)
  const handleGenerateHighlights = async () => {
    if (!selectedDocId) return;
    try {
      await suggestHighlightsMutation.mutateAsync({});
    } catch (err) {
      alert(`Could not suggest highlights: ${err.message}`);
    }
  };

  // Save annotation + find more like this
  const handleSaveAndFindMore = async (payload) => {
    try {
      const { scope, ...annPayload } = payload;
      const newAnn = await createAnnotationMutation.mutateAsync(annPayload);
      if (newAnn?.id) {
        await suggestHighlightsMutation.mutateAsync({
          seed_annotation_id: newAnn.id,
          scope: scope || 'passage',
        });
      }
    } catch (err) {
      alert(`Could not create annotation and find similar passages: ${err.message}`);
    }
  };

  // Find more from existing annotation
  const handleFindMore = async ({ seed_annotation_id, scope }) => {
    try {
      await suggestHighlightsMutation.mutateAsync({ seed_annotation_id, scope });
    } catch (err) {
      alert(`Could not find similar passages: ${err.message}`);
    }
  };

  // Accept smart highlight
  const handleAcceptSuggestion = (sugId) => {
    acceptSuggestionMutation.mutate(sugId);
  };

  // Reject smart highlight
  const handleRejectSuggestion = (sugId) => {
    rejectSuggestionMutation.mutate(sugId);
  };

  // Accept all visible suggestions
  const handleAcceptAllSuggestions = (sugIds) => {
    if (!sugIds || sugIds.length === 0) return;
    acceptAllSuggestionsMutation.mutate(sugIds);
  };

  // Trigger LLM relation inference
  const handleSuggestRelations = async () => {
    if (!selectedDocId) return;
    try {
      const payload = selectedAnnotationId ? { seed_annotation_id: selectedAnnotationId } : {};
      const desc = selectedAnnotationId
        ? 'Analyzing relations for selected annotation...'
        : 'Analyzing annotation pairs with AI...';
      setJobDescription(desc);
      const res = await api.post(`/documents/${selectedDocId}/suggest-relations`, payload);
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
        background: '#ffffff',
        fontFamily: '"Source Serif 4", Georgia, serif',
        color: '#000000',
      }}
    >
      {/* Top Header */}
      <header
        style={{
          height: '64px',
          background: '#ffffff',
          borderBottom: '4px solid #000000',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '0 24px',
          flexShrink: 0,
          boxShadow: 'none',
        }}
      >
        {/* Brand identity */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
          <div
            style={{
              width: '32px',
              height: '32px',
              borderRadius: 0,
              background: '#000000',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#ffffff',
              border: '1.5px solid #000000',
            }}
          >
            <Network size={18} strokeWidth={1.5} color="#ffffff" />
          </div>
          <div>
            <h1
              style={{
                margin: 0,
                fontFamily: '"Playfair Display", Georgia, serif',
                fontSize: '1.35rem',
                fontWeight: 900,
                color: '#000000',
                letterSpacing: '-0.025em',
                lineHeight: 1.1,
              }}
            >
              DocuMesh
            </h1>
            <span
              style={{
                fontFamily: '"JetBrains Mono", monospace',
                fontSize: '0.65rem',
                fontWeight: 600,
                color: '#525252',
                letterSpacing: '0.08em',
                textTransform: 'uppercase',
              }}
            >
              Editorial Document &amp; Semantic Mesh
            </span>
          </div>
        </div>

        {/* Center: View Switcher */}
        <div
          style={{
            display: 'flex',
            background: '#ffffff',
            border: '1.5px solid #000000',
            borderRadius: 0,
          }}
        >
          <button
            type="button"
            onClick={() => setActiveTab('graph')}
            style={{
              padding: '6px 14px',
              borderRadius: 0,
              border: 'none',
              fontFamily: '"JetBrains Mono", monospace',
              fontSize: '0.72rem',
              fontWeight: 600,
              textTransform: 'uppercase',
              letterSpacing: '0.06em',
              cursor: 'pointer',
              background: activeTab === 'graph' ? '#000000' : '#ffffff',
              color: activeTab === 'graph' ? '#ffffff' : '#000000',
              transition: 'none',
            }}
          >
            Graph View
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('both')}
            style={{
              padding: '6px 14px',
              borderRadius: 0,
              border: 'none',
              borderLeft: '1.5px solid #000000',
              borderRight: '1.5px solid #000000',
              fontFamily: '"JetBrains Mono", monospace',
              fontSize: '0.72rem',
              fontWeight: 600,
              textTransform: 'uppercase',
              letterSpacing: '0.06em',
              cursor: 'pointer',
              background: activeTab === 'both' ? '#000000' : '#ffffff',
              color: activeTab === 'both' ? '#ffffff' : '#000000',
              transition: 'none',
            }}
          >
            Split View
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('viewer')}
            style={{
              padding: '6px 14px',
              borderRadius: 0,
              border: 'none',
              fontFamily: '"JetBrains Mono", monospace',
              fontSize: '0.72rem',
              fontWeight: 600,
              textTransform: 'uppercase',
              letterSpacing: '0.06em',
              cursor: 'pointer',
              background: activeTab === 'viewer' ? '#000000' : '#ffffff',
              color: activeTab === 'viewer' ? '#ffffff' : '#000000',
              transition: 'none',
            }}
          >
            Document View
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
              padding: '7px 14px',
              borderRadius: 0,
              border: '1.5px solid #000000',
              background: selectedAnnotationId ? '#000000' : '#ffffff',
              color: selectedAnnotationId ? '#ffffff' : '#000000',
              fontFamily: '"JetBrains Mono", monospace',
              fontSize: '0.72rem',
              fontWeight: 600,
              textTransform: 'uppercase',
              letterSpacing: '0.05em',
              cursor: annotations.length < 2 || activeJobId !== null ? 'not-allowed' : 'pointer',
              opacity: annotations.length < 2 || activeJobId !== null ? 0.4 : 1,
              transition: 'none',
            }}
            title={
              selectedAnnotationId
                ? 'Infer typed relationships connected to selected annotation using AI'
                : 'Infer typed relationships between annotations across document using AI'
            }
          >
            <Sparkles size={13} strokeWidth={1.5} color={selectedAnnotationId ? '#ffffff' : '#000000'} />
            <span>{selectedAnnotationId ? 'Discover Relations (Selected)' : 'Discover Relations'}</span>
          </button>

          <label
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '7px 16px',
              borderRadius: 0,
              border: '1.5px solid #000000',
              background: '#000000',
              color: '#ffffff',
              fontFamily: '"JetBrains Mono", monospace',
              fontSize: '0.72rem',
              fontWeight: 600,
              textTransform: 'uppercase',
              letterSpacing: '0.06em',
              cursor: 'pointer',
              transition: 'none',
            }}
          >
            <Upload size={13} strokeWidth={1.5} color="#ffffff" />
            <span>Upload PDF</span>
            <input
              type="file"
              accept="application/pdf"
              onChange={handleFileUpload}
              style={{ display: 'none' }}
            />
          </label>

          {/* Auto-Highlight All & Construct Full Graph Button */}
          <div
            style={{
              display: 'inline-flex',
              alignItems: 'stretch',
              border: '1.5px solid #000000',
              background: '#ffffff',
            }}
          >
            <button
              type="button"
              disabled={isAutoHighlighting || !selectedDocId}
              onClick={() => handleAutoHighlight(autoHighlightMode)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                padding: '7px 14px',
                borderRadius: 0,
                border: 'none',
                borderRight: '1.5px solid #000000',
                background: isAutoHighlighting ? '#000000' : '#ffffff',
                color: isAutoHighlighting ? '#ffffff' : '#000000',
                fontFamily: '"JetBrains Mono", monospace',
                fontSize: '0.72rem',
                fontWeight: 700,
                textTransform: 'uppercase',
                letterSpacing: '0.06em',
                cursor: isAutoHighlighting ? 'wait' : 'pointer',
                transition: 'none',
              }}
              title="Automatically classify every sentence in top-down order and construct the full relation knowledge graph"
            >
              {isAutoHighlighting ? (
                <Loader2 size={13} className="spin" color="#ffffff" />
              ) : (
                <Sparkles size={13} strokeWidth={1.5} color="#000000" />
              )}
              <span>{isAutoHighlighting ? 'Processing All...' : 'Auto-Highlight All'}</span>
            </button>
            <select
              value={autoHighlightMode}
              onChange={(e) => setAutoHighlightMode(e.target.value)}
              disabled={isAutoHighlighting}
              style={{
                padding: '0 8px',
                border: 'none',
                borderRadius: 0,
                background: '#ffffff',
                color: '#000000',
                fontFamily: '"JetBrains Mono", monospace',
                fontSize: '0.68rem',
                fontWeight: 700,
                textTransform: 'uppercase',
                letterSpacing: '0.04em',
                cursor: isAutoHighlighting ? 'not-allowed' : 'pointer',
                outline: 'none',
              }}
              title="Choose between LLM semantic classification or Fast embedding prototype mode"
            >
              <option value="llm">LLM</option>
              <option value="embedding">Fast</option>
            </select>
          </div>

          {/* Backend Status indicator */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '5px 10px',
              borderRadius: 0,
              border: '1px solid #000000',
              background: '#ffffff',
              color: '#000000',
              fontFamily: '"JetBrains Mono", monospace',
              fontSize: '0.68rem',
              fontWeight: 600,
              textTransform: 'uppercase',
              letterSpacing: '0.05em',
            }}
          >
            <span
              style={{
                width: '6px',
                height: '6px',
                borderRadius: 0,
                background: !isOnline ? '#737373' : '#000000',
                border: '1px solid #000000',
              }}
            />
            <span>{!isOnline ? (isReconnecting ? 'Reconnecting...' : 'API Offline') : 'Connected'}</span>
          </div>
        </div>
      </header>

      {/* Auto-Reconnection Persistent Banner */}
      {!isOnline && (
        <div
          data-testid="reconnect-banner"
          style={{
            background: '#000000',
            color: '#ffffff',
            borderBottom: '2px solid #ffffff',
            padding: '8px 24px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            fontFamily: '"JetBrains Mono", monospace',
            fontSize: '0.75rem',
            letterSpacing: '0.04em',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <span
              style={{
                display: 'inline-block',
                width: '8px',
                height: '8px',
                background: '#ffffff',
              }}
            />
            <span>SERVER UNREACHABLE — AUTO-RECONNECTING IN BACKGROUND...</span>
          </div>
          <button
            type="button"
            onClick={() => reconnect()}
            style={{
              background: '#ffffff',
              color: '#000000',
              border: 'none',
              borderRadius: 0,
              padding: '4px 12px',
              fontFamily: '"JetBrains Mono", monospace',
              fontSize: '0.7rem',
              fontWeight: 700,
              textTransform: 'uppercase',
              letterSpacing: '0.05em',
              cursor: 'pointer',
            }}
          >
            {isReconnecting ? 'RECONNECTING...' : 'RETRY NOW'}
          </button>
        </div>
      )}

      {/* Upload Error Banner */}
      {uploadError && (
        <div
          style={{
            background: '#000000',
            color: '#ffffff',
            borderBottom: '2px solid #000000',
            padding: '10px 24px',
            display: 'flex',
            alignItems: 'center',
            gap: '10px',
            fontFamily: '"JetBrains Mono", monospace',
            fontSize: '0.78rem',
          }}
        >
          <AlertCircle size={16} strokeWidth={1.5} color="#ffffff" />
          <span>Upload Error: {uploadError}</span>
        </div>
      )}

      {/* Background Job Progress Notification Banner */}
      {activeJobId && jobData && (
        <div
          style={{
            background: '#000000',
            color: '#ffffff',
            borderBottom: '2px solid #000000',
            padding: '10px 24px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            fontSize: '0.78rem',
            fontFamily: '"JetBrains Mono", monospace',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            {jobData.status === 'done' ? (
              <CheckCircle2 size={16} strokeWidth={1.5} color="#ffffff" />
            ) : jobData.status === 'failed' ? (
              <AlertCircle size={16} strokeWidth={1.5} color="#ffffff" />
            ) : (
              <Loader2 size={16} color="#ffffff" className="spin" />
            )}
            <span style={{ fontWeight: 600, letterSpacing: '0.04em' }}>
              {jobData.status === 'done' && jobData.type === 'suggest_relations' && jobData.result?.suggested_count !== undefined
                ? jobData.result.suggested_count > 0
                  ? `Relation discovery complete: found ${jobData.result.suggested_count} new relation${jobData.result.suggested_count === 1 ? '' : 's'}!`
                  : 'Relation discovery complete: no clear new relations found among analyzed pairs.'
                : jobData.status === 'done' && jobData.type === 'auto_highlight' && jobData.result
                ? `Auto-highlight complete: ${jobData.result.annotations_created || 0} highlights & ${jobData.result.relations_created || 0} graph relations constructed!`
                : `${jobDescription || `Job ${jobData.type}`} (${jobData.status})`}
            </span>
            {jobData.status === 'failed' && (
              <span style={{ color: '#ffffff' }}>: {jobData.error}</span>
            )}
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <div
              style={{
                width: '140px',
                height: '8px',
                borderRadius: 0,
                border: '1px solid #ffffff',
                background: '#000000',
                overflow: 'hidden',
              }}
            >
              <div
                style={{
                  height: '100%',
                  width: `${jobData.progress}%`,
                  background: '#ffffff',
                  transition: 'none',
                }}
              />
            </div>
            <span style={{ fontSize: '0.72rem', color: '#ffffff', fontWeight: 600 }}>{jobData.progress}%</span>
          </div>
        </div>
      )}

      {/* Main Workspace Layout */}
      <div
        style={{
          display: 'flex',
          flex: 1,
          overflow: 'hidden',
          padding: '14px',
          gap: '14px',
          background: '#ffffff',
        }}
      >
        {/* Left Column: Knowledge Graph */}
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
              annotations={Array.isArray(graphData?.annotations) ? graphData.annotations : (Array.isArray(annotations) ? annotations : [])}
              relations={Array.isArray(graphData?.relations) ? graphData.relations : (Array.isArray(relations) ? relations : [])}
              taxonomy={taxonomy}
              selectedAnnotationId={selectedAnnotationId}
              selectedRelationId={selectedRelationId}
              onSelectAnnotation={handleSelectAnnotation}
              onAcceptSuggestion={handleAcceptSuggestion}
              onRejectSuggestion={handleRejectSuggestion}
              onCreateRelation={(payload) => createRelationMutation.mutate(payload)}
              onUpdateRelation={(id, data) => updateRelationMutation.mutate({ id, data })}
              onSaveNodePosition={(id, data) => updateAnnotationMutation.mutate({ id, data })}
              onDeleteRelation={(id) => deleteRelationMutation.mutate(id)}
            />
          </div>
        )}

        {/* Center Column: Reader / Document View (PDF default) */}
        {(activeTab === 'viewer' || activeTab === 'both') && (
          <div
            style={{
              flex: activeTab === 'both' ? 5 : 1,
              height: '100%',
              display: 'flex',
              flexDirection: 'column',
              overflow: 'hidden',
              gap: '8px',
            }}
          >
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '0 2px',
              }}
            >
              <div
                style={{
                  display: 'inline-flex',
                  border: '1px solid #000000',
                  borderRadius: 0,
                  background: '#ffffff',
                }}
              >
                <button
                  type="button"
                  onClick={() => setDocViewMode('pdf')}
                  style={{
                    padding: '4px 12px',
                    borderRadius: 0,
                    border: 'none',
                    fontFamily: '"JetBrains Mono", monospace',
                    fontSize: '0.72rem',
                    fontWeight: 600,
                    textTransform: 'uppercase',
                    letterSpacing: '0.04em',
                    cursor: 'pointer',
                    background: docViewMode === 'pdf' ? '#000000' : '#ffffff',
                    color: docViewMode === 'pdf' ? '#ffffff' : '#000000',
                    transition: 'none',
                  }}
                >
                  PDF View
                </button>
                <button
                  type="button"
                  onClick={() => setDocViewMode('reader')}
                  style={{
                    padding: '4px 12px',
                    borderRadius: 0,
                    border: 'none',
                    borderLeft: '1px solid #000000',
                    fontFamily: '"JetBrains Mono", monospace',
                    fontSize: '0.72rem',
                    fontWeight: 600,
                    textTransform: 'uppercase',
                    letterSpacing: '0.04em',
                    cursor: 'pointer',
                    background: docViewMode === 'reader' ? '#000000' : '#ffffff',
                    color: docViewMode === 'reader' ? '#ffffff' : '#000000',
                    transition: 'none',
                  }}
                >
                  Reader View
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
                  onSaveAndFindMore={handleSaveAndFindMore}
                  onAcceptSuggestion={handleAcceptSuggestion}
                  onRejectSuggestion={handleRejectSuggestion}
                  onAcceptAllSuggestions={handleAcceptAllSuggestions}
                  scrollToAnnotationId={scrollToId}
                  flashRange={flashRange}
                  isMutating={
                    createAnnotationMutation.isPending ||
                    suggestHighlightsMutation.isPending ||
                    acceptAllSuggestionsMutation.isPending
                  }
                />
              ) : (
                <PdfViewer
                  documentId={selectedDocId}
                  annotationsCount={annotations?.length || 0}
                  cleanText={textData?.clean_text || ''}
                  annotations={annotations}
                  suggestions={suggestions}
                  taxonomy={taxonomy}
                  selectedAnnotationId={selectedAnnotationId}
                  onSelectAnnotation={handleSelectAnnotation}
                  onCreateAnnotation={(payload) => createAnnotationMutation.mutate(payload)}
                  onSaveAndFindMore={handleSaveAndFindMore}
                  onAcceptSuggestion={handleAcceptSuggestion}
                  onRejectSuggestion={handleRejectSuggestion}
                  onAcceptAllSuggestions={handleAcceptAllSuggestions}
                  scrollToAnnotationId={scrollToId}
                  isMutating={
                    createAnnotationMutation.isPending ||
                    suggestHighlightsMutation.isPending ||
                    acceptAllSuggestionsMutation.isPending
                  }
                />
              )}
            </div>
          </div>
        )}

        {/* Right Sidebar: Inspector (Annotations & Suggestions) or Chat */}
        <div
          style={{
            width: '380px',
            flexShrink: 0,
            display: 'flex',
            flexDirection: 'column',
            gap: '8px',
            height: '100%',
            overflow: 'hidden',
          }}
        >
          {/* Sidebar Tab Switcher */}
          <div
            style={{
              display: 'flex',
              border: '1.5px solid #000000',
              borderRadius: 0,
              background: '#ffffff',
            }}
          >
            <button
              type="button"
              onClick={() => setSidebarTab('inspector')}
              style={{
                flex: 1,
                padding: '6px 10px',
                borderRadius: 0,
                border: 'none',
                fontFamily: '"JetBrains Mono", monospace',
                fontSize: '0.72rem',
                fontWeight: 600,
                textTransform: 'uppercase',
                letterSpacing: '0.05em',
                cursor: 'pointer',
                background: sidebarTab === 'inspector' ? '#000000' : '#ffffff',
                color: sidebarTab === 'inspector' ? '#ffffff' : '#000000',
                transition: 'none',
              }}
            >
              Annotations ({annotations.length})
            </button>
            <button
              type="button"
              onClick={() => setSidebarTab('chat')}
              style={{
                flex: 1,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '6px',
                padding: '6px 10px',
                borderRadius: 0,
                border: 'none',
                borderLeft: '1.5px solid #000000',
                fontFamily: '"JetBrains Mono", monospace',
                fontSize: '0.72rem',
                fontWeight: 600,
                textTransform: 'uppercase',
                letterSpacing: '0.05em',
                cursor: 'pointer',
                background: sidebarTab === 'chat' ? '#000000' : '#ffffff',
                color: sidebarTab === 'chat' ? '#ffffff' : '#000000',
                transition: 'none',
              }}
            >
              <Sparkles size={12} strokeWidth={1.5} color={sidebarTab === 'chat' ? '#ffffff' : '#000000'} />
              <span>Document Chat</span>
            </button>
          </div>

          {sidebarTab === 'chat' ? (
            <div style={{ flex: 1, minHeight: 0, overflow: 'hidden' }}>
              <ChatPanel
                documentId={selectedDocId}
                cleanText={textData?.clean_text || ''}
                taxonomy={taxonomy}
                onSelectAnnotation={handleSelectAnnotation}
                onSelectRelation={(relId) => setSelectedRelationId(relId)}
                onJumpToRange={(range) => setFlashRange(range)}
                onCreateAnnotation={(payload) => createAnnotationMutation.mutate(payload)}
              />
            </div>
          ) : (
            <div
              style={{
                flex: 1,
                minHeight: 0,
                display: 'flex',
                flexDirection: 'column',
                gap: '12px',
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
                  onFindMore={handleFindMore}
                  isFindingMore={suggestHighlightsMutation.isPending}
                />
              </div>

              {/* Bottom Panel: Smart Highlights Suggestions */}
              <div style={{ flex: 4, minHeight: 0 }}>
                <SuggestionList
                  suggestions={suggestions}
                  isLoading={suggestHighlightsMutation.isPending || acceptAllSuggestionsMutation.isPending}
                  onAccept={handleAcceptSuggestion}
                  onReject={handleRejectSuggestion}
                  onAcceptAll={handleAcceptAllSuggestions}
                  onRefresh={handleGenerateHighlights}
                  onSelect={(_sug) => {
                    setScrollToId(null);
                  }}
                />
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

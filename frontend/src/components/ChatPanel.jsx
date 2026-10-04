import React, { useState, useRef, useEffect } from 'react';
import {
  MessageSquare,
  Send,
  Loader2,
  FileText,
  Bookmark,
  Network,
  AlertCircle,
  PlusCircle,
  Sparkles,
  Check,
} from 'lucide-react';
import { useChat } from '../hooks/useApi';

/**
 * CitationChip component for rendering clickable citation pills.
 */
export function CitationChip({
  citation,
  onSelectAnnotation,
  onSelectRelation,
  onJumpToRange,
  onSaveSentenceAnnotation,
  savedSentenceIds = new Set(),
}) {
  const isSaved = citation.type === 'sentence' && savedSentenceIds.has(citation.id);

  const handleClick = () => {
    if (citation.type === 'annotation') {
      if (onSelectAnnotation) onSelectAnnotation(citation.id);
      if (onJumpToRange && citation.start !== null && citation.end !== null) {
        onJumpToRange({ start: citation.start, end: citation.end });
      }
    } else if (citation.type === 'sentence') {
      if (onJumpToRange && citation.start !== null && citation.end !== null) {
        onJumpToRange({ start: citation.start, end: citation.end });
      }
    } else if (citation.type === 'relation') {
      if (onSelectRelation) onSelectRelation(citation.id);
    }
  };

  const getBadgeStyle = () => {
    switch (citation.type) {
      case 'sentence':
        return {
          bg: '#f1f5f9',
          border: '#cbd5e1',
          text: '#334155',
          label: `[s${citation.id}] Sentence`,
          Icon: FileText,
        };
      case 'annotation':
        return {
          bg: '#eff6ff',
          border: '#93c5fd',
          text: '#1d4ed8',
          label: `[a${citation.id}] Annotation`,
          Icon: Bookmark,
        };
      case 'relation':
        return {
          bg: '#faf5ff',
          border: '#d8b4fe',
          text: '#7e22ce',
          label: `[r${citation.id}] Relation`,
          Icon: Network,
        };
      default:
        return {
          bg: '#f8fafc',
          border: '#e2e8f0',
          text: '#64748b',
          label: `[#${citation.id}]`,
          Icon: Sparkles,
        };
    }
  };

  const style = getBadgeStyle();
  const IconComponent = style.Icon;

  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '4px',
        margin: '2px 4px 2px 0',
      }}
    >
      <button
        type="button"
        onClick={handleClick}
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: '4px',
          padding: '2px 8px',
          borderRadius: '12px',
          border: `1px solid ${style.border}`,
          background: style.bg,
          color: style.text,
          fontSize: '0.72rem',
          fontWeight: 600,
          cursor: 'pointer',
          transition: 'all 0.15s ease',
        }}
        title={`Jump to ${citation.type} #${citation.id}`}
      >
        <IconComponent size={11} />
        <span>{style.label}</span>
      </button>

      {citation.type === 'sentence' && onSaveSentenceAnnotation && (
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            onSaveSentenceAnnotation(citation);
          }}
          disabled={isSaved}
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '2px',
            padding: '2px 6px',
            borderRadius: '10px',
            border: '1px solid #bbf7d0',
            background: isSaved ? '#f0fdf4' : '#ffffff',
            color: isSaved ? '#16a34a' : '#15803d',
            fontSize: '0.68rem',
            cursor: isSaved ? 'default' : 'pointer',
          }}
          title={isSaved ? 'Annotated' : 'Save this sentence as an annotation'}
        >
          {isSaved ? <Check size={10} /> : <PlusCircle size={10} />}
          <span>{isSaved ? 'Saved' : 'Annotate'}</span>
        </button>
      )}
    </span>
  );
}

export default function ChatPanel({
  documentId,
  cleanText = '',
  taxonomy = { labels: [] },
  onSelectAnnotation = () => {},
  onSelectRelation = () => {},
  onJumpToRange = () => {},
  onCreateAnnotation = () => {},
}) {
  const [messages, setMessages] = useState([
    {
      role: 'assistant',
      content:
        'Hello! I can answer questions about this document using its text and relationship graph. Answers include clickable citations that highlight referenced passages.',
      citations: [],
    },
  ]);
  const [input, setInput] = useState('');
  const [errorMessage, setErrorMessage] = useState(null);
  const [savedSentenceIds, setSavedSentenceIds] = useState(new Set());
  const messagesEndRef = useRef(null);

  const chatMutation = useChat(documentId);

  // Auto-scroll to bottom of message list
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, chatMutation.isPending]);

  const handleSend = async (e) => {
    e?.preventDefault();
    const query = input.trim();
    if (!query || chatMutation.isPending) return;

    setErrorMessage(null);
    setInput('');

    // Add user message to state
    const userMessage = { role: 'user', content: query };
    const updatedMessages = [...messages, userMessage];
    setMessages(updatedMessages);

    // Prepare history: dialogue turns excluding system greeting
    const historyTurns = updatedMessages
      .slice(1, -1)
      .map((m) => ({ role: m.role, content: m.content }));

    chatMutation.mutate(
      { question: query, history: historyTurns },
      {
        onSuccess: (data) => {
          setMessages((prev) => [
            ...prev,
            {
              role: 'assistant',
              content: data.answer,
              citations: data.citations || [],
              used_context: data.used_context,
            },
          ]);
        },
        onError: (err) => {
          if (err?.status === 503) {
            setErrorMessage(
              'Chat service is not configured (missing LLM API key). Please configure an LLM provider to enable chat.'
            );
          } else {
            setErrorMessage(err?.message || 'Failed to complete question');
          }
        },
      }
    );
  };

  const handleSaveSentenceAnnotation = (citation) => {
    if (!citation || citation.start === null || citation.end === null) return;
    const quote = cleanText.slice(citation.start, citation.end).trim();
    if (!quote) return;

    onCreateAnnotation({
      start: citation.start,
      end: citation.end,
      quote: quote,
      label: taxonomy?.labels?.[0] || 'Claim',
      note: 'Saved from chat citation',
      x: 220 + Math.random() * 40,
      y: 180 + Math.random() * 40,
    });

    setSavedSentenceIds((prev) => new Set(prev).add(citation.id));
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
        overflow: 'hidden',
        boxShadow: '0 1px 3px rgba(0,0,0,0.04)',
      }}
    >
      {/* Header */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          padding: '12px 16px',
          borderBottom: '1px solid #e2e8f0',
          background: '#f8fafc',
        }}
      >
        <div
          style={{
            width: '26px',
            height: '26px',
            borderRadius: '6px',
            background: 'linear-gradient(135deg, #2563eb, #3b82f6)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#fff',
          }}
        >
          <MessageSquare size={14} />
        </div>
        <div>
          <h2
            style={{
              margin: 0,
              fontSize: '0.85rem',
              fontWeight: 700,
              color: '#0f172a',
            }}
          >
            Document Chat
          </h2>
          <span style={{ fontSize: '0.7rem', color: '#64748b' }}>
            Graph-aware Q&amp;A with citations
          </span>
        </div>
      </div>

      {/* Message history */}
      <div
        style={{
          flex: 1,
          overflowY: 'auto',
          padding: '14px',
          display: 'flex',
          flexDirection: 'column',
          gap: '12px',
        }}
      >
        {messages.map((msg, idx) => (
          <div
            key={`msg-${idx}`}
            style={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: msg.role === 'user' ? 'flex-end' : 'flex-start',
            }}
          >
            <div
              style={{
                maxWidth: '90%',
                padding: '10px 14px',
                borderRadius: '10px',
                fontSize: '0.85rem',
                lineHeight: 1.5,
                background: msg.role === 'user' ? '#2563eb' : '#f1f5f9',
                color: msg.role === 'user' ? '#ffffff' : '#1e293b',
                border:
                  msg.role === 'user'
                    ? '1px solid #1d4ed8'
                    : '1px solid #e2e8f0',
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-word',
              }}
            >
              {msg.content}
            </div>

            {/* Citations list for assistant messages */}
            {msg.role === 'assistant' && msg.citations && msg.citations.length > 0 && (
              <div
                style={{
                  marginTop: '6px',
                  display: 'flex',
                  flexWrap: 'wrap',
                  gap: '4px',
                  alignItems: 'center',
                }}
              >
                <span
                  style={{
                    fontSize: '0.68rem',
                    fontWeight: 600,
                    color: '#64748b',
                    marginRight: '2px',
                  }}
                >
                  Citations:
                </span>
                {msg.citations.map((cit, cIdx) => (
                  <CitationChip
                    key={`cit-${idx}-${cIdx}`}
                    citation={cit}
                    onSelectAnnotation={onSelectAnnotation}
                    onSelectRelation={onSelectRelation}
                    onJumpToRange={onJumpToRange}
                    onSaveSentenceAnnotation={handleSaveSentenceAnnotation}
                    savedSentenceIds={savedSentenceIds}
                  />
                ))}
              </div>
            )}
          </div>
        ))}

        {chatMutation.isPending && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#64748b', fontSize: '0.8rem' }}>
            <Loader2 size={15} className="spin" color="#2563eb" />
            <span>Analyzing document and annotation graph...</span>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Error notification */}
      {errorMessage && (
        <div
          style={{
            margin: '0 12px 8px 12px',
            padding: '8px 12px',
            background: '#fee2e2',
            border: '1px solid #fca5a5',
            borderRadius: '8px',
            color: '#991b1b',
            fontSize: '0.78rem',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
          }}
        >
          <AlertCircle size={15} color="#dc2626" style={{ flexShrink: 0 }} />
          <span>{errorMessage}</span>
        </div>
      )}

      {/* Input bar */}
      <form
        onSubmit={handleSend}
        style={{
          display: 'flex',
          padding: '10px 12px',
          borderTop: '1px solid #e2e8f0',
          background: '#ffffff',
          gap: '8px',
        }}
      >
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask a question about the document..."
          disabled={chatMutation.isPending}
          style={{
            flex: 1,
            padding: '8px 12px',
            borderRadius: '8px',
            border: '1px solid #cbd5e1',
            fontSize: '0.84rem',
            outline: 'none',
          }}
        />
        <button
          type="submit"
          disabled={!input.trim() || chatMutation.isPending}
          style={{
            padding: '8px 14px',
            borderRadius: '8px',
            border: 'none',
            background: '#2563eb',
            color: '#ffffff',
            cursor: !input.trim() || chatMutation.isPending ? 'not-allowed' : 'pointer',
            opacity: !input.trim() || chatMutation.isPending ? 0.6 : 1,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
          title="Send question"
        >
          {chatMutation.isPending ? (
            <Loader2 size={15} className="spin" />
          ) : (
            <Send size={15} />
          )}
        </button>
      </form>
    </div>
  );
}

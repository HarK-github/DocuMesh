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
 * Maintains exact element hierarchy: [mainButton, optionalSaveButton] inside root span.
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
    } else if (citation.type === 'chunk') {
      if (onJumpToRange && citation.start !== null && citation.start !== undefined && citation.end !== null && citation.end !== undefined) {
        onJumpToRange({ start: citation.start, end: citation.end });
      }
    } else if (citation.type === 'relation') {
      if (onSelectRelation) onSelectRelation(citation.id);
      if (onJumpToRange && citation.start !== null && citation.start !== undefined && citation.end !== null && citation.end !== undefined) {
        onJumpToRange({ start: citation.start, end: citation.end });
      }
    }
  };

  const getBadgeStyle = () => {
    switch (citation.type) {
      case 'sentence':
        return {
          bg: '#ffffff',
          border: '#000000',
          text: '#000000',
          label: `[s${citation.id}] Sentence`,
          Icon: FileText,
        };
      case 'chunk':
        return {
          bg: '#ffffff',
          border: '#000000',
          text: '#000000',
          label: `[c${citation.id}] Chunk`,
          Icon: FileText,
        };
      case 'annotation':
        return {
          bg: '#000000',
          border: '#000000',
          text: '#ffffff',
          label: `[a${citation.id}] Annotation`,
          Icon: Bookmark,
        };
      case 'relation':
        return {
          bg: '#f5f5f5',
          border: '#000000',
          text: '#000000',
          label: `[r${citation.id}] Relation`,
          Icon: Network,
        };
      default:
        return {
          bg: '#ffffff',
          border: '#000000',
          text: '#000000',
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
          borderRadius: 0,
          border: `1px solid ${style.border}`,
          background: style.bg,
          color: style.text,
          fontFamily: '"JetBrains Mono", monospace',
          fontSize: '0.7rem',
          fontWeight: 600,
          cursor: 'pointer',
          transition: 'none',
        }}
        title={`Jump to ${citation.type} #${citation.id}`}
      >
        <IconComponent size={11} strokeWidth={1.5} color={style.text} />
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
            borderRadius: 0,
            border: '1px solid #000000',
            background: isSaved ? '#000000' : '#ffffff',
            color: isSaved ? '#ffffff' : '#000000',
            fontFamily: '"JetBrains Mono", monospace',
            fontSize: '0.68rem',
            fontWeight: 600,
            cursor: isSaved ? 'default' : 'pointer',
            transition: 'none',
          }}
          title={isSaved ? 'Annotated' : 'Save this sentence as an annotation'}
        >
          {isSaved ? <Check size={10} strokeWidth={1.5} /> : <PlusCircle size={10} strokeWidth={1.5} />}
          <span>{isSaved ? 'Saved' : 'Annotate'}</span>
        </button>
      )}
    </span>
  );
}

/**
 * Render message content with inline clickable badges for citations like [a89], [c124], [s10], [r5].
 * Does NOT treat filenames or URLs as links.
 */
export function renderMessageWithCitations(content, citations = [], handlers = {}) {
  if (!content) return null;

  const parts = content.split(/(\[[acsr]\d+\])/g);
  return parts.map((part, index) => {
    const match = part.match(/^\[([acsr])(\d+)\]$/);
    if (!match) return part;

    const prefix = match[1];
    const id = parseInt(match[2], 10);
    const typeMap = { a: 'annotation', c: 'chunk', s: 'sentence', r: 'relation' };
    const type = typeMap[prefix] || 'annotation';

    const citationMeta = citations.find(
      (c) => c.type === type && Number(c.id) === id
    );

    const handleInlineClick = (e) => {
      e.preventDefault();
      e.stopPropagation();
      if (type === 'annotation') {
        if (handlers.onSelectAnnotation) handlers.onSelectAnnotation(id);
        if (handlers.onJumpToRange && citationMeta?.start != null && citationMeta?.end != null) {
          handlers.onJumpToRange({ start: citationMeta.start, end: citationMeta.end });
        }
      } else if (type === 'chunk' || type === 'sentence') {
        if (handlers.onJumpToRange && citationMeta?.start != null && citationMeta?.end != null) {
          handlers.onJumpToRange({ start: citationMeta.start, end: citationMeta.end });
        }
      } else if (type === 'relation') {
        if (handlers.onSelectRelation) handlers.onSelectRelation(id);
        if (handlers.onJumpToRange && citationMeta?.start != null && citationMeta?.end != null) {
          handlers.onJumpToRange({ start: citationMeta.start, end: citationMeta.end });
        }
      }
    };

    const isAnnotation = type === 'annotation';
    return (
      <button
        key={`inline-cit-${index}`}
        type="button"
        onClick={handleInlineClick}
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          margin: '0 2px',
          padding: '1px 5px',
          border: '1px solid #000000',
          borderRadius: 0,
          background: isAnnotation ? '#000000' : '#f4f4f5',
          color: isAnnotation ? '#ffffff' : '#000000',
          fontFamily: '"JetBrains Mono", monospace',
          fontSize: '0.72rem',
          fontWeight: 700,
          cursor: 'pointer',
          verticalAlign: 'baseline',
          lineHeight: 1.2,
          transition: 'none',
        }}
        title={`Jump to ${type} #${id}`}
      >
        [{prefix}{id}]
      </button>
    );
  });
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
        'Hello. I can assist in examining this text and its relationship graph. Responses include clickable citations corresponding to passages and entities.',
      citations: [],
    },
  ]);
  const [input, setInput] = useState('');
  const [retrievalMode, setRetrievalMode] = useState('hybrid');
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

    const userMessage = { role: 'user', content: query };
    const updatedMessages = [...messages, userMessage];
    setMessages(updatedMessages);

    const historyTurns = updatedMessages
      .slice(1, -1)
      .map((m) => ({ role: m.role, content: m.content }));

    chatMutation.mutate(
      { question: query, history: historyTurns, mode: retrievalMode },
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
        borderRadius: 0,
        border: '1px solid #000000',
        overflow: 'hidden',
        boxShadow: 'none',
      }}
    >
      {/* Header */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '10px',
          padding: '12px 16px',
          borderBottom: '2px solid #000000',
          background: '#ffffff',
        }}
      >
        <div
          style={{
            width: '28px',
            height: '28px',
            borderRadius: 0,
            background: '#000000',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#ffffff',
          }}
        >
          <MessageSquare size={14} strokeWidth={1.5} color="#ffffff" />
        </div>
        <div>
          <h2
            style={{
              margin: 0,
              fontFamily: '"Playfair Display", Georgia, serif',
              fontSize: '0.95rem',
              fontWeight: 700,
              color: '#000000',
              letterSpacing: '-0.01em',
            }}
          >
            Document Chat
          </h2>
          <span
            style={{
              fontFamily: '"JetBrains Mono", monospace',
              fontSize: '0.68rem',
              color: '#525252',
              letterSpacing: '0.04em',
            }}
          >
            GRAPH-AWARE Q&amp;A
          </span>
        </div>
      </div>

      {/* Retrieval Mode Selector */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '6px',
          padding: '6px 12px',
          borderBottom: '1px solid #000000',
          background: '#fcfcfc',
        }}
      >
        <span
          style={{
            fontFamily: '"JetBrains Mono", monospace',
            fontSize: '0.65rem',
            fontWeight: 700,
            textTransform: 'uppercase',
            color: '#525252',
            letterSpacing: '0.04em',
            marginRight: '2px',
          }}
        >
          Mode:
        </span>
        {[
          { id: 'vector', label: 'Vector (Fast)' },
          { id: 'graph', label: 'Graph (Relational)' },
          { id: 'hybrid', label: 'Hybrid (Comprehensive)' },
        ].map((m) => {
          const active = retrievalMode === m.id;
          return (
            <button
              key={m.id}
              type="button"
              onClick={() => setRetrievalMode(m.id)}
              style={{
                fontFamily: '"JetBrains Mono", monospace',
                fontSize: '0.67rem',
                fontWeight: active ? 700 : 500,
                padding: '2px 8px',
                background: active ? '#000000' : '#ffffff',
                color: active ? '#ffffff' : '#000000',
                border: '1px solid #000000',
                cursor: 'pointer',
                borderRadius: 0,
                transition: 'none',
              }}
              title={`Switch retrieval mode to ${m.label}`}
            >
              {m.label}
            </button>
          );
        })}
      </div>

      {/* Message history */}
      <div
        style={{
          flex: 1,
          overflowY: 'auto',
          padding: '16px',
          display: 'flex',
          flexDirection: 'column',
          gap: '14px',
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
                maxWidth: '92%',
                padding: '12px 16px',
                borderRadius: 0,
                fontSize: '0.88rem',
                lineHeight: 1.55,
                fontFamily: '"Source Serif 4", Georgia, serif',
                background: msg.role === 'user' ? '#000000' : '#ffffff',
                color: msg.role === 'user' ? '#ffffff' : '#000000',
                border: msg.role === 'user' ? '1.5px solid #000000' : '1.5px solid #000000',
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-word',
              }}
            >
              {msg.role === 'assistant'
                ? renderMessageWithCitations(msg.content, msg.citations, {
                    onSelectAnnotation,
                    onSelectRelation,
                    onJumpToRange,
                  })
                : msg.content}
            </div>

            {/* Citations list for assistant messages */}
            {msg.role === 'assistant' && msg.citations && msg.citations.length > 0 && (
              <div
                style={{
                  marginTop: '8px',
                  display: 'flex',
                  flexWrap: 'wrap',
                  gap: '4px',
                  alignItems: 'center',
                }}
              >
                <span
                  style={{
                    fontFamily: '"JetBrains Mono", monospace',
                    fontSize: '0.68rem',
                    fontWeight: 700,
                    textTransform: 'uppercase',
                    color: '#525252',
                    marginRight: '2px',
                    letterSpacing: '0.05em',
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
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              color: '#000000',
              fontFamily: '"JetBrains Mono", monospace',
              fontSize: '0.78rem',
            }}
          >
            <Loader2 size={14} className="spin" color="#000000" />
            <span>Analyzing document and annotation graph...</span>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Error notification */}
      {errorMessage && (
        <div
          style={{
            margin: '0 12px 10px 12px',
            padding: '10px 12px',
            background: '#000000',
            border: '1px solid #000000',
            borderRadius: 0,
            color: '#ffffff',
            fontFamily: '"JetBrains Mono", monospace',
            fontSize: '0.75rem',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
          }}
        >
          <AlertCircle size={15} color="#ffffff" style={{ flexShrink: 0 }} />
          <span>{errorMessage}</span>
        </div>
      )}

      {/* Input bar */}
      <form
        onSubmit={handleSend}
        style={{
          display: 'flex',
          padding: '10px 12px',
          borderTop: '2px solid #000000',
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
            padding: '8px 10px',
            borderRadius: 0,
            border: '1.5px solid #000000',
            fontFamily: '"Source Serif 4", Georgia, serif',
            fontSize: '0.84rem',
            outline: 'none',
            background: '#ffffff',
            color: '#000000',
          }}
        />
        <button
          type="submit"
          disabled={!input.trim() || chatMutation.isPending}
          style={{
            padding: '8px 14px',
            borderRadius: 0,
            border: '1.5px solid #000000',
            background: '#000000',
            color: '#ffffff',
            cursor: !input.trim() || chatMutation.isPending ? 'not-allowed' : 'pointer',
            opacity: !input.trim() || chatMutation.isPending ? 0.6 : 1,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            transition: 'none',
          }}
          title="Send question"
        >
          {chatMutation.isPending ? (
            <Loader2 size={15} className="spin" color="#ffffff" />
          ) : (
            <Send size={15} strokeWidth={1.5} color="#ffffff" />
          )}
        </button>
      </form>
    </div>
  );
}

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import ReactFlow, {
  Background,
  Controls,
  applyNodeChanges,
  applyEdgeChanges,
  MarkerType,
  ConnectionMode,
  Handle,
  Position,
} from 'reactflow';
import 'reactflow/dist/style.css';
import dagre from 'dagre';
import {
  Filter,
  Layers,
  CheckCircle2,
  Trash2,
  Check,
  Sparkles,
  X,
} from 'lucide-react';
import { getLabelStyle } from '../lib/colors';

const NODE_WIDTH = 250;
const NODE_HEIGHT = 110;

/**
 * Custom React Flow Node with prominent handles on all 4 borders.
 * Formatted strictly according to Minimalist Monochrome principles:
 * 0px border-radius, pure black/white palette, stark typographic contrast.
 */
export function AnnotationNode({ _id, data, selected }) {
  const ann = data?.annotation;
  if (!ann) return null;

  const isSuggested = ann.status === 'suggested';
  const theme = getLabelStyle(ann.label);

  return (
    <div
      data-testid={`node-${ann.id}`}
      data-status={ann.status || 'confirmed'}
      style={{
        width: NODE_WIDTH,
        minHeight: NODE_HEIGHT,
        borderRadius: 0,
        border: selected
          ? '3px solid #000000'
          : isSuggested
          ? '1.5px dashed #000000'
          : '1.5px solid #000000',
        background: '#ffffff',
        opacity: isSuggested ? 0.72 : 1,
        boxShadow: 'none',
        padding: '10px 12px',
        position: 'relative',
        cursor: 'grab',
        transition: 'border 0.08s linear, opacity 0.08s linear',
        boxSizing: 'border-box',
      }}
    >
      {/* 4 Handles for loose bidirectional connections */}
      <Handle
        type="source"
        position={Position.Top}
        id="top"
        title="Connect from top"
      />
      <Handle
        type="source"
        position={Position.Right}
        id="right"
        title="Connect from right"
      />
      <Handle
        type="source"
        position={Position.Bottom}
        id="bottom"
        title="Connect from bottom"
      />
      <Handle
        type="source"
        position={Position.Left}
        id="left"
        title="Connect from left"
      />

      {/* Header: Label Badge + Score/Version */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: '6px',
          borderBottom: '1px solid #000000',
          paddingBottom: '4px',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <span
            style={{
              fontFamily: '"JetBrains Mono", monospace',
              fontWeight: 700,
              color: theme.badgeText || '#ffffff',
              background: theme.badge || '#000000',
              padding: '1px 6px',
              borderRadius: 0,
              border: '1px solid #000000',
              textTransform: 'uppercase',
              fontSize: '0.65rem',
              letterSpacing: '0.06em',
            }}
          >
            {ann.label}
          </span>
          {isSuggested && (
            <span
              style={{
                fontFamily: '"JetBrains Mono", monospace',
                fontSize: '0.62rem',
                fontWeight: 700,
                padding: '1px 5px',
                borderRadius: 0,
                background: '#ffffff',
                color: '#000000',
                border: '1px solid #000000',
                display: 'inline-flex',
                alignItems: 'center',
                gap: '2px',
                letterSpacing: '0.04em',
              }}
              title={`Similarity score: ${Math.round((ann.score || 0) * 100)}%`}
            >
              <Sparkles size={8} strokeWidth={1.5} color="#000000" />
              {ann.score ? `${Math.round(ann.score * 100)}%` : 'SUGGESTED'}
            </span>
          )}
        </div>
        {!isSuggested ? (
          <span
            style={{
              fontFamily: '"JetBrains Mono", monospace',
              color: '#525252',
              fontSize: '0.65rem',
              fontWeight: 600,
            }}
          >
            v{ann.version}
          </span>
        ) : (
          <span
            style={{
              fontFamily: '"JetBrains Mono", monospace',
              color: '#000000',
              fontSize: '0.65rem',
              fontWeight: 700,
              textTransform: 'uppercase',
            }}
          >
            ghost
          </span>
        )}
      </div>

      {/* Quote Preview */}
      <div
        style={{
          fontFamily: '"Source Serif 4", Georgia, serif',
          fontStyle: 'italic',
          color: '#000000',
          fontSize: '0.78rem',
          lineHeight: 1.35,
          maxHeight: '42px',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          display: '-webkit-box',
          WebkitLineClamp: 2,
          WebkitBoxOrient: 'vertical',
        }}
        title={ann.quote}
      >
        "{ann.quote}"
      </div>

      {/* Optional Note */}
      {ann.note && (
        <div
          style={{
            marginTop: '4px',
            fontFamily: '"Source Serif 4", Georgia, serif',
            fontSize: '0.7rem',
            color: '#525252',
            whiteSpace: 'nowrap',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
          }}
          title={ann.note}
        >
          {ann.note}
        </div>
      )}

      {/* Ghost Node Actions: Accept & Reject */}
      {isSuggested && (
        <div
          style={{
            marginTop: '8px',
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            justifyContent: 'flex-end',
          }}
        >
          <button
            type="button"
            data-testid={`accept-ghost-${ann.id}`}
            onClick={(e) => {
              e.stopPropagation();
              data?.onAccept?.(ann.id);
            }}
            style={{
              border: '1px solid #000000',
              borderRadius: 0,
              background: '#000000',
              color: '#ffffff',
              fontFamily: '"JetBrains Mono", monospace',
              fontSize: '0.68rem',
              fontWeight: 600,
              padding: '2px 8px',
              cursor: 'pointer',
              display: 'inline-flex',
              alignItems: 'center',
              gap: '3px',
              transition: 'none',
            }}
            title="Accept suggestion as confirmed highlight"
          >
            <Check size={11} strokeWidth={1.5} color="#ffffff" /> Accept
          </button>
          <button
            type="button"
            data-testid={`reject-ghost-${ann.id}`}
            onClick={(e) => {
              e.stopPropagation();
              data?.onReject?.(ann.id);
            }}
            style={{
              border: '1px solid #000000',
              borderRadius: 0,
              background: '#ffffff',
              color: '#000000',
              fontFamily: '"JetBrains Mono", monospace',
              fontSize: '0.68rem',
              fontWeight: 600,
              padding: '2px 8px',
              cursor: 'pointer',
              display: 'inline-flex',
              alignItems: 'center',
              gap: '3px',
              transition: 'none',
            }}
            title="Reject suggestion"
          >
            <X size={11} strokeWidth={1.5} color="#000000" /> Reject
          </button>
        </div>
      )}
    </div>
  );
}

const nodeTypes = {
  annotation: AnnotationNode,
};

function getLayoutedElements(nodes, edges, direction = 'LR') {
  const dagreGraph = new dagre.graphlib.Graph();
  dagreGraph.setDefaultEdgeLabel(() => ({}));
  dagreGraph.setGraph({ rankdir: direction, nodesep: 60, ranksep: 100 });

  nodes.forEach((node) => {
    dagreGraph.setNode(node.id, { width: NODE_WIDTH, height: NODE_HEIGHT });
  });

  edges.forEach((edge) => {
    dagreGraph.setEdge(edge.source, edge.target);
  });

  dagre.layout(dagreGraph);

  const layoutedNodes = nodes.map((node) => {
    const nodeWithPosition = dagreGraph.node(node.id);
    return {
      ...node,
      position: {
        x: Math.round(nodeWithPosition.x - NODE_WIDTH / 2),
        y: Math.round(nodeWithPosition.y - NODE_HEIGHT / 2),
      },
    };
  });

  return { nodes: layoutedNodes, edges };
}

export default function GraphView({
  annotations = [],
  relations = [],
  taxonomy = { labels: [], relation_types: [] },
  selectedAnnotationId = null,
  selectedRelationId = null,
  onSelectAnnotation = () => {},
  onAcceptSuggestion = () => {},
  onRejectSuggestion = () => {},
  onCreateRelation = () => {},
  onUpdateRelation = () => {},
  onSaveNodePosition = () => {},
  onDeleteRelation = () => {},
}) {
  const [filterLabel, setFilterLabel] = useState('ALL');
  const [filterRelType, setFilterRelType] = useState('ALL');
  const [showNeighborsOnly, setShowNeighborsOnly] = useState(false);
  const [showSimilarTo, setShowSimilarTo] = useState(true);

  // Connection dialog state (drag from handle to handle)
  const [pendingConnection, setPendingConnection] = useState(null);
  const [selectedRelType, setSelectedRelType] = useState('');

  // Edge inspection modal state (click on existing edge)
  const [inspectedEdge, setInspectedEdge] = useState(null);

  useEffect(() => {
    if (taxonomy?.relation_types?.length && !selectedRelType) {
      setSelectedRelType(taxonomy.relation_types[0]);
    }
  }, [taxonomy, selectedRelType]);

  // Compute filtered nodes and edges
  const { filteredAnnotations, filteredRelations } = useMemo(() => {
    let anns = Array.isArray(annotations) ? annotations : [];
    let rels = Array.isArray(relations) ? relations : [];

    // Filter by label
    if (filterLabel !== 'ALL') {
      anns = anns.filter((a) => a.label === filterLabel);
    }

    // Filter by relation type
    if (filterRelType !== 'ALL') {
      rels = rels.filter((r) => r.type === filterRelType);
    }

    // Hide confirmed similar_to edges by default unless toggled on, but keep suggested ghost edges visible
    if (!showSimilarTo) {
      rels = rels.filter((r) => r.type !== 'similar_to' || r.status === 'suggested');
    }

    // Filter neighbors of selected node
    if (showNeighborsOnly && selectedAnnotationId) {
      const neighborIds = new Set([selectedAnnotationId]);
      rels.forEach((r) => {
        if (r.source_id === selectedAnnotationId) neighborIds.add(r.target_id);
        if (r.target_id === selectedAnnotationId) neighborIds.add(r.source_id);
      });
      anns = anns.filter((a) => neighborIds.has(a.id));
      rels = rels.filter((r) => neighborIds.has(r.source_id) && neighborIds.has(r.target_id));
    }

    return { filteredAnnotations: anns, filteredRelations: rels };
  }, [annotations, relations, filterLabel, filterRelType, showSimilarTo, showNeighborsOnly, selectedAnnotationId]);

  // Transform annotations to React Flow nodes
  const initialNodes = useMemo(() => {
    const list = Array.isArray(filteredAnnotations) ? filteredAnnotations : [];
    return list.map((ann, idx) => {
      const isSuggested = ann.status === 'suggested';
      const nodeId = isSuggested ? `sug-${ann.id}` : String(ann.id);
      const posX = ann.x && ann.x !== 0 ? ann.x : 60 + (idx % 3) * 290;
      const posY = ann.y && ann.y !== 0 ? ann.y : 80 + Math.floor(idx / 3) * 160;

      return {
        id: nodeId,
        type: 'annotation',
        position: { x: posX, y: posY },
        selected: ann.id === selectedAnnotationId,
        data: {
          annotation: ann,
          onAccept: onAcceptSuggestion,
          onReject: onRejectSuggestion,
        },
      };
    });
  }, [filteredAnnotations, selectedAnnotationId, onAcceptSuggestion, onRejectSuggestion]);

  // Transform relations to React Flow edges
  const initialEdges = useMemo(() => {
    const annKeyMap = new Map();
    const annList = Array.isArray(filteredAnnotations) ? filteredAnnotations : [];
    annList.forEach((a) => {
      const k = a.status === 'suggested' ? `sug-${a.id}` : String(a.id);
      annKeyMap.set(k, a);
    });

    const relList = Array.isArray(filteredRelations) ? filteredRelations : [];
    return relList
      .map((rel) => {
        const isGhost = rel.id < 0 && annKeyMap.has(`sug-${rel.source_id}`);
        const sourceKey = isGhost ? `sug-${rel.source_id}` : String(rel.source_id);
        const targetKey = String(rel.target_id);

        if (!annKeyMap.has(sourceKey) || !annKeyMap.has(targetKey)) {
          return null;
        }

        const srcAnn = annKeyMap.get(sourceKey);
        const tgtAnn = annKeyMap.get(targetKey);

        let sourceHandle = 'bottom';
        let targetHandle = 'top';

        if (srcAnn && tgtAnn) {
          const dx = (tgtAnn.x || 0) - (srcAnn.x || 0);
          const dy = (tgtAnn.y || 0) - (srcAnn.y || 0);

          if (Math.abs(dx) > Math.abs(dy)) {
            if (dx > 0) {
              sourceHandle = 'right';
              targetHandle = 'left';
            } else {
              sourceHandle = 'left';
              targetHandle = 'right';
            }
          } else {
            if (dy > 0) {
              sourceHandle = 'bottom';
              targetHandle = 'top';
            } else {
              sourceHandle = 'top';
              targetHandle = 'bottom';
            }
          }
        }

        const isSuggested = rel.status === 'suggested';
        const isImplied = rel.status === 'implied';
        const isFocused = rel.id === selectedRelationId;
        const strokeColor = isImplied ? '#737373' : '#000000';

        let edgeLabel = rel.type;
        if (isImplied) {
          edgeLabel = `${rel.type} (implied)`;
        } else if (rel.type === 'similar_to' && rel.score) {
          edgeLabel = `similar_to (${Math.round(rel.score * 100)}%)`;
        }

        let dashArray = undefined;
        if (isImplied) {
          dashArray = '3,3';
        } else if (isSuggested || (rel.type === 'similar_to' && !isFocused)) {
          dashArray = '6,4';
        }

        return {
          id: `edge-${rel.id}`,
          source: sourceKey,
          target: targetKey,
          sourceHandle,
          targetHandle,
          type: 'smoothstep',
          pathOptions: { borderRadius: 0 },
          label: edgeLabel,
          animated: (isSuggested || isFocused) && !isImplied,
          style: {
            stroke: strokeColor,
            strokeWidth: isFocused ? 3.5 : (isImplied ? 1.2 : 1.5),
            strokeDasharray: dashArray,
          },
          markerEnd: {
            type: MarkerType.ArrowClosed,
            width: 16,
            height: 16,
            color: strokeColor,
          },
          labelStyle: {
            fill: '#000000',
            fontFamily: '"JetBrains Mono", monospace',
            fontWeight: 700,
            fontSize: 10,
          },
          labelBgStyle: {
            fill: '#ffffff',
            fillOpacity: 1,
            stroke: '#000000',
            strokeWidth: 1,
            rx: 0,
            ry: 0,
          },
          labelBgPadding: [6, 3],
          labelBgBorderRadius: 0,
          data: { relation: rel },
        };
      })
      .filter(Boolean);
  }, [filteredAnnotations, filteredRelations, selectedRelationId]);

  const [nodes, setNodes] = useState(initialNodes);
  const [edges, setEdges] = useState(initialEdges);

  useEffect(() => {
    setNodes(initialNodes);
    setEdges(initialEdges);
  }, [initialNodes, initialEdges]);

  const onNodesChange = useCallback(
    (changes) => setNodes((nds) => applyNodeChanges(changes, nds)),
    []
  );

  const onEdgesChange = useCallback(
    (changes) => setEdges((eds) => applyEdgeChanges(changes, eds)),
    []
  );

  const handleNodeDragStop = (event, node) => {
    const ann = node.data?.annotation;
    if (ann) {
      onSaveNodePosition(ann.id, {
        x: node.position.x,
        y: node.position.y,
        version: ann.version,
      });
    }
  };

  const handleConnect = (params) => {
    if (params.source === params.target) return;
    setPendingConnection(params);
  };

  const confirmCreateRelation = () => {
    if (!pendingConnection || !selectedRelType) return;
    onCreateRelation({
      source_id: parseInt(pendingConnection.source, 10),
      target_id: parseInt(pendingConnection.target, 10),
      type: selectedRelType,
      status: 'confirmed',
    });
    setPendingConnection(null);
  };

  const handleAutoLayout = () => {
    const layouted = getLayoutedElements(nodes, edges, 'LR');
    setNodes(layouted.nodes);
    setEdges(layouted.edges);
    layouted.nodes.forEach((n) => {
      const ann = n.data?.annotation;
      if (ann) {
        onSaveNodePosition(ann.id, {
          x: n.position.x,
          y: n.position.y,
          version: ann.version,
        });
      }
    });
  };

  const handleEdgeClick = (_, edge) => {
    const rel = edge.data?.relation;
    if (rel) {
      setInspectedEdge(rel);
    }
  };

  const handleConfirmSuggestedRelation = () => {
    if (!inspectedEdge) return;
    onUpdateRelation(inspectedEdge.id, {
      status: 'confirmed',
      version: inspectedEdge.version,
    });
    setInspectedEdge(null);
  };

  const handleDeleteInspectedRelation = () => {
    if (!inspectedEdge) return;
    if (window.confirm(`Delete relationship "${inspectedEdge.type}"?`)) {
      onDeleteRelation(inspectedEdge.id);
      setInspectedEdge(null);
    }
  };

  return (
    <div
      style={{
        position: 'relative',
        height: '100%',
        width: '100%',
        background: '#ffffff',
        borderRadius: 0,
        border: '1px solid #000000',
        overflow: 'clip',
        minHeight: 0,
        minWidth: 0,
      }}
    >
      {/* Top Filter Bar */}
      <div
        style={{
          position: 'absolute',
          top: 12,
          left: 12,
          right: 12,
          zIndex: 10,
          background: '#ffffff',
          borderRadius: 0,
          padding: '8px 12px',
          border: '1.5px solid #000000',
          display: 'flex',
          alignItems: 'center',
          gap: '12px',
          fontSize: '0.78rem',
          boxShadow: 'none',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: '#000000' }}>
          <Filter size={13} strokeWidth={1.5} />
          <span
            style={{
              fontFamily: '"JetBrains Mono", monospace',
              fontWeight: 700,
              textTransform: 'uppercase',
              letterSpacing: '0.05em',
            }}
          >
            Filter:
          </span>
        </div>

        <select
          value={filterLabel}
          onChange={(e) => setFilterLabel(e.target.value)}
          style={{
            padding: '4px 8px',
            borderRadius: 0,
            border: '1px solid #000000',
            fontSize: '0.75rem',
            fontFamily: '"JetBrains Mono", monospace',
            background: '#ffffff',
            color: '#000000',
          }}
        >
          <option value="ALL">All Labels</option>
          {taxonomy?.labels?.map((lbl) => (
            <option key={lbl} value={lbl}>
              {lbl}
            </option>
          ))}
        </select>

        <select
          value={filterRelType}
          onChange={(e) => setFilterRelType(e.target.value)}
          style={{
            padding: '4px 8px',
            borderRadius: 0,
            border: '1px solid #000000',
            fontSize: '0.75rem',
            fontFamily: '"JetBrains Mono", monospace',
            background: '#ffffff',
            color: '#000000',
          }}
        >
          <option value="ALL">All Relation Types</option>
          {taxonomy?.relation_types?.map((rel) => (
            <option key={rel} value={rel}>
              {rel}
            </option>
          ))}
        </select>

        <label
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            cursor: 'pointer',
            color: '#000000',
            fontFamily: '"JetBrains Mono", monospace',
            fontSize: '0.72rem',
          }}
        >
          <input
            type="checkbox"
            checked={showNeighborsOnly}
            onChange={(e) => setShowNeighborsOnly(e.target.checked)}
            style={{ accentColor: '#000000' }}
          />
          <span>Neighbors only</span>
        </label>

        <label
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            cursor: 'pointer',
            color: '#000000',
            fontFamily: '"JetBrains Mono", monospace',
            fontSize: '0.72rem',
          }}
        >
          <input
            type="checkbox"
            data-testid="toggle-similar-to"
            checked={showSimilarTo}
            onChange={(e) => setShowSimilarTo(e.target.checked)}
            style={{ accentColor: '#000000' }}
          />
          <span>Show accepted similar_to</span>
        </label>

        <button
          type="button"
          onClick={handleAutoLayout}
          style={{
            marginLeft: 'auto',
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            padding: '5px 12px',
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
          title="Auto arrange nodes with Dagre layout"
        >
          <Layers size={13} strokeWidth={1.5} color="#ffffff" />
          <span>Auto Layout</span>
        </button>
      </div>

      {/* React Flow Canvas */}
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        connectionMode={ConnectionMode.Loose}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeDragStop={handleNodeDragStop}
        onConnect={handleConnect}
        onNodeClick={(_, node) => onSelectAnnotation(node.data?.annotation?.id)}
        onEdgeClick={handleEdgeClick}
        fitView
      >
        <Background color="#000000" gap={24} size={1} />
        <Controls />
      </ReactFlow>

      {/* Modal for creating a new relation when dragging between handles */}
      {pendingConnection && (
        <div
          style={{
            position: 'absolute',
            top: '50%',
            left: '50%',
            transform: 'translate(-50%, -50%)',
            background: '#ffffff',
            borderRadius: 0,
            padding: '20px 24px',
            boxShadow: 'none',
            border: '2px solid #000000',
            zIndex: 100,
            width: '320px',
          }}
        >
          <h4
            style={{
              margin: '0 0 10px 0',
              fontFamily: '"Playfair Display", Georgia, serif',
              fontSize: '1.1rem',
              color: '#000000',
              fontWeight: 700,
            }}
          >
            Create Relationship
          </h4>
          <p
            style={{
              margin: '0 0 14px 0',
              fontFamily: '"Source Serif 4", Georgia, serif',
              fontSize: '0.82rem',
              color: '#525252',
            }}
          >
            Choose the relationship type to connect these two annotations:
          </p>
          <select
            value={selectedRelType}
            onChange={(e) => setSelectedRelType(e.target.value)}
            style={{
              width: '100%',
              padding: '7px 10px',
              borderRadius: 0,
              border: '1.5px solid #000000',
              fontFamily: '"JetBrains Mono", monospace',
              fontSize: '0.82rem',
              marginBottom: '16px',
              background: '#ffffff',
              color: '#000000',
            }}
          >
            {taxonomy?.relation_types?.map((rel) => (
              <option key={rel} value={rel}>
                {rel}
              </option>
            ))}
          </select>
          <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end' }}>
            <button
              type="button"
              onClick={() => setPendingConnection(null)}
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
                cursor: 'pointer',
              }}
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={confirmCreateRelation}
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
                cursor: 'pointer',
              }}
            >
              Link Nodes
            </button>
          </div>
        </div>
      )}

      {/* Modal for inspecting/confirming/deleting an clicked edge */}
      {inspectedEdge && (
        <div
          style={{
            position: 'absolute',
            top: '50%',
            left: '50%',
            transform: 'translate(-50%, -50%)',
            background: '#ffffff',
            borderRadius: 0,
            padding: '20px 24px',
            boxShadow: 'none',
            border: '2px solid #000000',
            zIndex: 100,
            width: '340px',
          }}
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
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              {inspectedEdge.status === 'suggested' ? (
                <Sparkles size={16} strokeWidth={1.5} color="#000000" />
              ) : (
                <CheckCircle2 size={16} strokeWidth={1.5} color="#000000" />
              )}
              <h4
                style={{
                  margin: 0,
                  fontFamily: '"Playfair Display", Georgia, serif',
                  fontSize: '1rem',
                  color: '#000000',
                  fontWeight: 700,
                }}
              >
                {inspectedEdge.type}
              </h4>
            </div>
            <span
              style={{
                fontFamily: '"JetBrains Mono", monospace',
                fontSize: '0.68rem',
                padding: '2px 6px',
                borderRadius: 0,
                fontWeight: 700,
                textTransform: 'uppercase',
                border: '1px solid #000000',
                background: inspectedEdge.status === 'suggested' ? '#ffffff' : '#000000',
                color: inspectedEdge.status === 'suggested' ? '#000000' : '#ffffff',
                letterSpacing: '0.05em',
              }}
            >
              {inspectedEdge.status}
            </span>
          </div>

          {inspectedEdge.reason && (
            <p
              style={{
                margin: '0 0 16px 0',
                fontFamily: '"Source Serif 4", Georgia, serif',
                fontSize: '0.82rem',
                color: '#000000',
                lineHeight: 1.45,
              }}
            >
              <strong style={{ fontFamily: '"JetBrains Mono", monospace' }}>AI Reasoning:</strong> {inspectedEdge.reason}
            </p>
          )}

          <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end', marginTop: '14px' }}>
            <button
              type="button"
              onClick={handleDeleteInspectedRelation}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '4px',
                padding: '6px 12px',
                borderRadius: 0,
                border: '1.5px solid #000000',
                background: '#ffffff',
                color: '#000000',
                fontFamily: '"JetBrains Mono", monospace',
                fontSize: '0.75rem',
                fontWeight: 600,
                textTransform: 'uppercase',
                cursor: 'pointer',
              }}
            >
              <Trash2 size={13} strokeWidth={1.5} />
              <span>Delete</span>
            </button>

            {inspectedEdge.status === 'suggested' && (
              <button
                type="button"
                onClick={handleConfirmSuggestedRelation}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '4px',
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
                  cursor: 'pointer',
                }}
              >
                <Check size={14} strokeWidth={1.5} />
                <span>Confirm</span>
              </button>
            )}

            <button
              type="button"
              onClick={() => setInspectedEdge(null)}
              style={{
                padding: '6px 12px',
                borderRadius: 0,
                border: '1.5px solid #000000',
                background: '#ffffff',
                color: '#000000',
                fontFamily: '"JetBrains Mono", monospace',
                fontSize: '0.75rem',
                fontWeight: 600,
                textTransform: 'uppercase',
                cursor: 'pointer',
              }}
            >
              Close
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

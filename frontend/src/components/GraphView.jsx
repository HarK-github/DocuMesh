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
} from 'lucide-react';
import { getLabelStyle } from '../lib/colors';

const NODE_WIDTH = 240;
const NODE_HEIGHT = 100;

/**
 * Custom React Flow Node with prominent handles on all 4 borders.
 * Allows easy drag-to-connect from any side.
 */
function AnnotationNode({ _id, data, selected }) {
  const ann = data?.annotation;
  if (!ann) return null;

  const theme = getLabelStyle(ann.label);

  return (
    <div
      style={{
        width: NODE_WIDTH,
        minHeight: NODE_HEIGHT,
        borderRadius: '10px',
        border: selected ? '2.5px solid #2563eb' : `1.5px solid ${theme.border}`,
        background: selected ? '#ffffff' : theme.bg,
        boxShadow: selected
          ? '0 6px 20px rgba(37, 99, 235, 0.25)'
          : '0 2px 8px rgba(0, 0, 0, 0.06)',
        padding: '10px 12px',
        position: 'relative',
        cursor: 'grab',
        transition: 'border 0.15s ease, box-shadow 0.15s ease',
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

      {/* Header: Label Badge + Version */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: '6px',
        }}
      >
        <span
          style={{
            fontWeight: 700,
            color: theme.text,
            background: theme.badge,
            padding: '2px 8px',
            borderRadius: '4px',
            textTransform: 'uppercase',
            fontSize: '0.68rem',
            letterSpacing: '0.04em',
          }}
        >
          {ann.label}
        </span>
        <span style={{ color: '#94a3b8', fontSize: '0.65rem', fontWeight: 600 }}>
          v{ann.version}
        </span>
      </div>

      {/* Quote Preview */}
      <div
        style={{
          fontStyle: 'italic',
          color: '#1e293b',
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
            marginTop: '6px',
            fontSize: '0.7rem',
            color: '#64748b',
            whiteSpace: 'nowrap',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
          }}
          title={ann.note}
        >
          {ann.note}
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
  onCreateRelation = () => {},
  onUpdateRelation = () => {},
  onSaveNodePosition = () => {},
  onDeleteRelation = () => {},
}) {
  const [filterLabel, setFilterLabel] = useState('ALL');
  const [filterRelType, setFilterRelType] = useState('ALL');
  const [showNeighborsOnly, setShowNeighborsOnly] = useState(false);

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
    let anns = annotations;
    let rels = relations;

    // Filter by label
    if (filterLabel !== 'ALL') {
      anns = anns.filter((a) => a.label === filterLabel);
    }

    // Filter by relation type
    if (filterRelType !== 'ALL') {
      rels = rels.filter((r) => r.type === filterRelType);
    }

    // Filter neighbors of selected node
    if (showNeighborsOnly && selectedAnnotationId) {
      const neighborIds = new Set([selectedAnnotationId]);
      relations.forEach((r) => {
        if (r.source_id === selectedAnnotationId) neighborIds.add(r.target_id);
        if (r.target_id === selectedAnnotationId) neighborIds.add(r.source_id);
      });
      anns = anns.filter((a) => neighborIds.has(a.id));
      rels = rels.filter((r) => neighborIds.has(r.source_id) && neighborIds.has(r.target_id));
    }

    return { filteredAnnotations: anns, filteredRelations: rels };
  }, [annotations, relations, filterLabel, filterRelType, showNeighborsOnly, selectedAnnotationId]);

  // Transform annotations to React Flow nodes
  const initialNodes = useMemo(() => {
    return filteredAnnotations.map((ann, idx) => {
      // If position is unassigned or (0,0), distribute across a clean grid
      const posX = ann.x && ann.x !== 0 ? ann.x : 60 + (idx % 3) * 290;
      const posY = ann.y && ann.y !== 0 ? ann.y : 80 + Math.floor(idx / 3) * 160;

      return {
        id: String(ann.id),
        type: 'annotation',
        position: { x: posX, y: posY },
        selected: ann.id === selectedAnnotationId,
        data: {
          annotation: ann,
        },
      };
    });
  }, [filteredAnnotations, selectedAnnotationId]);

  // Transform relations to React Flow edges with optimal handles and badges
  const initialEdges = useMemo(() => {
    const annMap = new Map(filteredAnnotations.map((a) => [String(a.id), a]));

    return filteredRelations
      .filter((r) => annMap.has(String(r.source_id)) && annMap.has(String(r.target_id)))
      .map((rel) => {
        const isSuggested = rel.status === 'suggested';
        const srcAnn = annMap.get(String(rel.source_id));
        const tgtAnn = annMap.get(String(rel.target_id));

        // Smart handle alignment based on relative coordinates
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

        const isFocused = rel.id === selectedRelationId;
        const strokeColor = isFocused
          ? '#2563eb'
          : isSuggested
          ? '#f59e0b'
          : rel.type === 'contradicts'
          ? '#ef4444'
          : '#64748b';

        return {
          id: `edge-${rel.id}`,
          source: String(rel.source_id),
          target: String(rel.target_id),
          sourceHandle,
          targetHandle,
          type: 'smoothstep',
          pathOptions: { borderRadius: 16 },
          label: rel.type,
          animated: isSuggested || isFocused,
          style: {
            stroke: strokeColor,
            strokeWidth: isFocused ? 4 : 2,
            strokeDasharray: isSuggested && !isFocused ? '6,4' : undefined,
          },
          markerEnd: {
            type: MarkerType.ArrowClosed,
            width: 20,
            height: 20,
            color: strokeColor,
          },
          labelStyle: {
            fill: isSuggested ? '#92400e' : '#1e40af',
            fontWeight: 700,
            fontSize: 11,
          },
          labelBgStyle: {
            fill: isSuggested ? '#fef3c7' : '#eff6ff',
            fillOpacity: 0.96,
            stroke: isSuggested ? '#f59e0b' : '#93c5fd',
            strokeWidth: 1.5,
            rx: 6,
            ry: 6,
          },
          labelBgPadding: [6, 4],
          labelBgBorderRadius: 6,
          data: { relation: rel },
        };
      });
  }, [filteredRelations, filteredAnnotations]);

  const [nodes, setNodes] = useState(initialNodes);
  const [edges, setEdges] = useState(initialEdges);

  // Sync state when props or filtered inputs change
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
    // Persist new layout positions to the database
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
        background: '#f8fafc',
        borderRadius: '12px',
        border: '1px solid #e2e8f0',
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
          background: 'rgba(255, 255, 255, 0.95)',
          backdropFilter: 'blur(8px)',
          borderRadius: '8px',
          padding: '8px 12px',
          border: '1px solid #e2e8f0',
          display: 'flex',
          alignItems: 'center',
          gap: '12px',
          fontSize: '0.8rem',
          boxShadow: '0 2px 6px rgba(0,0,0,0.04)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '4px', color: '#64748b' }}>
          <Filter size={14} />
          <span style={{ fontWeight: 600 }}>Filter:</span>
        </div>

        <select
          value={filterLabel}
          onChange={(e) => setFilterLabel(e.target.value)}
          style={{ padding: '4px 8px', borderRadius: '4px', border: '1px solid #cbd5e1', fontSize: '0.75rem' }}
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
          style={{ padding: '4px 8px', borderRadius: '4px', border: '1px solid #cbd5e1', fontSize: '0.75rem' }}
        >
          <option value="ALL">All Relation Types</option>
          {taxonomy?.relation_types?.map((rel) => (
            <option key={rel} value={rel}>
              {rel}
            </option>
          ))}
        </select>

        <label style={{ display: 'flex', alignItems: 'center', gap: '4px', cursor: 'pointer', color: '#475569' }}>
          <input
            type="checkbox"
            checked={showNeighborsOnly}
            onChange={(e) => setShowNeighborsOnly(e.target.checked)}
          />
          <span>Neighbors only</span>
        </label>

        <button
          type="button"
          onClick={handleAutoLayout}
          style={{
            marginLeft: 'auto',
            display: 'flex',
            alignItems: 'center',
            gap: '4px',
            padding: '5px 10px',
            borderRadius: '6px',
            border: '1px solid #cbd5e1',
            background: '#ffffff',
            fontSize: '0.75rem',
            fontWeight: 500,
            cursor: 'pointer',
            boxShadow: '0 1px 2px rgba(0,0,0,0.05)',
          }}
          title="Auto arrange nodes with Dagre layout"
        >
          <Layers size={13} />
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
        onNodeClick={(_, node) => onSelectAnnotation(parseInt(node.id, 10))}
        onEdgeClick={handleEdgeClick}
        fitView
      >
        <Background color="#cbd5e1" gap={16} />
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
            borderRadius: '10px',
            padding: '18px 22px',
            boxShadow: '0 12px 30px rgba(0,0,0,0.18)',
            border: '1px solid #e2e8f0',
            zIndex: 100,
            width: '300px',
          }}
        >
          <h4 style={{ margin: '0 0 12px 0', fontSize: '0.95rem', color: '#0f172a', fontWeight: 600 }}>
            Create Relationship
          </h4>
          <p style={{ margin: '0 0 12px 0', fontSize: '0.78rem', color: '#64748b' }}>
            Choose the relationship type to connect these two annotations:
          </p>
          <select
            value={selectedRelType}
            onChange={(e) => setSelectedRelType(e.target.value)}
            style={{
              width: '100%',
              padding: '7px 10px',
              borderRadius: '6px',
              border: '1px solid #cbd5e1',
              fontSize: '0.85rem',
              marginBottom: '16px',
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
                padding: '6px 12px',
                borderRadius: '6px',
                border: '1px solid #cbd5e1',
                background: '#fff',
                fontSize: '0.8rem',
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
                borderRadius: '6px',
                border: 'none',
                background: '#2563eb',
                color: '#fff',
                fontSize: '0.8rem',
                fontWeight: 600,
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
            borderRadius: '10px',
            padding: '18px 22px',
            boxShadow: '0 12px 30px rgba(0,0,0,0.18)',
            border: '1px solid #e2e8f0',
            zIndex: 100,
            width: '320px',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '10px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              {inspectedEdge.status === 'suggested' ? (
                <Sparkles size={16} color="#d97706" />
              ) : (
                <CheckCircle2 size={16} color="#2563eb" />
              )}
              <h4 style={{ margin: 0, fontSize: '0.95rem', color: '#0f172a', fontWeight: 600 }}>
                {inspectedEdge.type}
              </h4>
            </div>
            <span
              style={{
                fontSize: '0.7rem',
                padding: '2px 6px',
                borderRadius: '4px',
                fontWeight: 600,
                textTransform: 'uppercase',
                background: inspectedEdge.status === 'suggested' ? '#fef3c7' : '#dbeafe',
                color: inspectedEdge.status === 'suggested' ? '#b45309' : '#1e40af',
              }}
            >
              {inspectedEdge.status}
            </span>
          </div>

          {inspectedEdge.reason && (
            <p style={{ margin: '0 0 14px 0', fontSize: '0.78rem', color: '#475569', lineHeight: 1.4 }}>
              <strong>AI Reasoning:</strong> {inspectedEdge.reason}
            </p>
          )}

          <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end', marginTop: '12px' }}>
            <button
              type="button"
              onClick={handleDeleteInspectedRelation}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '4px',
                padding: '6px 10px',
                borderRadius: '6px',
                border: '1px solid #fecaca',
                background: '#fef2f2',
                color: '#dc2626',
                fontSize: '0.78rem',
                fontWeight: 500,
                cursor: 'pointer',
              }}
            >
              <Trash2 size={13} />
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
                  padding: '6px 12px',
                  borderRadius: '6px',
                  border: 'none',
                  background: '#16a34a',
                  color: '#fff',
                  fontSize: '0.78rem',
                  fontWeight: 600,
                  cursor: 'pointer',
                }}
              >
                <Check size={14} />
                <span>Confirm</span>
              </button>
            )}

            <button
              type="button"
              onClick={() => setInspectedEdge(null)}
              style={{
                padding: '6px 10px',
                borderRadius: '6px',
                border: '1px solid #cbd5e1',
                background: '#fff',
                fontSize: '0.78rem',
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

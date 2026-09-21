import React, { useState, useEffect, useCallback, useMemo } from 'react';
import ReactFlow, {
  Background,
  Controls,
  applyNodeChanges,
  applyEdgeChanges,
  MarkerType,
} from 'reactflow';
import 'reactflow/dist/style.css';
import dagre from 'dagre';
import { Share2, Filter, Layers, CheckCircle2 } from 'lucide-react';

const NODE_WIDTH = 220;
const NODE_HEIGHT = 90;

function getLayoutedElements(nodes, edges, direction = 'TB') {
  const dagreGraph = new dagre.graphlib.Graph();
  dagreGraph.setDefaultEdgeLabel(() => ({}));
  dagreGraph.setGraph({ rankdir: direction, nodesep: 50, ranksep: 70 });

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
        x: nodeWithPosition.x - NODE_WIDTH / 2,
        y: nodeWithPosition.y - NODE_HEIGHT / 2,
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
  onSelectAnnotation = () => {},
  onCreateRelation = () => {},
  onSaveNodePosition = () => {},
  onDeleteRelation = () => {},
}) {
  const [filterLabel, setFilterLabel] = useState('ALL');
  const [filterRelType, setFilterRelType] = useState('ALL');
  const [showNeighborsOnly, setShowNeighborsOnly] = useState(false);

  // Connection dialog state
  const [pendingConnection, setPendingConnection] = useState(null);
  const [selectedRelType, setSelectedRelType] = useState('');

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
    return filteredAnnotations.map((ann) => {
      const isSelected = ann.id === selectedAnnotationId;
      return {
        id: String(ann.id),
        type: 'default',
        position: { x: ann.x || 0, y: ann.y || 0 },
        data: {
          label: (
            <div style={{ textAlign: 'left', fontSize: '0.75rem', lineHeight: 1.3 }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '4px' }}>
                <span style={{ fontWeight: 700, color: '#1e40af', textTransform: 'uppercase', fontSize: '0.65rem' }}>
                  {ann.label}
                </span>
                <span style={{ color: '#94a3b8', fontSize: '0.65rem' }}>v{ann.version}</span>
              </div>
              <div
                style={{
                  fontStyle: 'italic',
                  color: '#334155',
                  maxHeight: '40px',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  display: '-webkit-box',
                  WebkitLineClamp: 2,
                  WebkitBoxOrient: 'vertical',
                }}
              >
                "{ann.quote}"
              </div>
            </div>
          ),
          annotation: ann,
        },
        style: {
          width: NODE_WIDTH,
          borderRadius: '8px',
          border: isSelected ? '2px solid #2563eb' : '1px solid #cbd5e1',
          background: isSelected ? '#eff6ff' : '#ffffff',
          boxShadow: isSelected ? '0 4px 12px rgba(37,99,235,0.2)' : '0 2px 4px rgba(0,0,0,0.05)',
          padding: '8px 10px',
        },
      };
    });
  }, [filteredAnnotations, selectedAnnotationId]);

  // Transform relations to React Flow edges
  const initialEdges = useMemo(() => {
    const annIdSet = new Set(filteredAnnotations.map((a) => String(a.id)));
    return filteredRelations
      .filter((r) => annIdSet.has(String(r.source_id)) && annIdSet.has(String(r.target_id)))
      .map((rel) => {
        const isSuggested = rel.status === 'suggested';
        return {
          id: String(rel.id),
          source: String(rel.source_id),
          target: String(rel.target_id),
          label: rel.type,
          animated: isSuggested,
          style: {
            stroke: isSuggested ? '#f59e0b' : '#64748b',
            strokeWidth: 2,
            strokeDasharray: isSuggested ? '5,5' : undefined,
          },
          markerEnd: {
            type: MarkerType.ArrowClosed,
            color: isSuggested ? '#f59e0b' : '#64748b',
          },
          data: { relation: rel },
        };
      });
  }, [filteredRelations, filteredAnnotations]);

  const [nodes, setNodes] = useState(initialNodes);
  const [edges, setEdges] = useState(initialEdges);

  // Sync state when props change
  useEffect(() => {
    // If all positions are 0 or unassigned, run dagre layout
    const needsLayout = initialNodes.length > 0 && initialNodes.every((n) => n.position.x === 0 && n.position.y === 0);
    if (needsLayout) {
      const layouted = getLayoutedElements(initialNodes, initialEdges);
      setNodes(layouted.nodes);
      setEdges(layouted.edges);
    } else {
      setNodes(initialNodes);
      setEdges(initialEdges);
    }
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
    const layouted = getLayoutedElements(nodes, edges);
    setNodes(layouted.nodes);
    setEdges(layouted.edges);
    // Save new positions
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

  return (
    <div
      style={{
        position: 'relative',
        height: '100%',
        width: '100%',
        background: '#f8fafc',
        borderRadius: '12px',
        border: '1px solid #e2e8f0',
        overflow: 'hidden',
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
          style={{ padding: '3px 6px', borderRadius: '4px', border: '1px solid #cbd5e1', fontSize: '0.75rem' }}
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
          style={{ padding: '3px 6px', borderRadius: '4px', border: '1px solid #cbd5e1', fontSize: '0.75rem' }}
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
            padding: '4px 8px',
            borderRadius: '4px',
            border: '1px solid #cbd5e1',
            background: '#ffffff',
            fontSize: '0.75rem',
            cursor: 'pointer',
          }}
        >
          <Layers size={13} />
          <span>Auto Layout</span>
        </button>
      </div>

      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeDragStop={handleNodeDragStop}
        onConnect={handleConnect}
        onNodeClick={(_, node) => onSelectAnnotation(parseInt(node.id, 10))}
        onEdgeClick={(_, edge) => {
          if (window.confirm(`Delete relation "${edge.label}"?`)) {
            onDeleteRelation(parseInt(edge.id, 10));
          }
        }}
        fitView
      >
        <Background color="#cbd5e1" gap={16} />
        <Controls />
      </ReactFlow>

      {/* Modal for choosing relation type when an edge is dragged */}
      {pendingConnection && (
        <div
          style={{
            position: 'absolute',
            top: '50%',
            left: '50%',
            transform: 'translate(-50%, -50%)',
            background: '#ffffff',
            borderRadius: '10px',
            padding: '16px 20px',
            boxShadow: '0 10px 25px rgba(0,0,0,0.15)',
            border: '1px solid #e2e8f0',
            zIndex: 100,
            width: '280px',
          }}
        >
          <h4 style={{ margin: '0 0 10px 0', fontSize: '0.9rem', color: '#1e293b' }}>
            Choose Relationship Type
          </h4>
          <select
            value={selectedRelType}
            onChange={(e) => setSelectedRelType(e.target.value)}
            style={{
              width: '100%',
              padding: '6px 8px',
              borderRadius: '6px',
              border: '1px solid #cbd5e1',
              fontSize: '0.85rem',
              marginBottom: '12px',
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
                padding: '5px 10px',
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
                padding: '5px 12px',
                borderRadius: '6px',
                border: 'none',
                background: '#2563eb',
                color: '#fff',
                fontSize: '0.8rem',
                fontWeight: 500,
                cursor: 'pointer',
              }}
            >
              Link
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

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
  Compass,
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

export function getRadialLayoutedElements(nodes, edges, focusNodeId = null) {
  if (!nodes || nodes.length === 0) return { nodes: [], edges: [] };

  const nodeMap = new Map(nodes.map((n) => [n.id, n]));
  const adj = new Map();
  nodes.forEach((n) => adj.set(n.id, new Set()));

  edges.forEach((e) => {
    if (adj.has(e.source) && adj.has(e.target)) {
      adj.get(e.source).add(e.target);
      adj.get(e.target).add(e.source);
    }
  });

  // 1. Identify Central Anchor Node (either user-selected or highest-scoring epistemic node)
  let centerId = focusNodeId && nodeMap.has(focusNodeId) ? focusNodeId : null;

  if (!centerId) {
    let bestScore = -1;
    nodes.forEach((n) => {
      const ann = n.data?.annotation;
      const deg = adj.get(n.id)?.size || 0;
      let score = deg * 3;
      if (ann?.label === 'Problem') score += 25;
      else if (ann?.label === 'Solution') score += 20;
      else if (ann?.label === 'Claim') score += 15;
      else if (ann?.label === 'Definition') score += 8;

      if (score > bestScore) {
        bestScore = score;
        centerId = n.id;
      }
    });
  }

  if (!centerId && nodes.length > 0) {
    centerId = nodes[0].id;
  }

  const layoutedNodes = [];
  const placed = new Set();

  // Place Central Anchor Node at (0, 0)
  const centerNode = nodeMap.get(centerId);
  if (centerNode) {
    layoutedNodes.push({
      ...centerNode,
      position: { x: 0, y: 0 },
    });
    placed.add(centerId);
  }

  // Ring 1: Direct Neighbors (Inner Semantic Orbit)
  const directNeighbors = Array.from(adj.get(centerId) || []).filter((id) => !placed.has(id));
  const r1 = Math.max(420, directNeighbors.length * 65);

  directNeighbors.forEach((nid, i) => {
    const angle = (2 * Math.PI * i) / Math.max(1, directNeighbors.length) - Math.PI / 2;
    const node = nodeMap.get(nid);
    if (node) {
      layoutedNodes.push({
        ...node,
        position: {
          x: Math.round(r1 * Math.cos(angle) - NODE_WIDTH / 2),
          y: Math.round(r1 * Math.sin(angle) - NODE_HEIGHT / 2),
        },
      });
      placed.add(nid);
    }
  });

  // Ring 2: Second-degree Neighbors (Intermediate Semantic Orbit)
  const secondNeighbors = [];
  directNeighbors.forEach((dnId) => {
    (adj.get(dnId) || []).forEach((n2) => {
      if (!placed.has(n2)) {
        placed.add(n2);
        secondNeighbors.push(n2);
      }
    });
  });

  const r2 = Math.max(r1 + 380, secondNeighbors.length * 60);
  secondNeighbors.forEach((nid, i) => {
    // Interleave angles so they don't visually clash with Ring 1 nodes
    const angle = (2 * Math.PI * i) / Math.max(1, secondNeighbors.length) - Math.PI / 2 + Math.PI / Math.max(1, secondNeighbors.length * 2);
    const node = nodeMap.get(nid);
    if (node) {
      layoutedNodes.push({
        ...node,
        position: {
          x: Math.round(r2 * Math.cos(angle) - NODE_WIDTH / 2),
          y: Math.round(r2 * Math.sin(angle) - NODE_HEIGHT / 2),
        },
      });
      placed.add(nid);
    }
  });

  // Ring 3: All remaining nodes (Outer Orbit - Never grid-wise!)
  const remaining = nodes.filter((n) => !placed.has(n.id));
  if (remaining.length > 0) {
    const r3 = Math.max(r2 + 400, remaining.length * 55);
    remaining.forEach((n, i) => {
      const angle = (2 * Math.PI * i) / Math.max(1, remaining.length) - Math.PI / 2;
      layoutedNodes.push({
        ...n,
        position: {
          x: Math.round(r3 * Math.cos(angle) - NODE_WIDTH / 2),
          y: Math.round(r3 * Math.sin(angle) - NODE_HEIGHT / 2),
        },
      });
      placed.add(n.id);
    });
  }

  return { nodes: layoutedNodes, edges };
}

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
  const [showSimilarTo, setShowSimilarTo] = useState(false);
  const [hideUnconnected, setHideUnconnected] = useState(false);
  const [layoutMode, setLayoutMode] = useState('radial');

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

  // Compute set of connected node IDs (nodes with at least 1 relationship)
  const connectedNodeIds = useMemo(() => {
    const ids = new Set();
    const relList = Array.isArray(relations) ? relations : [];
    relList.forEach((r) => {
      ids.add(r.source_id);
      ids.add(r.target_id);
    });
    return ids;
  }, [relations]);

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

    // Hide similar_to edges by default unless explicitly toggled on
    if (!showSimilarTo) {
      rels = rels.filter((r) => r.type !== 'similar_to');
    }

    // Deduplicate pair connections: Between any pair {u, v}, keep only ONE primary, highest-priority semantic relation
    const RELATION_PRIORITY = {
      solves: 100,
      supports: 90,
      contradicts: 85,
      enables: 80,
      causes: 75,
      defines: 60,
      elaborates: 50,
      part_of: 45,
      example_of: 30,
      similar_to: 10,
    };

    const bestEdgeByPair = new Map();
    rels.forEach((r) => {
      const u = Number(r.source_id);
      const v = Number(r.target_id);
      if (u === v) return; // Prune self-loops

      const pairKey = u < v ? `${u}-${v}` : `${v}-${u}`;
      const basePri = RELATION_PRIORITY[r.type] || 20;
      const statusBonus = r.status === 'confirmed' ? 200 : (r.status === 'auto_candidate' ? 100 : 0);
      const score = basePri + statusBonus + (r.score ? r.score * 10 : 0);

      const existing = bestEdgeByPair.get(pairKey);
      if (!existing || score > existing.score) {
        bestEdgeByPair.set(pairKey, { rel: r, score });
      }
    });

    rels = Array.from(bestEdgeByPair.values()).map((item) => item.rel);

    // Filter out unconnected / isolated nodes if toggled on
    if (hideUnconnected) {
      anns = anns.filter((a) => connectedNodeIds.has(a.id));
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
  }, [
    annotations,
    relations,
    filterLabel,
    filterRelType,
    showSimilarTo,
    hideUnconnected,
    connectedNodeIds,
    showNeighborsOnly,
    selectedAnnotationId,
  ]);

  // Transform annotations to React Flow nodes
  const initialNodes = useMemo(() => {
    const list = Array.isArray(filteredAnnotations) ? filteredAnnotations : [];
    const hasCustomCoords = list.some((a) => (a.x && a.x !== 0) || (a.y && a.y !== 0));

    const rawNodes = list.map((ann, idx) => {
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

    // Clean, organic concentric radial layout
    if (rawNodes.length > 0 && (layoutMode === 'radial' || !hasCustomCoords)) {
      const edgesForLayout = (Array.isArray(filteredRelations) ? filteredRelations : []).map((r) => ({
        source: String(r.source_id),
        target: String(r.target_id),
      }));
      const layouted = getRadialLayoutedElements(
        rawNodes,
        edgesForLayout,
        selectedAnnotationId ? String(selectedAnnotationId) : null
      );
      return layouted.nodes;
    }

    return rawNodes;
  }, [
    filteredAnnotations,
    filteredRelations,
    selectedAnnotationId,
    layoutMode,
    onAcceptSuggestion,
    onRejectSuggestion,
  ]);

  // Transform relations to React Flow edges
  const initialEdges = useMemo(() => {
    const annKeyMap = new Map();
    const nodePosMap = new Map();
    const annList = Array.isArray(filteredAnnotations) ? filteredAnnotations : [];
    annList.forEach((a) => {
      const k = a.status === 'suggested' ? `sug-${a.id}` : String(a.id);
      annKeyMap.set(k, a);
    });

    (initialNodes || []).forEach((n) => {
      nodePosMap.set(n.id, n.position);
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

        let sourceHandle = 'bottom';
        let targetHandle = 'top';

        const srcPos = nodePosMap.get(sourceKey);
        const tgtPos = nodePosMap.get(targetKey);

        if (srcPos && tgtPos) {
          const dx = tgtPos.x - srcPos.x;
          const dy = tgtPos.y - srcPos.y;

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

        // Color code relations by semantic taxonomy
        const REL_COLOR_MAP = {
          solves: '#0284c7', // Sky Blue
          supports: '#059669', // Emerald
          defines: '#7c3aed', // Purple/Violet
          causes: '#ea580c', // Orange
          enables: '#0d9488', // Teal
          contradicts: '#e11d48', // Crimson Rose
          part_of: '#6366f1', // Indigo
          elaborates: '#d97706', // Amber
          example_of: '#4b5563', // Slate Gray
          similar_to: '#a3a3a3', // Light Gray
        };

        const relColor = REL_COLOR_MAP[rel.type] || '#262626';
        const strokeColor = isImplied ? '#737373' : (isFocused ? '#000000' : relColor);

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
          type: 'default', // Smooth curved Bezier!
          label: edgeLabel,
          animated: (isSuggested || isFocused) && !isImplied,
          style: {
            stroke: strokeColor,
            strokeWidth: isFocused ? 3.5 : (isImplied ? 1.4 : 2.0),
            strokeDasharray: dashArray,
            opacity: isFocused ? 1 : 0.88,
          },
          markerEnd: {
            type: MarkerType.ArrowClosed,
            width: 14,
            height: 14,
            color: strokeColor,
          },
          labelStyle: {
            fill: strokeColor,
            fontFamily: '"JetBrains Mono", monospace',
            fontWeight: 700,
            fontSize: 10,
          },
          labelBgStyle: {
            fill: '#ffffff',
            fillOpacity: 0.95,
            stroke: strokeColor,
            strokeWidth: 1.2,
            rx: 6,
            ry: 6,
          },
          labelBgPadding: [6, 4],
          data: { relation: rel },
        };
      })
      .filter(Boolean);
  }, [filteredAnnotations, filteredRelations, initialNodes, selectedRelationId]);

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

  const handleRadialLayout = () => {
    setLayoutMode('radial');
    const layouted = getRadialLayoutedElements(
      nodes,
      edges,
      selectedAnnotationId ? String(selectedAnnotationId) : null
    );
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

  const handleDagreLayout = () => {
    setLayoutMode('tree');
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
          flexWrap: 'wrap',
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
          title="Show only direct neighbors of the selected node"
        >
          <input
            type="checkbox"
            data-testid="toggle-neighbors-only"
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
          title="Remove unlinked/isolated highlights from the stage"
        >
          <input
            type="checkbox"
            data-testid="toggle-hide-unconnected"
            checked={hideUnconnected}
            onChange={(e) => setHideUnconnected(e.target.checked)}
            style={{ accentColor: '#000000' }}
          />
          <span>Connected only ({connectedNodeIds.size})</span>
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
          title="Toggle visibility of similar_to edges"
        >
          <input
            type="checkbox"
            data-testid="toggle-similar-to"
            checked={showSimilarTo}
            onChange={(e) => setShowSimilarTo(e.target.checked)}
            style={{ accentColor: '#000000' }}
          />
          <span>Show similar_to</span>
        </label>

        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <button
            type="button"
            data-testid="btn-radial-layout"
            onClick={handleRadialLayout}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '5px 12px',
              borderRadius: 0,
              border: '1.5px solid #000000',
              background: layoutMode === 'radial' ? '#000000' : '#ffffff',
              color: layoutMode === 'radial' ? '#ffffff' : '#000000',
              fontFamily: '"JetBrains Mono", monospace',
              fontSize: '0.72rem',
              fontWeight: 600,
              textTransform: 'uppercase',
              letterSpacing: '0.06em',
              cursor: 'pointer',
              transition: 'none',
            }}
            title={selectedAnnotationId ? "Radially expand around selected node" : "Concentric radial orbit layout"}
          >
            <Compass size={13} strokeWidth={1.5} color={layoutMode === 'radial' ? '#ffffff' : '#000000'} />
            <span>Radial Layout</span>
          </button>

          <button
            type="button"
            data-testid="btn-dagre-layout"
            onClick={handleDagreLayout}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '5px 12px',
              borderRadius: 0,
              border: '1.5px solid #000000',
              background: layoutMode === 'tree' ? '#000000' : '#ffffff',
              color: layoutMode === 'tree' ? '#ffffff' : '#000000',
              fontFamily: '"JetBrains Mono", monospace',
              fontSize: '0.72rem',
              fontWeight: 600,
              textTransform: 'uppercase',
              letterSpacing: '0.06em',
              cursor: 'pointer',
              transition: 'none',
            }}
            title="Auto arrange nodes with Dagre Left-to-Right hierarchy"
          >
            <Layers size={13} strokeWidth={1.5} color={layoutMode === 'tree' ? '#ffffff' : '#000000'} />
            <span>Tree Layout</span>
          </button>
        </div>
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

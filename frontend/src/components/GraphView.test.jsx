import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import { ReactFlowProvider } from 'reactflow';
import { AnnotationNode, getRadialLayoutedElements } from './GraphView';

describe('GraphView AnnotationNode styling and ghost nodes', () => {
  it('renders confirmed annotation node with solid border and no ghost actions', () => {
    const ann = {
      id: 1,
      label: 'Claim',
      quote: 'Machines can think computationally.',
      version: 2,
      status: 'confirmed',
    };

    const html = renderToStaticMarkup(
      <ReactFlowProvider>
        <AnnotationNode
          data={{ annotation: ann }}
          selected={false}
        />
      </ReactFlowProvider>
    );

    expect(html).toContain('data-status="confirmed"');
    expect(html).toContain('solid');
    expect(html).not.toContain('dashed');
    expect(html).toContain('v2');
    expect(html).not.toContain('Accept');
    expect(html).not.toContain('Reject');
  });

  it('renders suggested ghost node with dashed border, faded opacity, and action buttons', () => {
    const ghostAnn = {
      id: 5,
      label: 'Claim',
      quote: 'Computers perform high-dimensional linear algebra.',
      score: 0.88,
      status: 'suggested',
      seed_annotation_id: 1,
    };

    const html = renderToStaticMarkup(
      <ReactFlowProvider>
        <AnnotationNode
          data={{ annotation: ghostAnn }}
          selected={false}
        />
      </ReactFlowProvider>
    );

    expect(html).toContain('data-status="suggested"');
    expect(html).toContain('dashed');
    expect(html).toContain('opacity:0.72');
    expect(html).toContain('88%');
    expect(html).toContain('Accept');
    expect(html).toContain('Reject');
    expect(html).toContain('ghost');
  });

  it('triggers onAccept and onReject callbacks when ghost buttons are clicked', () => {
    const onAccept = vi.fn();
    const onReject = vi.fn();
    const ghostAnn = {
      id: 12,
      label: 'Method',
      quote: 'Neural networks optimize cross entropy loss.',
      score: 0.92,
      status: 'suggested',
    };

    const element = AnnotationNode({
      data: {
        annotation: ghostAnn,
        onAccept,
        onReject,
      },
      selected: false,
    });

    // The element contains children: 4 handles, header, quote, note/actions
    const actionContainer = element.props.children[element.props.children.length - 1];
    const [acceptBtn, rejectBtn] = actionContainer.props.children;

    const stopPropagation = vi.fn();
    acceptBtn.props.onClick({ stopPropagation });
    expect(onAccept).toHaveBeenCalledWith(12);

    rejectBtn.props.onClick({ stopPropagation });
    expect(onReject).toHaveBeenCalledWith(12);
  });

  it('calculates radial layout coordinates fanning out around hub nodes', () => {
    const testNodes = [
      { id: '1', data: { annotation: { id: 1, label: 'Problem', quote: 'Challenge' } }, position: { x: 0, y: 0 } },
      { id: '2', data: { annotation: { id: 2, label: 'Solution', quote: 'Answer' } }, position: { x: 0, y: 0 } },
      { id: '3', data: { annotation: { id: 3, label: 'Method', quote: 'Algorithm' } }, position: { x: 0, y: 0 } },
      { id: '4', data: { annotation: { id: 4, label: 'Result', quote: 'Outcome' } }, position: { x: 0, y: 0 } },
    ];
    const testEdges = [
      { source: '1', target: '2' },
      { source: '1', target: '3' },
      { source: '2', target: '4' },
    ];

    const result = getRadialLayoutedElements(testNodes, testEdges);
    expect(result.nodes).toHaveLength(4);
    // Ensure nodes receive non-overlapping radial positions
    const posKeys = new Set(result.nodes.map((n) => `${n.position.x},${n.position.y}`));
    expect(posKeys.size).toBe(4);
  });

  it('calculates focused radial layout with focus node at origin (0, 0)', () => {
    const testNodes = [
      { id: '10', data: { annotation: { id: 10, label: 'Problem', quote: 'Root Problem' } }, position: { x: 0, y: 0 } },
      { id: '11', data: { annotation: { id: 11, label: 'Solution', quote: 'Direct Sol' } }, position: { x: 0, y: 0 } },
      { id: '12', data: { annotation: { id: 12, label: 'Method', quote: 'Direct Method' } }, position: { x: 0, y: 0 } },
    ];
    const testEdges = [
      { source: '10', target: '11' },
      { source: '10', target: '12' },
    ];

    const result = getRadialLayoutedElements(testNodes, testEdges, '10');
    expect(result.nodes).toHaveLength(3);
    const centerNode = result.nodes.find((n) => n.id === '10');
    expect(centerNode.position.x).toBe(0);
    expect(centerNode.position.y).toBe(0);

    const neighbor11 = result.nodes.find((n) => n.id === '11');
    const neighbor12 = result.nodes.find((n) => n.id === '12');
    expect(neighbor11.position.x !== 0 || neighbor11.position.y !== 0).toBe(true);
    expect(neighbor12.position.x !== 0 || neighbor12.position.y !== 0).toBe(true);
  });
});

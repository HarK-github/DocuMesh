import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import { ReactFlowProvider } from 'reactflow';
import { AnnotationNode } from './GraphView';

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
});

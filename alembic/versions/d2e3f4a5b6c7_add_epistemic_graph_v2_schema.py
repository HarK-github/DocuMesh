"""add_epistemic_graph_v2_schema

Revision ID: d2e3f4a5b6c7
Revises: c1f2e3d4a5b6
Create Date: 2026-11-11

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'd2e3f4a5b6c7'
down_revision: Union[str, Sequence[str], None] = 'c1f2e3d4a5b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. extraction_runs
    op.create_table(
        'extraction_runs',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('document_id', sa.Integer(), sa.ForeignKey('documents.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('graph_version', sa.Integer(), nullable=False, server_default='2'),
        sa.Column('model_name', sa.String(length=128), nullable=False),
        sa.Column('prompt_version', sa.String(length=64), nullable=False),
        sa.Column('config', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='draft'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    )
    # Guarantee only one active run per document
    op.create_index(
        'uq_active_run_per_doc',
        'extraction_runs',
        ['document_id'],
        unique=True,
        postgresql_where=sa.text('is_active = true')
    )

    # 2. propositions
    op.create_table(
        'propositions',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('document_id', sa.Integer(), sa.ForeignKey('documents.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('run_id', sa.Integer(), sa.ForeignKey('extraction_runs.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('canonical_statement', sa.Text(), nullable=False),
        sa.Column('statement_type', sa.String(length=32), nullable=False),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('confidence', sa.Numeric(precision=4, scale=3), nullable=False),
        sa.Column('review_status', sa.String(length=32), nullable=False, server_default='auto_candidate'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    )
    op.create_index('idx_props_run_type', 'propositions', ['run_id', 'statement_type'])

    # 3. concepts
    op.create_table(
        'concepts',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('document_id', sa.Integer(), sa.ForeignKey('documents.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('run_id', sa.Integer(), sa.ForeignKey('extraction_runs.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('canonical_name', sa.String(length=255), nullable=False),
        sa.Column('category', sa.String(length=64), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.UniqueConstraint('run_id', 'canonical_name', name='uq_run_canonical_concept')
    )

    # 4. proposition_highlights (provenance junction)
    op.create_table(
        'proposition_highlights',
        sa.Column('proposition_id', sa.Integer(), sa.ForeignKey('propositions.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('highlight_id', sa.Integer(), sa.ForeignKey('annotations.id', ondelete='CASCADE'), primary_key=True),
    )
    op.create_index('idx_prop_hl_highlight', 'proposition_highlights', ['highlight_id'])

    # 5. proposition_concept_links
    op.create_table(
        'proposition_concept_links',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('proposition_id', sa.Integer(), sa.ForeignKey('propositions.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('concept_id', sa.Integer(), sa.ForeignKey('concepts.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('mention_type', sa.String(length=64), nullable=False, server_default='mentions'),
        sa.UniqueConstraint('proposition_id', 'concept_id', name='uq_prop_concept_link')
    )

    # 6. graph_edges
    op.create_table(
        'graph_edges',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('document_id', sa.Integer(), sa.ForeignKey('documents.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('run_id', sa.Integer(), sa.ForeignKey('extraction_runs.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('source_kind', sa.String(length=32), nullable=False),
        sa.Column('source_id', sa.Integer(), nullable=False),
        sa.Column('target_kind', sa.String(length=32), nullable=False),
        sa.Column('target_id', sa.Integer(), nullable=False),
        sa.Column('relation_type', sa.String(length=64), nullable=False),
        sa.Column('direction', sa.String(length=16), nullable=False, server_default='forward'),
        sa.Column('confidence', sa.Numeric(precision=4, scale=3), nullable=False),
        sa.Column('rationale', sa.Text(), nullable=False),
        sa.Column('review_status', sa.String(length=32), nullable=False, server_default='auto_candidate'),
        sa.Column('extraction_method', sa.String(length=32), nullable=False, server_default='llm'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.CheckConstraint('confidence >= 0.0 AND confidence <= 1.0', name='chk_edge_confidence_bounds'),
        sa.CheckConstraint('NOT (source_kind = target_kind AND source_id = target_id)', name='chk_edge_no_self_loops')
    )
    op.create_index('idx_graph_edges_run_conf', 'graph_edges', ['run_id', 'confidence', 'review_status'])
    op.create_index('idx_graph_edges_run_src', 'graph_edges', ['run_id', 'source_kind', 'source_id'])
    op.create_index('idx_graph_edges_run_tgt', 'graph_edges', ['run_id', 'target_kind', 'target_id'])

    # 7. edge_evidence
    op.create_table(
        'edge_evidence',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('edge_id', sa.Integer(), sa.ForeignKey('graph_edges.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('highlight_id', sa.Integer(), sa.ForeignKey('annotations.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('evidence_quote', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    )

    # 8. extraction_run_activation_history
    op.create_table(
        'extraction_run_activation_history',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('document_id', sa.Integer(), sa.ForeignKey('documents.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('run_id', sa.Integer(), sa.ForeignKey('extraction_runs.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('previous_run_id', sa.Integer(), sa.ForeignKey('extraction_runs.id', ondelete='SET NULL'), nullable=True),
        sa.Column('action', sa.String(length=32), nullable=False),  # 'activate', 'rollback'
        sa.Column('activated_by', sa.String(length=128), nullable=False, server_default='admin'),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('activated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    )
    op.create_index('idx_activation_doc_time', 'extraction_run_activation_history', ['document_id', 'activated_at'])

    # 9. legacy_edge_reviews (tracks reviewer decisions on legacy relations vs V2)
    op.create_table(
        'legacy_edge_reviews',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('run_id', sa.Integer(), sa.ForeignKey('extraction_runs.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('legacy_relation_id', sa.Integer(), sa.ForeignKey('relations.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('classification', sa.String(length=64), nullable=False),
        sa.Column('reviewer_reason', sa.Text(), nullable=True),
        sa.Column('mapped_edge_id', sa.Integer(), sa.ForeignKey('graph_edges.id', ondelete='SET NULL'), nullable=True),
        sa.Column('reviewed_by', sa.String(length=128), nullable=False, server_default='reviewer'),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.CheckConstraint(
            "classification IN ('retained', 'merged', 'demoted_to_review', 'rejected', 'replaced_by_new_edge')",
            name='chk_legacy_review_classification'
        ),
        sa.UniqueConstraint('run_id', 'legacy_relation_id', name='uq_run_legacy_rel_review')
    )


def downgrade() -> None:
    # Drop in exact reverse order
    op.drop_table('legacy_edge_reviews')
    op.drop_table('extraction_run_activation_history')
    op.drop_table('edge_evidence')
    op.drop_table('graph_edges')
    op.drop_table('proposition_concept_links')
    op.drop_table('proposition_highlights')
    op.drop_table('concepts')
    op.drop_table('propositions')
    op.drop_table('extraction_runs')

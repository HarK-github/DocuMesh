"""migrate_to_pgvector

Revision ID: c1f2e3d4a5b6
Revises: b4b96b316075
Create Date: 2026-11-09

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
import numpy as np

EMBEDDING_DIM = 384

# revision identifiers, used by Alembic.
revision: str = 'c1f2e3d4a5b6'
down_revision: Union[str, Sequence[str], None] = 'b4b96b316075'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # a. Create vector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")

    conn = op.get_bind()

    # b. Convert existing blob data via np.frombuffer into new Vector(384) column
    for table_name in ['sentences', 'chunks', 'nodes']:
        check_table = conn.execute(sa.text(
            f"SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = '{table_name}');"
        )).scalar()
        if not check_table:
            continue

        col_type = conn.execute(sa.text(
            f"SELECT data_type FROM information_schema.columns WHERE table_name = '{table_name}' AND column_name = 'embedding';"
        )).scalar()

        if col_type == 'bytea':
            # Add temporary vector column
            op.add_column(table_name, sa.Column('embedding_vec', Vector(EMBEDDING_DIM), nullable=True))

            # Convert existing blob data via np.frombuffer into the new column
            rows = conn.execute(sa.text(f"SELECT id, embedding FROM {table_name} WHERE embedding IS NOT NULL")).fetchall()
            for row_id, blob in rows:
                if blob:
                    try:
                        arr = np.frombuffer(blob, dtype=np.float32).tolist()
                        conn.execute(
                            sa.text(f"UPDATE {table_name} SET embedding_vec = :vec WHERE id = :id"),
                            {"vec": str(arr), "id": row_id}
                        )
                    except Exception:
                        pass

            # Drop old blob column and rename vector column
            op.drop_column(table_name, 'embedding')
            op.alter_column(table_name, 'embedding_vec', new_column_name='embedding')
        elif col_type is None:
            op.add_column(table_name, sa.Column('embedding', Vector(EMBEDDING_DIM), nullable=True))

    # c. Create HNSW index with cosine ops after data load
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_sentences_embedding_hnsw ON sentences "
        "USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);"
    )


def downgrade() -> None:
    conn = op.get_bind()
    op.execute("DROP INDEX IF EXISTS ix_sentences_embedding_hnsw;")

    for table_name in ['sentences', 'chunks', 'nodes']:
        check_table = conn.execute(sa.text(
            f"SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = '{table_name}');"
        )).scalar()
        if not check_table:
            continue

        col_type = conn.execute(sa.text(
            f"SELECT udt_name FROM information_schema.columns WHERE table_name = '{table_name}' AND column_name = 'embedding';"
        )).scalar()

        if col_type == 'vector':
            op.add_column(table_name, sa.Column('embedding_blob', sa.LargeBinary(), nullable=True))
            rows = conn.execute(sa.text(f"SELECT id, embedding FROM {table_name} WHERE embedding IS NOT NULL")).fetchall()
            for row_id, vec in rows:
                if vec is not None:
                    try:
                        if isinstance(vec, str):
                            vec_floats = [float(x) for x in vec.strip('[]').split(',')]
                        else:
                            vec_floats = list(vec)
                        blob = np.asarray(vec_floats, dtype=np.float32).tobytes()
                        conn.execute(
                            sa.text(f"UPDATE {table_name} SET embedding_blob = :blob WHERE id = :id"),
                            {"blob": blob, "id": row_id}
                        )
                    except Exception:
                        pass
            op.drop_column(table_name, 'embedding')
            op.alter_column(table_name, 'embedding_blob', new_column_name='embedding')

    op.execute("DROP EXTENSION IF EXISTS vector CASCADE;")

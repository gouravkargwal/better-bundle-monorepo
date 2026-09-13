"""upgrade_vectors

Revision ID: 47239f0cc303
Revises: 2e4b4f530eae
Create Date: 2026-09-12 23:09:31.124457
"""

from typing import Sequence, Union

from alembic import op
import pgvector.sqlalchemy


revision: str = '47239f0cc303'
down_revision: Union[str, None] = '2e4b4f530eae'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index('idx_product_vectors_vector', table_name='product_vectors')
    # Clear out 384-d vectors since pgvector cannot cast vector(384) to vector(1408);
    # active products will be re-embedded with the multimodal model on next sync.
    op.execute("TRUNCATE TABLE product_vectors")
    op.alter_column('product_vectors', 'vector',
               existing_type=pgvector.sqlalchemy.vector.VECTOR(dim=384),
               type_=pgvector.sqlalchemy.vector.VECTOR(dim=1408),
               existing_nullable=False)
    op.create_index(
        'idx_product_vectors_vector',
        'product_vectors',
        ['vector'],
        unique=False,
        postgresql_using='hnsw',
        postgresql_with={'m': 16, 'ef_construction': 64},
        postgresql_ops={'vector': 'vector_cosine_ops'},
    )


def downgrade() -> None:
    op.drop_index('idx_product_vectors_vector', table_name='product_vectors')
    op.alter_column('product_vectors', 'vector',
               existing_type=pgvector.sqlalchemy.vector.VECTOR(dim=1408),
               type_=pgvector.sqlalchemy.vector.VECTOR(dim=384),
               existing_nullable=False)
    op.create_index(
        'idx_product_vectors_vector',
        'product_vectors',
        ['vector'],
        unique=False,
        postgresql_using='ivfflat',
        postgresql_with={'lists': 100},
        postgresql_ops={'vector': 'vector_cosine_ops'},
    )

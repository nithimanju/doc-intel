"""embedding vector dimension 640 harrier

Revision ID: f350a97cbc93
Revises: 6a644c60b409
Create Date: 2026-10-29

Embedder choice moved to harrier-oss-v1-270m (640-dim) — see decisions.md
[2026-10-29] "Embedder Selection for RAG". Changes document_chunk.embedding_vector
from vector(768) to vector(640). Only valid while the column holds no vectors
(Postgres rejects the cast otherwise) — nothing has been embedded yet.
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'f350a97cbc93'
down_revision: Union[str, Sequence[str], None] = '6a644c60b409'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("ALTER TABLE document_chunk ALTER COLUMN embedding_vector TYPE vector(640)")


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("ALTER TABLE document_chunk ALTER COLUMN embedding_vector TYPE vector(768)")

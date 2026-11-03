"""document_chunk.content_hash

Revision ID: e2c5a7d4b861
Revises: d8a2f6b13e90
Create Date: 2026-11-04

SHA-256 (hex) of each chunk's content, computed in Python at ingest. Existing
rows are backfilled in SQL with the same function over the UTF-8 bytes, so old
and new rows hash identically.
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'e2c5a7d4b861'
down_revision: Union[str, Sequence[str], None] = 'd8a2f6b13e90'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("ALTER TABLE document_chunk ADD COLUMN content_hash VARCHAR(64)")
    op.execute(
        "UPDATE document_chunk "
        "SET content_hash = encode(sha256(convert_to(content, 'UTF8')), 'hex')"
    )
    op.execute("ALTER TABLE document_chunk ALTER COLUMN content_hash SET NOT NULL")


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("ALTER TABLE document_chunk DROP COLUMN content_hash")

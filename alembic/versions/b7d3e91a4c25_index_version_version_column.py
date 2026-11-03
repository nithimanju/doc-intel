"""index_version.version column

Revision ID: b7d3e91a4c25
Revises: f350a97cbc93
Create Date: 2026-11-04

index_version had no natural key, so "does this index version already exist"
could not be answered. Adds a UNIQUE version label. Existing rows are
backfilled with 'legacy-<id>' so the NOT NULL + UNIQUE constraints can apply.
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'b7d3e91a4c25'
down_revision: Union[str, Sequence[str], None] = 'f350a97cbc93'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("ALTER TABLE index_version ADD COLUMN version VARCHAR(50)")
    op.execute(
        "UPDATE index_version SET version = 'legacy-' || index_version_id "
        "WHERE version IS NULL"
    )
    op.execute("ALTER TABLE index_version ALTER COLUMN version SET NOT NULL")
    op.execute(
        "ALTER TABLE index_version "
        "ADD CONSTRAINT uq_index_version_version UNIQUE (version)"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("ALTER TABLE index_version DROP CONSTRAINT uq_index_version_version")
    op.execute("ALTER TABLE index_version DROP COLUMN version")

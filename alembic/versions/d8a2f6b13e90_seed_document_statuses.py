"""seed document statuses

Revision ID: d8a2f6b13e90
Revises: b7d3e91a4c25
Create Date: 2026-11-04

Seeds SUCCESS, PARTIAL_SUCCESS and FAILURE (see decisions.md [2026-10-29]:
per-document status).
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'd8a2f6b13e90'
down_revision: Union[str, Sequence[str], None] = 'b7d3e91a4c25'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("""
        INSERT INTO status (status_name, status_description, created_date, created_by)
        VALUES
            ('SUCCESS', 'Document parsed and every chunk embedded', now(), 'system'),
            ('PARTIAL_SUCCESS', 'Document stored but some chunks were not embedded', now(), 'system'),
            ('FAILURE', 'Document could not be processed', now(), 'system')
        ON CONFLICT (status_name) DO NOTHING
    """)


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("""
        DELETE FROM status
        WHERE status_name IN ('SUCCESS', 'PARTIAL_SUCCESS', 'FAILURE')
          AND status_id NOT IN (SELECT status_id FROM document)
          AND status_id NOT IN (SELECT status_id FROM index_run)
          AND status_id NOT IN (SELECT status_id FROM eval_run)
    """)

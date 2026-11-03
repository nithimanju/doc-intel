"""seed index_run statuses

Revision ID: f6b1c3d8e745
Revises: e2c5a7d4b861
Create Date: 2026-11-04

Seeds RUNNING and COMPLETED, the index_run statuses, in uppercase like the
document statuses (see decisions.md [2026-11-04]).
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'f6b1c3d8e745'
down_revision: Union[str, Sequence[str], None] = 'e2c5a7d4b861'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("""
        INSERT INTO status (status_name, status_description, created_date, created_by)
        VALUES
            ('RUNNING', 'Index run started and not finished', now(), 'system'),
            ('COMPLETED', 'Index run finished', now(), 'system')
        ON CONFLICT (status_name) DO NOTHING
    """)


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("""
        DELETE FROM status
        WHERE status_name IN ('RUNNING', 'COMPLETED')
          AND status_id NOT IN (SELECT status_id FROM index_run)
          AND status_id NOT IN (SELECT status_id FROM document)
          AND status_id NOT IN (SELECT status_id FROM eval_run)
    """)

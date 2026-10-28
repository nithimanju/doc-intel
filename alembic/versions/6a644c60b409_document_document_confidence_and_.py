"""document document confidence and document chunk tables

Revision ID: 6a644c60b409
Revises: cdf6018503ab
Create Date: 2026-10-29 01:43:50.895092

Written as raw SQL (op.execute), not op.create_table — same schema as
before, transcribed from the already-applied live DB so there's no drift
from what's actually running. See decisions.md [2026-10-29]:
- DOCUMENT keys to INDEX_RUN (the execution that parsed it), not
  INDEX_VERSION directly — resumability is scoped to "has this doc already
  succeeded within the current run" (UNIQUE(index_run_id, source_hash)).
- DOCUMENT keeps its own STATUS_ID. One INDEX_RUN parses many documents, so
  INDEX_RUN.STATUS_ID (a run-level rollup) can't represent "23 of 25 docs
  succeeded, 2 failed" — per-document status has to live on DOCUMENT itself.
  ERRORS stays alongside it for the actual error detail.
- DOCUMENT_CONFIDENCE.page_no is NOT NULL with 0 = document-level, never
  nullable — Postgres treats NULL <> NULL for uniqueness, so a nullable
  page_no would let duplicate document-level rows slip past the unique
  constraint.
- DOCUMENT_CHUNK.chunk_region is a single JSONB column holding the *list* of
  a chunk's regions (a chunk can span many pages/doc_items); nothing queries
  into it from SQL, so no child per-region table.
- embedding_vector is hardcoded to vector(768) — a migration's DDL must stay
  fixed once written; 768 is EmbeddingGemma-300M's documented output size,
  not yet a measured choice (see decisions.md [2026-10-29]).
"""
from typing import Sequence, Union

from alembic import op


EMBEDDING_VECTOR_DIM = 768

# revision identifiers, used by Alembic.
revision: str = '6a644c60b409'
down_revision: Union[str, Sequence[str], None] = 'cdf6018503ab'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    op.execute("""
        CREATE TABLE document (
            document_id SERIAL PRIMARY KEY,
            index_run_id INTEGER NOT NULL REFERENCES index_run(index_run_id) ON DELETE RESTRICT,
            document_name VARCHAR(500) NOT NULL,
            document_source TEXT NOT NULL,
            status_id INTEGER NOT NULL REFERENCES status(status_id) ON DELETE RESTRICT,
            source_hash VARCHAR(64) NOT NULL,
            start_time TIMESTAMPTZ,
            end_time TIMESTAMPTZ,
            errors JSONB NOT NULL DEFAULT '[]'::jsonb,
            created_date TIMESTAMPTZ NOT NULL,
            created_by VARCHAR(255) NOT NULL,
            active BOOLEAN NOT NULL DEFAULT TRUE,
            modified_date TIMESTAMPTZ,
            modified_by VARCHAR(255),
            CONSTRAINT uq_document_run_hash UNIQUE (index_run_id, source_hash)
        )
    """)
    op.execute("CREATE INDEX ix_document_index_run_id ON document (index_run_id)")
    op.execute("CREATE INDEX ix_document_status_id ON document (status_id)")

    op.execute("""
        CREATE TABLE document_confidence (
            document_confidence_id SERIAL PRIMARY KEY,
            document_id INTEGER NOT NULL REFERENCES document(document_id) ON DELETE CASCADE,
            page_no INTEGER NOT NULL DEFAULT 0,
            name VARCHAR(100) NOT NULL,
            value TEXT NOT NULL,
            created_date TIMESTAMPTZ NOT NULL,
            created_by VARCHAR(255) NOT NULL,
            active BOOLEAN NOT NULL DEFAULT TRUE,
            modified_date TIMESTAMPTZ,
            modified_by VARCHAR(255),
            CONSTRAINT uq_document_confidence_doc_page_name UNIQUE (document_id, page_no, name)
        )
    """)
    op.execute(
        "CREATE INDEX ix_document_confidence_document_id "
        "ON document_confidence (document_id)"
    )

    op.execute(f"""
        CREATE TABLE document_chunk (
            chunk_id BIGSERIAL PRIMARY KEY,
            document_id INTEGER NOT NULL REFERENCES document(document_id) ON DELETE CASCADE,
            chunk_label VARCHAR(100),
            chunk_heading_path JSONB,
            chunk_region JSONB,
            reading_order INTEGER NOT NULL,
            content TEXT NOT NULL,
            embedding_vector VECTOR({EMBEDDING_VECTOR_DIM}),
            created_date TIMESTAMPTZ NOT NULL,
            created_by VARCHAR(255) NOT NULL,
            active BOOLEAN NOT NULL DEFAULT TRUE,
            modified_date TIMESTAMPTZ,
            modified_by VARCHAR(255),
            CONSTRAINT uq_document_chunk_doc_reading_order UNIQUE (document_id, reading_order)
        )
    """)
    op.execute(
        "CREATE INDEX ix_document_chunk_document_id ON document_chunk (document_id)"
    )
    # No HNSW index yet — issue 0.4/0.10: insert all vectors first, then
    # CREATE INDEX once the corpus is bulk-loaded and the dimension is final.


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP TABLE document_chunk")
    op.execute("DROP TABLE document_confidence")
    op.execute("DROP TABLE document")

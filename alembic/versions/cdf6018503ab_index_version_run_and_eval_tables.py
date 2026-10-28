"""index version run and eval tables

Revision ID: cdf6018503ab
Revises: a81c97fe7f23
Create Date: 2026-10-29 01:43:37.222253

Written as raw SQL (op.execute), not op.create_table — same schema as
before, transcribed from the already-applied live DB so there's no drift
from what's actually running. See decisions.md [2026-10-28]/[2026-10-29]:
- INDEX_VERSION is config identity (one chunker/parser/embedder, NOT NULL —
  the DB-level guarantee behind "never mix embeddings from different models
  in one index"). INDEX_RUN is one concrete execution of that config.
- The three INDEX_*_CONFIG tables key on (INDEX_VERSION_ID, CONFIG_NAME)
  only — no redundant copy of CHUNKER_ID/EMBEDDER_ID/PARSER_ID.
- EVAL_TYPE -> EVAL_RECORD -> EVAL_RUN is a three-level metric hierarchy.
  EVAL_RUN is scoped to one INDEX_RUN, enforced by a unique constraint.
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'cdf6018503ab'
down_revision: Union[str, Sequence[str], None] = 'a81c97fe7f23'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    # --- catalogs ---------------------------------------------------------
    op.execute("""
        CREATE TABLE status (
            status_id SERIAL PRIMARY KEY,
            status_name VARCHAR(100) NOT NULL,
            status_description TEXT,
            created_date TIMESTAMPTZ NOT NULL,
            created_by VARCHAR(255) NOT NULL,
            active BOOLEAN NOT NULL DEFAULT TRUE,
            modified_date TIMESTAMPTZ,
            modified_by VARCHAR(255),
            CONSTRAINT uq_status_name UNIQUE (status_name)
        )
    """)
    op.execute("CREATE INDEX ix_status_active ON status (active) WHERE active")

    op.execute("""
        CREATE TABLE chunker (
            chunker_id SERIAL PRIMARY KEY,
            chunker_name VARCHAR(255) NOT NULL,
            chunker_description TEXT,
            version VARCHAR(50) NOT NULL,
            created_date TIMESTAMPTZ NOT NULL,
            created_by VARCHAR(255) NOT NULL,
            active BOOLEAN NOT NULL DEFAULT TRUE,
            modified_date TIMESTAMPTZ,
            modified_by VARCHAR(255),
            CONSTRAINT uq_chunker_name_version UNIQUE (chunker_name, version)
        )
    """)
    op.execute("CREATE INDEX ix_chunker_active ON chunker (active) WHERE active")

    op.execute("""
        CREATE TABLE parser (
            parser_id SERIAL PRIMARY KEY,
            parser_name VARCHAR(255) NOT NULL,
            parser_description TEXT,
            version VARCHAR(50) NOT NULL,
            created_date TIMESTAMPTZ NOT NULL,
            created_by VARCHAR(255) NOT NULL,
            active BOOLEAN NOT NULL DEFAULT TRUE,
            modified_date TIMESTAMPTZ,
            modified_by VARCHAR(255),
            CONSTRAINT uq_parser_name_version UNIQUE (parser_name, version)
        )
    """)
    op.execute("CREATE INDEX ix_parser_active ON parser (active) WHERE active")

    op.execute("""
        CREATE TABLE embedder (
            embedder_id SERIAL PRIMARY KEY,
            embedder_name VARCHAR(255) NOT NULL,
            embedder_description TEXT,
            version VARCHAR(50) NOT NULL,
            created_date TIMESTAMPTZ NOT NULL,
            created_by VARCHAR(255) NOT NULL,
            active BOOLEAN NOT NULL DEFAULT TRUE,
            modified_date TIMESTAMPTZ,
            modified_by VARCHAR(255),
            CONSTRAINT uq_embedder_name_version UNIQUE (embedder_name, version)
        )
    """)
    op.execute("CREATE INDEX ix_embedder_active ON embedder (active) WHERE active")

    op.execute("""
        CREATE TABLE eval_type (
            eval_type_id SERIAL PRIMARY KEY,
            eval_name VARCHAR(100) NOT NULL,
            eval_description TEXT,
            created_date TIMESTAMPTZ NOT NULL,
            created_by VARCHAR(255) NOT NULL,
            active BOOLEAN NOT NULL DEFAULT TRUE,
            modified_date TIMESTAMPTZ,
            modified_by VARCHAR(255),
            CONSTRAINT uq_eval_type_name UNIQUE (eval_name)
        )
    """)

    op.execute("""
        CREATE TABLE eval_record (
            eval_record_id SERIAL PRIMARY KEY,
            eval_type_id INTEGER NOT NULL REFERENCES eval_type(eval_type_id) ON DELETE RESTRICT,
            metric_name VARCHAR(100) NOT NULL,
            eval_description TEXT,
            created_date TIMESTAMPTZ NOT NULL,
            created_by VARCHAR(255) NOT NULL,
            active BOOLEAN NOT NULL DEFAULT TRUE,
            modified_date TIMESTAMPTZ,
            modified_by VARCHAR(255),
            CONSTRAINT uq_eval_record_metric_name UNIQUE (metric_name)
        )
    """)
    op.execute(
        "CREATE INDEX ix_eval_record_eval_type_id ON eval_record (eval_type_id)"
    )

    op.execute("""
        CREATE TABLE question_type (
            question_type_id SERIAL PRIMARY KEY,
            question_type VARCHAR(50) NOT NULL,
            question_type_description TEXT,
            created_date TIMESTAMPTZ NOT NULL,
            created_by VARCHAR(255) NOT NULL,
            active BOOLEAN NOT NULL DEFAULT TRUE,
            modified_date TIMESTAMPTZ,
            modified_by VARCHAR(255),
            CONSTRAINT uq_question_type_name UNIQUE (question_type)
        )
    """)

    # --- index version / run ----------------------------------------------
    op.execute("""
        CREATE TABLE index_version (
            index_version_id SERIAL PRIMARY KEY,
            description TEXT,
            chunker_id INTEGER NOT NULL REFERENCES chunker(chunker_id) ON DELETE RESTRICT,
            embedder_id INTEGER NOT NULL REFERENCES embedder(embedder_id) ON DELETE RESTRICT,
            parser_id INTEGER NOT NULL REFERENCES parser(parser_id) ON DELETE RESTRICT,
            config JSONB,
            created_date TIMESTAMPTZ NOT NULL,
            created_by VARCHAR(255) NOT NULL
        )
    """)
    op.execute(
        "CREATE INDEX ix_index_version_chunker_id ON index_version (chunker_id)"
    )
    op.execute(
        "CREATE INDEX ix_index_version_embedder_id ON index_version (embedder_id)"
    )
    op.execute(
        "CREATE INDEX ix_index_version_parser_id ON index_version (parser_id)"
    )

    op.execute("""
        CREATE TABLE index_run (
            index_run_id SERIAL PRIMARY KEY,
            index_version_id INTEGER NOT NULL REFERENCES index_version(index_version_id) ON DELETE RESTRICT,
            doc_count INTEGER,
            chunk_count INTEGER,
            time_elapsed DOUBLE PRECISION,
            status_id INTEGER NOT NULL REFERENCES status(status_id) ON DELETE RESTRICT,
            created_date TIMESTAMPTZ NOT NULL,
            created_by VARCHAR(255) NOT NULL
        )
    """)
    op.execute(
        "CREATE INDEX ix_index_run_index_version_id ON index_run (index_version_id)"
    )
    op.execute("CREATE INDEX ix_index_run_status_id ON index_run (status_id)")

    # --- per-stage config (EAV, keyed on index_version alone) -------------
    for name in ("index_parser_config", "index_chunker_config", "index_embedder_config"):
        op.execute(f"""
            CREATE TABLE {name} (
                {name}_id SERIAL PRIMARY KEY,
                index_version_id INTEGER NOT NULL REFERENCES index_version(index_version_id) ON DELETE CASCADE,
                config_name VARCHAR(255) NOT NULL,
                config_value TEXT NOT NULL,
                description TEXT,
                details TEXT,
                created_date TIMESTAMPTZ NOT NULL,
                created_by VARCHAR(255) NOT NULL,
                active BOOLEAN NOT NULL DEFAULT TRUE,
                modified_date TIMESTAMPTZ,
                modified_by VARCHAR(255),
                CONSTRAINT uq_{name}_version_name UNIQUE (index_version_id, config_name)
            )
        """)
        op.execute(
            f"CREATE INDEX ix_{name}_index_version_id ON {name} (index_version_id)"
        )

    # --- eval ---------------------------------------------------------------
    op.execute("""
        CREATE TABLE eval_run (
            eval_run_id SERIAL PRIMARY KEY,
            index_run_id INTEGER NOT NULL REFERENCES index_run(index_run_id) ON DELETE RESTRICT,
            eval_record_id INTEGER NOT NULL REFERENCES eval_record(eval_record_id) ON DELETE RESTRICT,
            metric_value DOUBLE PRECISION NOT NULL,
            question_type_id INTEGER NOT NULL REFERENCES question_type(question_type_id) ON DELETE RESTRICT,
            status_id INTEGER NOT NULL REFERENCES status(status_id) ON DELETE RESTRICT,
            created_date TIMESTAMPTZ NOT NULL,
            created_by VARCHAR(255) NOT NULL,
            CONSTRAINT uq_eval_run_index_run_record_question_type
                UNIQUE (index_run_id, eval_record_id, question_type_id)
        )
    """)
    op.execute("CREATE INDEX ix_eval_run_index_run_id ON eval_run (index_run_id)")
    op.execute("CREATE INDEX ix_eval_run_eval_record_id ON eval_run (eval_record_id)")
    op.execute(
        "CREATE INDEX ix_eval_run_question_type_id ON eval_run (question_type_id)"
    )
    op.execute("CREATE INDEX ix_eval_run_status_id ON eval_run (status_id)")


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP TABLE eval_run")
    for name in ("index_embedder_config", "index_chunker_config", "index_parser_config"):
        op.execute(f"DROP TABLE {name}")
    op.execute("DROP TABLE index_run")
    op.execute("DROP TABLE index_version")
    op.execute("DROP TABLE question_type")
    op.execute("DROP TABLE eval_record")
    op.execute("DROP TABLE eval_type")
    op.execute("DROP TABLE embedder")
    op.execute("DROP TABLE parser")
    op.execute("DROP TABLE chunker")
    op.execute("DROP TABLE status")

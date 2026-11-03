"""Persistence for index catalog (chunker/parser/embedder) and index_version."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

import psycopg
from psycopg.types.json import Jsonb

from src.config.postgres import connect
from src.persistance.catalog_repo import ensure_status
from src.vo.catalog_vo import Status
from src.vo.index_vo import Chunker, Embedder, IndexConfig, IndexRun, IndexVersion, Parser


@dataclass(frozen=True)
class _CatalogSpec:
    table: str
    id_col: str
    name_col: str
    desc_col: str
    config_table: str


_CHUNKER = _CatalogSpec(
    "chunker", "chunker_id", "chunker_name", "chunker_description", "index_chunker_config"
)
_PARSER = _CatalogSpec(
    "parser", "parser_id", "parser_name", "parser_description", "index_parser_config"
)
_EMBEDDER = _CatalogSpec(
    "embedder", "embedder_id", "embedder_name", "embedder_description", "index_embedder_config"
)

_Catalog = Chunker | Parser | Embedder


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _catalog_is_present(
    conn: psycopg.Connection, spec: _CatalogSpec, vo: _Catalog
) -> int | None:
    with conn.cursor() as cur:
        cur.execute(
            f"SELECT {spec.id_col} FROM {spec.table} "
            f"WHERE {spec.name_col} = %s AND version = %s",
            (vo.name, vo.version),
        )
        row = cur.fetchone()
    return row[0] if row else None


def _catalog_insert(conn: psycopg.Connection, spec: _CatalogSpec, vo: _Catalog) -> int:
    with conn.cursor() as cur:
        cur.execute(
            f"INSERT INTO {spec.table} "
            f"({spec.name_col}, {spec.desc_col}, version, created_date, created_by) "
            f"VALUES (%s, %s, %s, %s, %s) RETURNING {spec.id_col}",
            (vo.name, vo.description, vo.version, _now(), vo.created_by),
        )
        return cur.fetchone()[0]


def _set_id(vo: _Catalog, spec: _CatalogSpec, value: int) -> None:
    setattr(vo, spec.id_col, value)


def _catalog_ensure(conn: psycopg.Connection, spec: _CatalogSpec, vo: _Catalog) -> None:
    """Fill vo's id, inserting the row first if name+version is not present. No commit."""
    existing = _catalog_is_present(conn, spec, vo)
    _set_id(vo, spec, existing if existing is not None else _catalog_insert(conn, spec, vo))


def _catalog_insert_if_not_exist(
    conn: psycopg.Connection, spec: _CatalogSpec, vo: _Catalog
) -> _Catalog:
    try:
        _catalog_ensure(conn, spec, vo)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return vo


def is_chunker_present(conn: psycopg.Connection, chunker: Chunker) -> int | None:
    return _catalog_is_present(conn, _CHUNKER, chunker)


def insert_chunker(conn: psycopg.Connection, chunker: Chunker) -> int:
    return _catalog_insert(conn, _CHUNKER, chunker)


def insert_chunker_if_not_exist(conn: psycopg.Connection, chunker: Chunker) -> Chunker:
    return _catalog_insert_if_not_exist(conn, _CHUNKER, chunker)


def is_parser_present(conn: psycopg.Connection, parser: Parser) -> int | None:
    return _catalog_is_present(conn, _PARSER, parser)


def insert_parser(conn: psycopg.Connection, parser: Parser) -> int:
    return _catalog_insert(conn, _PARSER, parser)


def insert_parser_if_not_exist(conn: psycopg.Connection, parser: Parser) -> Parser:
    return _catalog_insert_if_not_exist(conn, _PARSER, parser)


def is_embedder_present(conn: psycopg.Connection, embedder: Embedder) -> int | None:
    return _catalog_is_present(conn, _EMBEDDER, embedder)


def insert_embedder(conn: psycopg.Connection, embedder: Embedder) -> int:
    return _catalog_insert(conn, _EMBEDDER, embedder)


def insert_embedder_if_not_exist(conn: psycopg.Connection, embedder: Embedder) -> Embedder:
    return _catalog_insert_if_not_exist(conn, _EMBEDDER, embedder)


def is_index_version_present(conn: psycopg.Connection, index_version: IndexVersion) -> int | None:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT index_version_id FROM index_version WHERE version = %s",
            (index_version.version,),
        )
        row = cur.fetchone()
    return row[0] if row else None


def _insert_configs(
    conn: psycopg.Connection,
    spec: _CatalogSpec,
    index_version_id: int,
    configs: list[IndexConfig],
    created_by: str,
) -> None:
    if not configs:
        return
    now = _now()
    rows = [
        (index_version_id, c.name, c.value, c.description, c.details, now, created_by)
        for c in configs
    ]
    with conn.cursor() as cur:
        cur.executemany(
            f"INSERT INTO {spec.config_table} "
            "(index_version_id, config_name, config_value, description, details, "
            "created_date, created_by) VALUES (%s, %s, %s, %s, %s, %s, %s)",
            rows,
        )


def insert_index_version(conn: psycopg.Connection, index_version: IndexVersion) -> int:
    """Insert the index_version row plus the configs of its chunker/parser/embedder. No commit."""
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO index_version "
            "(version, description, chunker_id, embedder_id, parser_id, config, "
            "created_date, created_by) VALUES (%s, %s, %s, %s, %s, %s, %s, %s) "
            "RETURNING index_version_id",
            (
                index_version.version,
                index_version.description,
                index_version.chunker.chunker_id,
                index_version.embedder.embedder_id,
                index_version.parser.parser_id,
                Jsonb(index_version.config) if index_version.config is not None else None,
                _now(),
                index_version.created_by,
            ),
        )
        new_id = cur.fetchone()[0]

    for spec, component in (
        (_CHUNKER, index_version.chunker),
        (_PARSER, index_version.parser),
        (_EMBEDDER, index_version.embedder),
    ):
        _insert_configs(conn, spec, new_id, component.configs, index_version.created_by)
    return new_id


def insert_index_version_if_not_exist(
    index_version: IndexVersion, conn: psycopg.Connection | None = None
) -> IndexVersion:
    """Ensure chunker/parser/embedder exist, then the version, in one transaction.

    Opens (and closes) its own connection unless one is passed in.
    """
    if conn is None:
        with connect() as own_conn:
            return insert_index_version_if_not_exist(index_version, own_conn)

    try:
        _catalog_ensure(conn, _CHUNKER, index_version.chunker)
        _catalog_ensure(conn, _PARSER, index_version.parser)
        _catalog_ensure(conn, _EMBEDDER, index_version.embedder)

        existing = is_index_version_present(conn, index_version)
        index_version.index_version_id = (
            existing if existing is not None else insert_index_version(conn, index_version)
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return index_version


def insert_index_run(
    index_run: IndexRun, conn: psycopg.Connection | None = None
) -> IndexRun:
    """Always creates a new run for its (already persisted) index version."""
    if conn is None:
        with connect() as own_conn:
            return insert_index_run(index_run, own_conn)

    try:
        ensure_status(conn, index_run.status)
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO index_run (index_version_id, doc_count, chunk_count, "
                "time_elapsed, status_id, created_date, created_by) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING index_run_id",
                (
                    index_run.index_version.index_version_id,
                    index_run.doc_count,
                    index_run.chunk_count,
                    index_run.time_elapsed,
                    index_run.status.status_id,
                    _now(),
                    index_run.created_by,
                ),
            )
            index_run.index_run_id = cur.fetchone()[0]
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return index_run


def finish_index_run(
    index_run: IndexRun,
    status: Status,
    time_elapsed: float,
    conn: psycopg.Connection | None = None,
) -> IndexRun:
    if conn is None:
        with connect() as own_conn:
            return finish_index_run(index_run, status, time_elapsed, own_conn)

    try:
        ensure_status(conn, status)
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE index_run SET status_id = %s, time_elapsed = %s "
                "WHERE index_run_id = %s",
                (status.status_id, time_elapsed, index_run.index_run_id),
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    index_run.status = status
    index_run.time_elapsed = time_elapsed
    return index_run

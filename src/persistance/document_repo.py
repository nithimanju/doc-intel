"""Persistence for document, document_confidence and document_chunk."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any, Iterator

import psycopg
from psycopg.types.json import Jsonb

from src.config.postgres import connect
from src.config.settings import DB_BATCH_SIZE
from src.injest.docling.models import DocumentRecord
from src.persistance.catalog_repo import ensure_status
from src.vo.catalog_vo import STATUS_PARTIAL_SUCCESS, STATUS_FAILURE, STATUS_SUCCESS, Status
from src.vo.document_vo import Document, DocumentChunk, DocumentConfidence


def _document_status_name(raw: str) -> str:
    """Docling/app status string -> one of the three seeded status names."""
    name = raw.upper()
    return name if name in (STATUS_SUCCESS, STATUS_PARTIAL_SUCCESS) else STATUS_FAILURE


def _confidence_value(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, (dict, list)):
        return json.dumps(value)
    return str(value)


def format_to_document_confidence_entities(
    record: DocumentRecord, created_by: str = "system"
) -> list[DocumentConfidence]:
    """Overall scores get page_no 0; scores under 'pages' get their page number."""
    confidence = record.confidence or {}
    rows: list[DocumentConfidence] = []

    def add(page_no: int, name: str, value: Any) -> None:
        if value is not None:
            rows.append(
                DocumentConfidence(
                    name=name,
                    value=_confidence_value(value),
                    created_by=created_by,
                    page_no=page_no,
                )
            )

    for name, value in confidence.items():
        if name == "pages" and isinstance(value, dict):
            for page, scores in value.items():
                if isinstance(scores, dict):
                    for score_name, score in scores.items():
                        add(int(page), score_name, score)
        else:
            add(0, name, value)
    return rows


def format_to_document_chunk_entities(
    record: DocumentRecord, created_by: str = "system"
) -> list[DocumentChunk]:
    return [
        DocumentChunk(
            content=chunk.content,
            reading_order=order,
            created_by=created_by,
            content_hash=hashlib.sha256(chunk.content.encode("utf-8")).hexdigest(),
            label=chunk.chunk_type,
            heading_path=list(chunk.heading_level) or None,
            region=[asdict(r) for r in chunk.regions] or None,
            embedding_vector=chunk.embedding_vector,
        )
        for order, chunk in enumerate(record.chunks)
    ]


def format_to_document_entities(
    record: DocumentRecord,
    document_source: str | None = None,
    created_by: str = "system",
) -> list[Document]:
    if record.index_run is None:
        raise ValueError(f"DocumentRecord {record.doc_id} has no index_run attached")
    return [
        Document(
            document_name=record.document_name,
            document_source=document_source or record.document_name,
            source_hash=record.source_hash,
            status=Status(name=_document_status_name(record.status), created_by=created_by),
            index_run=record.index_run,
            created_by=created_by,
            start_time=record.start_date,
            end_time=record.end_time,
            errors=list(record.errors),
            confidences=format_to_document_confidence_entities(record, created_by),
            chunks=format_to_document_chunk_entities(record, created_by),
        )
    ]


def _vector_literal(vector: list[float] | None) -> str | None:
    return None if vector is None else "[" + ",".join(repr(float(x)) for x in vector) + "]"


def _insert_document_row(conn: psycopg.Connection, document: Document) -> int:
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO document (index_run_id, document_name, document_source, "
            "status_id, source_hash, start_time, end_time, errors, created_date, created_by) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING document_id",
            (
                document.index_run.index_run_id,
                document.document_name,
                document.document_source,
                document.status.status_id,
                document.source_hash,
                document.start_time,
                document.end_time,
                Jsonb(document.errors),
                datetime.now(timezone.utc),
                document.created_by,
            ),
        )
        return cur.fetchone()[0]


def _batches(items: list, size: int) -> Iterator[list]:
    for start in range(0, len(items), size):
        yield items[start : start + size]


def _insert_confidences(conn: psycopg.Connection, document: Document) -> None:
    now = datetime.now(timezone.utc)
    with conn.cursor() as cur:
        for batch in _batches(document.confidences, DB_BATCH_SIZE):
            cur.executemany(
                "INSERT INTO document_confidence "
                "(document_id, page_no, name, value, created_date, created_by) "
                "VALUES (%s, %s, %s, %s, %s, %s)",
                [
                    (document.document_id, c.page_no, c.name, c.value, now, c.created_by)
                    for c in batch
                ],
            )


def _insert_chunks(conn: psycopg.Connection, document: Document) -> None:
    now = datetime.now(timezone.utc)
    with conn.cursor() as cur:
        for batch in _batches(document.chunks, DB_BATCH_SIZE):
            cur.executemany(
                "INSERT INTO document_chunk (document_id, chunk_label, chunk_heading_path, "
                "chunk_region, reading_order, content, content_hash, embedding_vector, "
                "created_date, created_by) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s::vector, %s, %s) "
                "RETURNING chunk_id",
                [
                    (
                        document.document_id,
                        c.label,
                        Jsonb(c.heading_path) if c.heading_path is not None else None,
                        Jsonb(c.region) if c.region is not None else None,
                        c.reading_order,
                        c.content,
                        c.content_hash,
                        _vector_literal(c.embedding_vector),
                        now,
                        c.created_by,
                    )
                    for c in batch
                ],
                returning=True,
            )
            for chunk in batch:
                chunk.chunk_id = cur.fetchone()[0]
                cur.nextset()


def insert_document(
    record: DocumentRecord,
    document_source: str | None = None,
    conn: psycopg.Connection | None = None,
    created_by: str = "system",
) -> Document:
    """Insert document, then its confidences, then its chunks, in one transaction.

    No duplicate check: a second insert of the same (index_run, source_hash)
    fails on the UNIQUE constraint. Opens its own connection unless one is passed in.
    """
    if conn is None:
        with connect() as own_conn:
            return insert_document(record, document_source, own_conn, created_by)

    document = format_to_document_entities(record, document_source, created_by)[0]
    try:
        ensure_status(conn, document.status)
        document.document_id = _insert_document_row(conn, document)
        _insert_confidences(conn, document)
        _insert_chunks(conn, document)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return document

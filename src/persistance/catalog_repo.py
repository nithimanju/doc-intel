"""Persistence for shared catalog tables (status)."""

from __future__ import annotations

from datetime import datetime, timezone

import psycopg

from src.config.postgres import connect
from src.vo.catalog_vo import Status


def is_status_present(conn: psycopg.Connection, status: Status) -> int | None:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT status_id FROM status WHERE status_name = %s", (status.name,)
        )
        row = cur.fetchone()
    return row[0] if row else None


def insert_status(conn: psycopg.Connection, status: Status) -> int:
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO status (status_name, status_description, created_date, created_by) "
            "VALUES (%s, %s, %s, %s) RETURNING status_id",
            (status.name, status.description, datetime.now(timezone.utc), status.created_by),
        )
        return cur.fetchone()[0]


def ensure_status(conn: psycopg.Connection, status: Status) -> Status:
    """Fill status_id, inserting the row first if the name is new. No commit."""
    existing = is_status_present(conn, status)
    status.status_id = existing if existing is not None else insert_status(conn, status)
    return status


def insert_status_if_not_exist(
    status: Status, conn: psycopg.Connection | None = None
) -> Status:
    if conn is None:
        with connect() as own_conn:
            return insert_status_if_not_exist(status, own_conn)
    try:
        ensure_status(conn, status)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return status

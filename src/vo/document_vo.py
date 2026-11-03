"""Value objects for ingested documents, their confidence signals and chunks."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from src.vo.catalog_vo import Status
from src.vo.index_vo import IndexRun


@dataclass
class DocumentConfidence:
    name: str
    value: str
    created_by: str
    page_no: int = 0
    document_confidence_id: int | None = None


@dataclass
class DocumentChunk:
    content: str
    reading_order: int
    created_by: str
    content_hash: str | None = None
    label: str | None = None
    heading_path: list[str] | None = None
    region: list[dict[str, Any]] | None = None
    embedding_vector: list[float] | None = None
    chunk_id: int | None = None


@dataclass
class Document:
    document_name: str
    document_source: str
    source_hash: str
    status: Status
    index_run: IndexRun
    created_by: str
    start_time: datetime | None = None
    end_time: datetime | None = None
    errors: list[Any] = field(default_factory=list)
    confidences: list[DocumentConfidence] = field(default_factory=list)
    chunks: list[DocumentChunk] = field(default_factory=list)
    document_id: int | None = None

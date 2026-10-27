"""Extraction-time document and chunk records (pre-DB schema)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class ChunkRegion:
    page: int
    bbox: dict[str, Any]  # l, t, r, b (+ coord_origin when present)
    char_start: int | None
    char_end: int | None


@dataclass
class ChunkRecord:
    chunk_id: str
    content: str
    heading_level: list[str]
    chunk_type: str
    table_structure: Any | None
    regions: list[ChunkRegion]
    source_hash: str
    embedding_vector: list[float] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DocumentRecord:
    doc_id: str
    document_name: str
    index_version_id: str | None
    confidence: dict[str, Any] | None
    status: str
    errors: list[Any]
    start_date: datetime | None
    end_time: datetime | None
    source_hash: str
    chunks: list[ChunkRecord] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

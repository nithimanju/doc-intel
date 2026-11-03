"""Value objects for index versioning and component catalog/config tables."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.vo.catalog_vo import Status


@dataclass
class IndexConfig:
    name: str
    value: str
    description: str | None = None
    details: str | None = None


@dataclass
class Chunker:
    name: str
    version: str
    created_by: str
    description: str | None = None
    chunker_id: int | None = None
    configs: list[IndexConfig] = field(default_factory=list)


@dataclass
class Parser:
    name: str
    version: str
    created_by: str
    description: str | None = None
    parser_id: int | None = None
    configs: list[IndexConfig] = field(default_factory=list)


@dataclass
class Embedder:
    name: str
    version: str
    created_by: str
    description: str | None = None
    embedder_id: int | None = None
    configs: list[IndexConfig] = field(default_factory=list)


@dataclass
class IndexVersion:
    version: str
    chunker: Chunker
    embedder: Embedder
    parser: Parser
    created_by: str
    description: str | None = None
    config: dict[str, Any] | None = None
    index_version_id: int | None = None


@dataclass
class IndexRun:
    doc_count: int
    chunk_count: int
    status: Status
    index_version: IndexVersion
    created_by: str
    time_elapsed: float | None = None
    index_run_id: int | None = None

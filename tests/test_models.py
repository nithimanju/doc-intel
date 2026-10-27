"""Tests for src.injest.docling.models — the extraction-time dataclasses."""

from __future__ import annotations

from datetime import datetime, timezone

from src.injest.docling.models import ChunkRecord, ChunkRegion, DocumentRecord


def _region(**overrides):
    base = dict(page=1, bbox={"l": 0.0, "t": 10.0, "r": 5.0, "b": 0.0}, char_start=0, char_end=10)
    base.update(overrides)
    return ChunkRegion(**base)


def _chunk(**overrides):
    base = dict(
        chunk_id="doc:00000",
        content="hello world",
        heading_level=["1. INTRO"],
        chunk_type="text",
        table_structure=None,
        regions=[_region()],
        source_hash="abc123",
    )
    base.update(overrides)
    return ChunkRecord(**base)


class TestChunkRegion:
    def test_allows_none_char_offsets(self):
        region = _region(char_start=None, char_end=None)
        assert region.char_start is None
        assert region.char_end is None


class TestChunkRecord:
    def test_embedding_vector_defaults_to_none(self):
        chunk = _chunk()
        assert chunk.embedding_vector is None

    def test_to_dict_serializes_nested_regions(self):
        chunk = _chunk()
        out = chunk.to_dict()
        assert out["chunk_id"] == "doc:00000"
        assert isinstance(out["regions"], list)
        assert out["regions"][0] == {
            "page": 1,
            "bbox": {"l": 0.0, "t": 10.0, "r": 5.0, "b": 0.0},
            "char_start": 0,
            "char_end": 10,
        }

    def test_to_dict_preserves_embedding_vector_when_set(self):
        chunk = _chunk(embedding_vector=[0.1, 0.2, 0.3])
        assert chunk.to_dict()["embedding_vector"] == [0.1, 0.2, 0.3]


class TestDocumentRecord:
    def test_to_dict_serializes_nested_chunks(self):
        doc = DocumentRecord(
            doc_id="doc1",
            document_name="doc1.pdf",
            index_version_id=None,
            confidence={"mean_score": 0.9},
            status="success",
            errors=[],
            start_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
            end_time=datetime(2026, 1, 1, 0, 0, 30, tzinfo=timezone.utc),
            source_hash="abc123",
            chunks=[_chunk()],
        )
        out = doc.to_dict()
        assert out["doc_id"] == "doc1"
        assert len(out["chunks"]) == 1
        assert out["chunks"][0]["chunk_id"] == "doc:00000"

    def test_chunks_defaults_to_empty_list(self):
        doc = DocumentRecord(
            doc_id="doc1",
            document_name="doc1.pdf",
            index_version_id=None,
            confidence=None,
            status="failure",
            errors=["parse error"],
            start_date=None,
            end_time=None,
            source_hash="abc123",
        )
        assert doc.chunks == []

"""HybridChunker → ChunkRecord / DocumentRecord population."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from docling.chunking import HybridChunker
from docling.datamodel.document import ConversionResult
from docling_core.transforms.chunker.tokenizer.huggingface import HuggingFaceTokenizer
from docling_core.types.doc import DocItemLabel, TableItem
from docling_core.types.doc.document import DoclingDocument
from transformers import AutoTokenizer

from src.config.settings import (
    CHUNK_MAX_TOKEN_LIMIT,
    EMBEDDING_MODEL_NAME,
    HF_TOKEN,
    INDEX_VERSION_ID,
)
from src.injest.docling.converter import ConversionOutput
from src.injest.docling.models import ChunkRecord, ChunkRegion, DocumentRecord
from src.utils.logger import logger


def _label_value(label: Any) -> str:
    return getattr(label, "value", str(label))


def _derive_chunk_type(doc_items: list[Any]) -> str:
    """Prefer table when any doc_item is a table; otherwise first item label."""
    labels = [_label_value(getattr(item, "label", None)) for item in doc_items]
    if DocItemLabel.TABLE.value in labels or "table" in labels:
        return "table"
    if not labels:
        return "unknown"
    return labels[0]


def _bbox_dict(bbox: Any) -> dict[str, Any]:
    out: dict[str, Any] = {
        "l": float(bbox.l),
        "t": float(bbox.t),
        "r": float(bbox.r),
        "b": float(bbox.b),
    }
    origin = getattr(bbox, "coord_origin", None)
    if origin is not None:
        out["coord_origin"] = getattr(origin, "value", str(origin))
    return out


def _regions_from_doc_items(doc_items: list[Any]) -> list[ChunkRegion]:
    regions: list[ChunkRegion] = []
    for item in doc_items:
        for prov in getattr(item, "prov", None) or []:
            charspan = getattr(prov, "charspan", None) or (None, None)
            char_start = int(charspan[0]) if charspan[0] is not None else None
            char_end = int(charspan[1]) if charspan[1] is not None else None
            regions.append(
                ChunkRegion(
                    page=int(prov.page_no),
                    bbox=_bbox_dict(prov.bbox),
                    char_start=char_start,
                    char_end=char_end,
                )
            )
    return regions


def _table_structure_for_chunk(
    doc: DoclingDocument,
    doc_items: list[Any],
    chunk_type: str,
) -> Any | None:
    if chunk_type != "table":
        return None
    for item in doc_items:
        if _label_value(getattr(item, "label", None)) != DocItemLabel.TABLE.value:
            continue
        ref = getattr(item, "self_ref", None)
        if ref and hasattr(doc, "tables"):
            for table in doc.tables or []:
                if getattr(table, "self_ref", None) == ref and isinstance(table, TableItem):
                    data = getattr(table, "data", None)
                    if data is None:
                        return None
                    if hasattr(data, "model_dump"):
                        return data.model_dump()
                    return data
        if isinstance(item, TableItem):
            data = getattr(item, "data", None)
            if data is not None and hasattr(data, "model_dump"):
                return data.model_dump()
            return data
    return None


def _source_hash(result: ConversionResult, doc: DoclingDocument) -> str:
    input_hash = getattr(getattr(result, "input", None), "document_hash", None)
    if input_hash:
        return str(input_hash)
    origin = getattr(doc, "origin", None)
    binary_hash = getattr(origin, "binary_hash", None)
    if binary_hash is not None:
        return str(binary_hash)
    return ""


def _document_name(result: ConversionResult, doc: DoclingDocument) -> str:
    origin = getattr(doc, "origin", None)
    filename = getattr(origin, "filename", None)
    if filename:
        return str(filename)
    input_file = getattr(getattr(result, "input", None), "file", None)
    if input_file is not None:
        return str(getattr(input_file, "name", input_file))
    return getattr(doc, "name", None) or "unknown"


def _confidence_dict(result: ConversionResult) -> dict[str, Any] | None:
    confidence = getattr(result, "confidence", None)
    if confidence is None:
        return None
    if hasattr(confidence, "model_dump"):
        return confidence.model_dump(mode="json")
    return dict(confidence) if isinstance(confidence, dict) else {"value": confidence}


def _errors_list(result: ConversionResult) -> list[Any]:
    errors = getattr(result, "errors", None) or []
    out: list[Any] = []
    for err in errors:
        if hasattr(err, "model_dump"):
            out.append(err.model_dump(mode="json"))
        else:
            out.append(err)
    return out


def _build_chunk_record(
    *,
    chunk_index: int,
    chunk: Any,
    content: str,
    doc: DoclingDocument,
    source_hash: str,
    doc_id: str,
) -> ChunkRecord:
    doc_items = list(getattr(chunk.meta, "doc_items", None) or [])
    chunk_type = _derive_chunk_type(doc_items)
    headings = list(getattr(chunk.meta, "headings", None) or [])
    return ChunkRecord(
        chunk_id=f"{doc_id}:{chunk_index:05d}",
        content=content,
        heading_level=headings,
        chunk_type=chunk_type,
        table_structure=_table_structure_for_chunk(doc, doc_items, chunk_type),
        regions=_regions_from_doc_items(doc_items),
        source_hash=source_hash,
        embedding_vector=None,
    )


def chunk_docling_document(conversion: ConversionOutput) -> DocumentRecord:
    """Run HybridChunker and populate DocumentRecord + ChunkRecords.

    Fields not available yet (``index_version_id`` until issue 0.5, embeddings
    until the embed step) are left null. ``start_date`` / ``end_time`` come from
    the converter wall clock (Docling ``timings`` is often empty).
    """
    result = conversion.result
    doc = result.document
    source_hash = _source_hash(result, doc)
    document_name = _document_name(result, doc)
    doc_id = Path(document_name).stem or source_hash[:16] or "doc"

    logger.info(
        "Chunking %s (tokenizer=%s)",
        document_name,
        EMBEDDING_MODEL_NAME,
    )
    if not HF_TOKEN:
        raise RuntimeError(
            f"{EMBEDDING_MODEL_NAME} is a gated Hugging Face model."
        )

    tokenizer = HuggingFaceTokenizer(
        tokenizer=AutoTokenizer.from_pretrained(
            EMBEDDING_MODEL_NAME,
            token=HF_TOKEN,
        ),
        max_tokens=CHUNK_MAX_TOKEN_LIMIT,
    )
    chunker = HybridChunker(tokenizer=tokenizer, repeat_table_header=True)

    chunks: list[ChunkRecord] = []
    for i, chunk in enumerate(chunker.chunk(dl_doc=doc)):
        content = chunker.contextualize(chunk=chunk)
        record = _build_chunk_record(
            chunk_index=i,
            chunk=chunk,
            content=content,
            doc=doc,
            source_hash=source_hash,
            doc_id=doc_id,
        )
        chunks.append(record)
        logger.info(
            "chunk %s type=%s headings=%s regions=%s",
            record.chunk_id,
            record.chunk_type,
            record.heading_level,
            len(record.regions),
        )

    document = DocumentRecord(
        doc_id=doc_id,
        document_name=document_name,
        index_version_id=INDEX_VERSION_ID,
        confidence=_confidence_dict(result),
        status=str(getattr(result.status, "value", result.status)),
        errors=_errors_list(result),
        start_date=conversion.start_date,
        end_time=conversion.end_time,
        source_hash=source_hash,
        chunks=chunks,
    )
    logger.info(
        "Document %s status=%s chunks=%s",
        document.doc_id,
        document.status,
        len(document.chunks),
    )
    return document
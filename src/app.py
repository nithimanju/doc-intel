import time
from pathlib import Path

from src.config.index_settings import get_index_setting
from src.embed.client import EmbeddingFailedError, embed_documents
from src.injest.docling.chunker import chunk_docling_document
from src.injest.docling.converter import convert_document
from src.persistance.document_repo import insert_document
from src.persistance.index_repo import (
    finish_index_run,
    insert_index_run,
    insert_index_version_if_not_exist,
)
from src.utils.logger import logger
from src.vo.catalog_vo import STATUS_COMPLETED, STATUS_RUNNING, Status
from src.vo.index_vo import IndexRun

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SAMPLE_PDF = _REPO_ROOT / "corpus" / "raw" / "faa" / "dot_67913_DS1.pdf"


def main() -> None:
    if not _SAMPLE_PDF.is_file():
        raise FileNotFoundError(f"Sample PDF not found: {_SAMPLE_PDF}")

    started = time.perf_counter()
    conversion = convert_document(str(_SAMPLE_PDF))
    document = chunk_docling_document(conversion)
    logger.info(
        "done doc_id=%s status=%s chunks=%s source_hash=%s",
        document.doc_id,
        document.status,
        len(document.chunks),
        document.source_hash[:16],
    )

    texts = [chunk.content for chunk in document.chunks]
    ids = [chunk.chunk_id for chunk in document.chunks]
    try:
        vectors = embed_documents(texts, ids=ids)
    except EmbeddingFailedError:
        logger.exception("TEI embed failed for doc_id=%s", document.doc_id)
        raise

    embedded = 0
    for chunk, vector in zip(document.chunks, vectors, strict=True):
        if vector is None:
            document.errors.append(
                {"chunk_id": chunk.chunk_id, "error": "embed_rejected"}
            )
            continue
        chunk.embedding_vector = vector
        embedded += 1

    if document.chunks and embedded < len(document.chunks):
        document.status = "failure" if embedded == 0 else "partial_success"

    logger.info(
        "embedded=%s skipped=%s status=%s doc_id=%s",
        embedded,
        len(document.chunks) - embedded,
        document.status,
        document.doc_id,
    )

    index_version = insert_index_version_if_not_exist(get_index_setting())
    document.index_version = index_version
    document.index_version_id = str(index_version.index_version_id)
    logger.info(
        "index_version=%s id=%s chunker_id=%s parser_id=%s embedder_id=%s doc_id=%s",
        index_version.version,
        index_version.index_version_id,
        index_version.chunker.chunker_id,
        index_version.parser.parser_id,
        index_version.embedder.embedder_id,
        document.doc_id,
    )

    index_run = insert_index_run(
        IndexRun(
            doc_count=1,
            chunk_count=len(document.chunks),
            status=Status(name=STATUS_RUNNING, created_by="system"),
            index_version=index_version,
            created_by="system",
        )
    )
    document.index_run = index_run
    logger.info(
        "index_run_id=%s index_version_id=%s doc_id=%s",
        index_run.index_run_id,
        index_version.index_version_id,
        document.doc_id,
    )

    stored = insert_document(
        document, document_source=str(_SAMPLE_PDF.relative_to(_REPO_ROOT).as_posix())
    )
    finish_index_run(
        index_run,
        Status(name=STATUS_COMPLETED, created_by="system"),
        time.perf_counter() - started,
    )
    logger.info(
        "stored document_id=%s index_run_id=%s confidences=%s chunks=%s doc_id=%s",
        stored.document_id,
        index_run.index_run_id,
        len(stored.confidences),
        len(stored.chunks),
        document.doc_id,
    )


if __name__ == "__main__":
    main()

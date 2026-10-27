from pathlib import Path

from src.injest.docling.chunker import chunk_docling_document
from src.injest.docling.converter import convert_document
from src.utils.logger import logger

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SAMPLE_PDF = _REPO_ROOT / "corpus" / "raw" / "faa" / "dot_67913_DS1.pdf"


def main() -> None:
    if not _SAMPLE_PDF.is_file():
        raise FileNotFoundError(f"Sample PDF not found: {_SAMPLE_PDF}")

    conversion = convert_document(str(_SAMPLE_PDF))
    document = chunk_docling_document(conversion)
    logger.info(
        "done doc_id=%s status=%s chunks=%s source_hash=%s",
        document.doc_id,
        document.status,
        len(document.chunks),
        document.source_hash[:16],
    )
    logger.info(document)


if __name__ == "__main__":
    main()

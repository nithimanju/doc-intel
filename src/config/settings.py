"""Application settings loaded from environment / .env."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

_REPO_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(_REPO_ROOT / ".env", override=True)

LOG_FILE: str = os.getenv("LOG_FILE", "logs/doc-intel.log")

EMBEDDING_MODEL_NAME: str = os.getenv(
    "EMBEDDING_MODEL_NAME",
    "google/embeddinggemma-300m",
)
CHUNK_MAX_TOKEN_LIMIT: int = int(os.getenv("CHUNK_MAX_TOKEN_LIMIT", "1000"))

HF_TOKEN: str | None = os.getenv("HF_TOKEN") or None

DOCLING_IS_VLM: bool = os.getenv("DOCLING_IS_VLM", "false") == "true"
DOCLING_VLM_PRESET: str = os.getenv("DOCLING_VLM_PRESET", "granite_docling")
DOCLING_DO_OCR: bool = os.getenv("DOCLING_DO_OCR", "true") == "true"
DOCLING_DO_TABLE_STRUCTURE: bool = os.getenv("DOCLING_DO_TABLE_STRUCTURE", "true") == "true"
DOCLING_DO_CELL_MATCHING: bool = os.getenv("DOCLING_DO_CELL_MATCHING", "true") == "true"
DOCLING_IS_TESSERACT: bool = os.getenv("DOCLING_IS_TESSERACT", "true") == "true"
DOCLING_OCR_CPU_ONLY: bool = os.getenv("DOCLING_OCR_CPU_ONLY", "false") == "true"
DOCLING_DO_HEADING_HIERARCHY: bool = (
    os.getenv("DOCLING_DO_HEADING_HIERARCHY", "true") == "true"
)
DOCLING_PDF_BACKEND: str = os.getenv("DOCLING_PDF_BACKEND", "pypdfium2")

INDEX_VERSION_ID: str | None = os.getenv("INDEX_VERSION_ID") or None

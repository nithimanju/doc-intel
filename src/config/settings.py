"""Application settings loaded from environment / .env."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

_REPO_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(_REPO_ROOT / ".env", override=False)

# Embedding configuration
EMBEDDING_NAME: str = os.getenv("EMBEDDING_NAME", "microsoft/harrier-oss-v1-270m")
EMBEDDING_VERSION: str = os.getenv(
    "EMBEDDING_VERSION",
    "31de22b673913c7d658c0f03f792d77c2dcf8ebd",
)
EMBEDDING_MODEL_NAME: str = os.getenv(
    "EMBEDDING_MODEL_NAME",
    "microsoft/harrier-oss-v1-270m",
)
EMBEDDING_MODEL_REVISION: str = os.getenv(
    "EMBEDDING_MODEL_REVISION",
    "31de22b673913c7d658c0f03f792d77c2dcf8ebd",
)
EMBEDDING_BATCH_SIZE: int = int(os.getenv("EMBEDDING_BATCH_SIZE", "32"))
EMBEDDING_DIMENSION: int = int(os.getenv("EMBEDDING_DIMENSION", "640"))
IS_EMBEDDING_NORMALIZE: bool = os.getenv("IS_EMBEDDING_NORMALIZE", "true") == "true"
IS_EMBEDDING_TRUNCATE: bool = os.getenv("IS_EMBEDDING_TRUNCATE", "false") == "true"
EMBEDDING_BASE_URL: str = os.getenv(
    "EMBEDDING_BASE_URL",
    "http://embed:80",
).rstrip("/")

# Huggingface token
HF_TOKEN: str | None = os.getenv("HF_TOKEN") or None

# Parser configuration
PARSER_NAME: str = os.getenv("PARSER_NAME", "docling_parser")
PARSER_VERSION: str = os.getenv("PARSER_VERSION", "2.143.0")
DOCLING_IS_VLM: bool = os.getenv("DOCLING_IS_VLM", "false") == "true"
DOCLING_VLM_PRESET: str = os.getenv("DOCLING_VLM_PRESET", "granite_docling")
DOCLING_DO_OCR: bool = os.getenv("DOCLING_DO_OCR", "true") == "true"
DOCLING_DO_TABLE_STRUCTURE: bool = os.getenv("DOCLING_DO_TABLE_STRUCTURE", "true") == "true"
DOCLING_DO_CELL_MATCHING: bool = os.getenv("DOCLING_DO_CELL_MATCHING", "true") == "true"
DOCLING_IS_TESSERACT: bool = os.getenv("DOCLING_IS_TESSERACT", "false") == "true"
DOCLING_OCR_CPU_ONLY: bool = os.getenv("DOCLING_OCR_CPU_ONLY", "false") == "true"
DOCLING_DO_HEADING_HIERARCHY: bool = (
    os.getenv("DOCLING_DO_HEADING_HIERARCHY", "true") == "true"
)
DOCLING_PDF_BACKEND: str = os.getenv("DOCLING_PDF_BACKEND", "pypdfium2")

# Database configuration
POSTGRES_USER: str = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "postgres")
POSTGRES_DB: str = os.getenv("POSTGRES_DB", "doc_intel")
POSTGRES_HOST: str = os.getenv("POSTGRES_HOST", "db")
POSTGRES_PORT: str = os.getenv("POSTGRES_PORT", "5432")
DB_BATCH_SIZE: int = int(os.getenv("DB_BATCH_SIZE", "2000"))

DATABASE_URL: str = (
    f"postgresql+psycopg://{POSTGRES_USER}:{POSTGRES_PASSWORD}"
    f"@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
)

# Chunker configuration
CHUNK_MAX_TOKEN_LIMIT: int = int(os.getenv("CHUNK_MAX_TOKEN_LIMIT", "2000"))
CHUNK_NAME: str = os.getenv("CHUNK_NAME", "docling_hybrid_chunker")
CHUNKER_VERSION: str = os.getenv("CHUNKER_VERSION", "0.1")

# Index configuration
INDEX_VERSION_ID: str | None = os.getenv("INDEX_VERSION_ID") or None

# Logging configuration
LOG_FILE: str = os.getenv("LOG_FILE", "logs/doc-intel.log")

"""Docling PDF conversion — standard layout pipeline or VLM pipeline."""

from __future__ import annotations

import platform
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from docling.backend.pypdfium2_backend import PyPdfiumDocumentBackend
from docling.datamodel.accelerator_options import AcceleratorDevice, AcceleratorOptions
from docling.datamodel.base_models import InputFormat
from docling.datamodel.document import ConversionResult
from docling.datamodel.pipeline_options import (
    HeadingHierarchyOptions,
    PdfPipelineOptions,
    RapidOcrOptions,
    TableStructureOptions,
    TesseractCliOcrOptions,
    VlmConvertOptions,
    VlmPipelineOptions,
)
from docling.datamodel.vlm_engine_options import (
    MlxVlmEngineOptions,
    TransformersVlmEngineOptions,
)
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.pipeline.vlm_pipeline import VlmPipeline

from src.config import settings
from src.utils.logger import logger


@dataclass(frozen=True)
class DoclingConvertConfig:
    is_vlm: bool
    modes: dict[Any, Any] | None
    vlm_preset: str


@dataclass(frozen=True)
class ConversionOutput:
    """ConversionResult plus wall-clock bounds (Docling timings are often empty)."""

    result: ConversionResult
    start_date: datetime
    end_time: datetime

    @property
    def document(self) -> Any:
        return self.result.document



def _resolve_pdf_backend(name: str) -> Any:
    key = name.strip().lower()
    if key in {"pypdfium2", "pypdfium"}:
        return PyPdfiumDocumentBackend
    if key in {"docling_parse", "docling-parse", "default"}:
        return "docling_parse"
    raise ValueError(
        f"Unknown DOCLING_PDF_BACKEND={name!r}; use 'pypdfium2' or 'docling_parse'"
    )


def load_docling_config() -> DoclingConvertConfig:
    """Build conversion options from env / ``src.config.settings``."""
    is_vlm = settings.DOCLING_IS_VLM
    preset = settings.DOCLING_VLM_PRESET
    if is_vlm:
        logger.info(
            "Docling config: VLM pipeline (preset=%s)",
            preset,
        )
        return DoclingConvertConfig(is_vlm=True, modes=None, vlm_preset=preset)

    modes = get_default_modes(
        do_ocr=settings.DOCLING_DO_OCR,
        do_table_structure=settings.DOCLING_DO_TABLE_STRUCTURE,
        do_cell_matching=settings.DOCLING_DO_CELL_MATCHING,
        isTesseract=settings.DOCLING_IS_TESSERACT,
        is_ocr_cpu_only=settings.DOCLING_OCR_CPU_ONLY,
        backend=_resolve_pdf_backend(settings.DOCLING_PDF_BACKEND),
        do_heading_hierarchy=settings.DOCLING_DO_HEADING_HIERARCHY,
    )
    logger.info(
        "Docling config: standard pipeline "
        "(ocr=%s tesseract=%s tables=%s heading_hierarchy=%s backend=%s)",
        settings.DOCLING_DO_OCR,
        settings.DOCLING_IS_TESSERACT,
        settings.DOCLING_DO_TABLE_STRUCTURE,
        settings.DOCLING_DO_HEADING_HIERARCHY,
        settings.DOCLING_PDF_BACKEND,
    )
    return DoclingConvertConfig(is_vlm=False, modes=modes, vlm_preset=preset)


def convert_document(
    file_path: str,
    modes: dict[str, Any] | None = None,
    *,
    is_vlm: bool | None = None,
    vlm_preset: str | None = None,
) -> ConversionOutput:
    """Convert a PDF via the standard pipeline or the VLM pipeline.

    When ``is_vlm`` / ``modes`` / ``vlm_preset`` are omitted, values come from
    ``load_docling_config()`` (env-driven). Returns the full ConversionResult
    (status, confidence, errors) plus start/end timestamps for DocumentRecord.
    """
    cfg = load_docling_config()
    use_vlm = cfg.is_vlm if is_vlm is None else is_vlm
    preset = vlm_preset or cfg.vlm_preset
    format_options = modes if modes is not None else cfg.modes

    if use_vlm:
        return convert_document_via_vlm(file_path, preset=preset)
    if format_options is None:
        raise ValueError("modes is required when is_vlm=False")
    return convert_to_docling_document(file_path, format_options)


def convert_to_docling_document(file_path: str, modes: dict[str, Any]) -> ConversionOutput:
    logger.info("Converting %s to docling document (standard pipeline)", file_path)
    start = datetime.now(timezone.utc)
    converter = DocumentConverter(format_options=modes)
    result = converter.convert(file_path)
    end = datetime.now(timezone.utc)
    logger.info(
        "Converted %s (status=%s)",
        file_path,
        getattr(result.status, "value", result.status),
    )
    return ConversionOutput(result=result, start_date=start, end_time=end)


def convert_document_via_vlm(
    file_path: str,
    *,
    preset: str = "granite_docling",
) -> ConversionOutput:
    """Convert a PDF with Docling's VLM pipeline (Granite-Docling by default).

    Uses the preset API (recommended). Engine is MLX on Apple Silicon, Transformers
    everywhere else (including the Linux Docker host).
    """
    logger.info("Converting %s via VLM pipeline (preset=%s)", file_path, preset)

    engine_options = (
        MlxVlmEngineOptions()
        if platform.system() == "Darwin" and platform.machine() == "arm64"
        else TransformersVlmEngineOptions()
    )
    vlm_options = VlmConvertOptions.from_preset(
        preset,
        engine_options=engine_options,
    )
    repo_id = vlm_options.model_spec.get_repo_id(
        vlm_options.engine_options.engine_type
    )
    logger.info("VLM model: %s", repo_id)

    converter = DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(
                pipeline_cls=VlmPipeline,
                pipeline_options=VlmPipelineOptions(vlm_options=vlm_options),
            ),
        }
    )
    start = datetime.now(timezone.utc)
    result = converter.convert(source=file_path)
    end = datetime.now(timezone.utc)
    logger.info(
        "Converted %s via VLM (status=%s)",
        file_path,
        getattr(result.status, "value", result.status),
    )
    return ConversionOutput(result=result, start_date=start, end_time=end)


def get_default_modes(
    do_ocr: bool = True,
    do_table_structure: bool = True,
    do_cell_matching: bool = True,
    isTesseract: bool = True,
    is_ocr_cpu_only: bool = False,
    backend: Any = "pypdfium2",
    do_heading_hierarchy: bool = True,
) -> dict[Any, Any]:
    pipeline_options = PdfPipelineOptions()
    pipeline_options.do_ocr = do_ocr
    pipeline_options.do_table_structure = do_table_structure
    pipeline_options.table_structure_options = TableStructureOptions(
        do_cell_matching=do_cell_matching
    )
    pipeline_options.generate_parsed_pages = True
    pipeline_options.heading_hierarchy_options = HeadingHierarchyOptions(
        enabled=do_heading_hierarchy
    )
    if isTesseract:
        pipeline_options.ocr_options = TesseractCliOcrOptions(lang=["eng"])
    else:
        pipeline_options.ocr_options = RapidOcrOptions()

    device = AcceleratorDevice.CPU if is_ocr_cpu_only else AcceleratorDevice.AUTO
    pipeline_options.accelerator_options = AcceleratorOptions(device=device)

    return {
        InputFormat.PDF: PdfFormatOption(
            pipeline_options=pipeline_options,
            backend=backend,
        )
    }

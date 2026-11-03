from src.config.config_items import to_index_configs
from src.config.settings import (
    DOCLING_DO_CELL_MATCHING,
    DOCLING_DO_HEADING_HIERARCHY,
    DOCLING_DO_OCR,
    DOCLING_DO_TABLE_STRUCTURE,
    DOCLING_IS_TESSERACT,
    DOCLING_IS_VLM,
    DOCLING_OCR_CPU_ONLY,
    DOCLING_PDF_BACKEND,
    DOCLING_VLM_PRESET,
    PARSER_NAME,
    PARSER_VERSION,
)
from src.vo.index_vo import Parser


def get_parser_setting(created_by: str = "system") -> Parser:
    return Parser(
        name=PARSER_NAME,
        version=PARSER_VERSION,
        created_by=created_by,
        configs=to_index_configs(
            {
                "is_vlm": DOCLING_IS_VLM,
                "vlm_preset": DOCLING_VLM_PRESET,
                "do_ocr": DOCLING_DO_OCR,
                "do_table_structure": DOCLING_DO_TABLE_STRUCTURE,
                "do_cell_matching": DOCLING_DO_CELL_MATCHING,
                "is_tesseract": DOCLING_IS_TESSERACT,
                "ocr_cpu_only": DOCLING_OCR_CPU_ONLY,
                "do_heading_hierarchy": DOCLING_DO_HEADING_HIERARCHY,
                "pdf_backend": DOCLING_PDF_BACKEND,
            }
        ),
    )

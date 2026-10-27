"""Tests for src.injest.docling.converter — config resolution only.

These patch attributes directly on the already-imported ``src.config.settings``
module object rather than setting env vars and reloading, so they never touch
the real project ``.env`` file and don't depend on load order.
"""

from __future__ import annotations

import pytest

from docling.backend.pypdfium2_backend import PyPdfiumDocumentBackend
from docling.datamodel.accelerator_options import AcceleratorDevice
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import RapidOcrOptions, TesseractCliOcrOptions

from src.injest.docling.converter import (
    DoclingConvertConfig,
    _resolve_pdf_backend,
    get_default_modes,
    load_docling_config,
)


class TestResolvePdfBackend:
    @pytest.mark.parametrize("name", ["pypdfium2", "pypdfium", "PyPdfium2", "  pypdfium2  "])
    def test_recognizes_pypdfium_variants(self, name):
        assert _resolve_pdf_backend(name) is PyPdfiumDocumentBackend

    @pytest.mark.parametrize("name", ["docling_parse", "docling-parse", "default", "DEFAULT"])
    def test_recognizes_docling_parse_variants(self, name):
        assert _resolve_pdf_backend(name) == "docling_parse"

    def test_unknown_backend_raises(self):
        with pytest.raises(ValueError, match="Unknown DOCLING_PDF_BACKEND"):
            _resolve_pdf_backend("some_other_backend")


class TestGetDefaultModes:
    def test_keys_on_pdf_input_format(self):
        modes = get_default_modes(backend=PyPdfiumDocumentBackend)
        assert set(modes.keys()) == {InputFormat.PDF}

    def test_tesseract_selected_when_isTesseract_true(self):
        modes = get_default_modes(isTesseract=True, backend=PyPdfiumDocumentBackend)
        opts = modes[InputFormat.PDF].pipeline_options
        assert isinstance(opts.ocr_options, TesseractCliOcrOptions)

    def test_rapidocr_selected_when_isTesseract_false(self):
        modes = get_default_modes(isTesseract=False, backend=PyPdfiumDocumentBackend)
        opts = modes[InputFormat.PDF].pipeline_options
        assert isinstance(opts.ocr_options, RapidOcrOptions)

    def test_do_ocr_and_table_structure_flags_passed_through(self):
        modes = get_default_modes(do_ocr=False, do_table_structure=False, backend=PyPdfiumDocumentBackend)
        opts = modes[InputFormat.PDF].pipeline_options
        assert opts.do_ocr is False
        assert opts.do_table_structure is False

    def test_heading_hierarchy_enabled_flag_passed_through(self):
        modes = get_default_modes(do_heading_hierarchy=False, backend=PyPdfiumDocumentBackend)
        opts = modes[InputFormat.PDF].pipeline_options
        assert opts.heading_hierarchy_options.enabled is False

    def test_cpu_only_forces_cpu_accelerator(self):
        modes = get_default_modes(is_ocr_cpu_only=True, backend=PyPdfiumDocumentBackend)
        opts = modes[InputFormat.PDF].pipeline_options
        assert opts.accelerator_options.device == AcceleratorDevice.CPU

    def test_not_cpu_only_uses_auto_accelerator(self):
        modes = get_default_modes(is_ocr_cpu_only=False, backend=PyPdfiumDocumentBackend)
        opts = modes[InputFormat.PDF].pipeline_options
        assert opts.accelerator_options.device == AcceleratorDevice.AUTO

    def test_default_backend_param_is_already_resolved(self):
        """backend's default must be a real backend class, not a name string."""
        modes = get_default_modes()
        opts = modes[InputFormat.PDF]
        assert opts.backend is PyPdfiumDocumentBackend


class TestLoadDoclingConfig:
    def test_vlm_mode_returns_no_modes(self, monkeypatch):
        import src.config.settings as settings

        monkeypatch.setattr(settings, "DOCLING_IS_VLM", True)
        monkeypatch.setattr(settings, "DOCLING_VLM_PRESET", "granite_docling")
        cfg = load_docling_config()
        assert cfg == DoclingConvertConfig(is_vlm=True, modes=None, vlm_preset="granite_docling")

    def test_standard_mode_builds_modes_dict(self, monkeypatch):
        import src.config.settings as settings

        monkeypatch.setattr(settings, "DOCLING_IS_VLM", False)
        monkeypatch.setattr(settings, "DOCLING_DO_OCR", True)
        monkeypatch.setattr(settings, "DOCLING_DO_TABLE_STRUCTURE", True)
        monkeypatch.setattr(settings, "DOCLING_DO_CELL_MATCHING", True)
        monkeypatch.setattr(settings, "DOCLING_IS_TESSERACT", True)
        monkeypatch.setattr(settings, "DOCLING_OCR_CPU_ONLY", False)
        monkeypatch.setattr(settings, "DOCLING_PDF_BACKEND", "pypdfium2")
        monkeypatch.setattr(settings, "DOCLING_DO_HEADING_HIERARCHY", True)
        cfg = load_docling_config()
        assert cfg.is_vlm is False
        assert InputFormat.PDF in cfg.modes

    def test_unknown_backend_in_settings_raises(self, monkeypatch):
        import src.config.settings as settings

        monkeypatch.setattr(settings, "DOCLING_IS_VLM", False)
        monkeypatch.setattr(settings, "DOCLING_PDF_BACKEND", "nonsense_backend")
        with pytest.raises(ValueError):
            load_docling_config()

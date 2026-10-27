"""Tests for src.config.settings env parsing.

``settings.py`` calls ``load_dotenv(..., override=True)`` at import time, which
would let a real project ``.env`` silently override whatever env vars a test
sets via monkeypatch+reload. Every test here stubs out ``load_dotenv`` first
so the module under test never touches the real ``.env`` file — only the env
vars this test explicitly sets (via ``monkeypatch.setenv``/``delenv``) are in
play.
"""

from __future__ import annotations

import importlib

import pytest


@pytest.fixture
def reload_settings(monkeypatch):
    """Reload src.config.settings with load_dotenv stubbed to a no-op.

    Returns a function that performs the reload after the test has set up
    its env vars, so ``settings.py``'s module-level reads pick them up.
    """

    def _reload():
        import src.config.settings as settings_module

        # settings.py does `from dotenv import load_dotenv`, so reload() re-runs
        # that import and rebinds the module-level name to the real function
        # again — patching the module's own attribute doesn't survive a reload.
        # Patch the function in the `dotenv` package itself instead.
        monkeypatch.setattr("dotenv.load_dotenv", lambda *a, **k: None)
        return importlib.reload(settings_module)

    return _reload


class TestBooleanFlags:
    @pytest.mark.parametrize(
        "env_value,expected",
        [("true", True), ("false", False), ("TRUE", False), ("", False)],
    )
    def test_docling_do_ocr_only_true_lowercase_is_truthy(self, monkeypatch, reload_settings, env_value, expected):
        monkeypatch.setenv("DOCLING_DO_OCR", env_value)
        settings = reload_settings()
        assert settings.DOCLING_DO_OCR is expected

    def test_docling_do_ocr_defaults_true_when_unset(self, monkeypatch, reload_settings):
        monkeypatch.delenv("DOCLING_DO_OCR", raising=False)
        settings = reload_settings()
        assert settings.DOCLING_DO_OCR is True

    def test_docling_is_vlm_defaults_false_when_unset(self, monkeypatch, reload_settings):
        monkeypatch.delenv("DOCLING_IS_VLM", raising=False)
        settings = reload_settings()
        assert settings.DOCLING_IS_VLM is False


class TestScalarSettings:
    def test_chunk_max_token_limit_parses_int_from_env(self, monkeypatch, reload_settings):
        monkeypatch.setenv("CHUNK_MAX_TOKEN_LIMIT", "512")
        settings = reload_settings()
        assert settings.CHUNK_MAX_TOKEN_LIMIT == 512

    def test_chunk_max_token_limit_default(self, monkeypatch, reload_settings):
        monkeypatch.delenv("CHUNK_MAX_TOKEN_LIMIT", raising=False)
        settings = reload_settings()
        assert settings.CHUNK_MAX_TOKEN_LIMIT == 1000

    def test_hf_token_empty_string_normalizes_to_none(self, monkeypatch, reload_settings):
        monkeypatch.setenv("HF_TOKEN", "")
        settings = reload_settings()
        assert settings.HF_TOKEN is None

    def test_hf_token_passthrough_when_set(self, monkeypatch, reload_settings):
        monkeypatch.setenv("HF_TOKEN", "hf_abc123")
        settings = reload_settings()
        assert settings.HF_TOKEN == "hf_abc123"

    def test_index_version_id_empty_string_normalizes_to_none(self, monkeypatch, reload_settings):
        monkeypatch.setenv("INDEX_VERSION_ID", "")
        settings = reload_settings()
        assert settings.INDEX_VERSION_ID is None

    def test_embedding_model_name_default(self, monkeypatch, reload_settings):
        monkeypatch.delenv("EMBEDDING_MODEL_NAME", raising=False)
        settings = reload_settings()
        assert settings.EMBEDDING_MODEL_NAME == "google/embeddinggemma-300m"

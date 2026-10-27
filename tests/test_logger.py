"""Tests for src.utils.logger.setup_logger.

Patches LOG_FILE to a tmp path per test so nothing writes into the real
logs/doc-intel.log, and uses a fresh logger name per test so handlers from
one test can't leak into (or be hidden by) another via the global logging
registry.
"""

from __future__ import annotations

import logging

from src.utils import logger as logger_module


def test_creates_file_and_console_handlers(tmp_path, monkeypatch):
    monkeypatch.setattr(logger_module, "LOG_FILE", str(tmp_path / "test.log"))
    log = logger_module.setup_logger("doc-intel-test-handlers")
    assert len(log.handlers) == 2
    assert any(isinstance(h, logging.FileHandler) for h in log.handlers)
    assert any(isinstance(h, logging.StreamHandler) for h in log.handlers)


def test_does_not_duplicate_handlers_on_second_call(tmp_path, monkeypatch):
    monkeypatch.setattr(logger_module, "LOG_FILE", str(tmp_path / "test.log"))
    logger_module.setup_logger("doc-intel-test-idempotent")
    log = logger_module.setup_logger("doc-intel-test-idempotent")
    assert len(log.handlers) == 2


def test_sets_info_level(tmp_path, monkeypatch):
    monkeypatch.setattr(logger_module, "LOG_FILE", str(tmp_path / "test.log"))
    log = logger_module.setup_logger("doc-intel-test-level")
    assert log.level == logging.INFO

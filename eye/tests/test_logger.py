"""Tests for utils/logger.py — structured logging, JSON format, LLM call logging."""

from __future__ import annotations

import json
import logging
from io import StringIO

from utils.logger import _JsonFormatter, get_console, log_llm_call, setup_logger


# ---------------------------------------------------------------------------
# _JsonFormatter
# ---------------------------------------------------------------------------

class TestJsonFormatter:
    def test_basic_format(self):
        formatter = _JsonFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="hello world",
            args=(),
            exc_info=None,
        )
        result = formatter.format(record)
        data = json.loads(result)

        assert data["level"] == "INFO"
        assert data["logger"] == "test"
        assert data["message"] == "hello world"
        assert "timestamp" in data

    def test_with_data_attribute(self):
        formatter = _JsonFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.DEBUG,
            pathname="",
            lineno=0,
            msg="test msg",
            args=(),
            exc_info=None,
        )
        record.data = {"key": "value", "count": 42}  # type: ignore[attr-defined]
        result = formatter.format(record)
        data = json.loads(result)

        assert data["data"]["key"] == "value"
        assert data["data"]["count"] == 42

    def test_without_data_attribute(self):
        formatter = _JsonFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.WARNING,
            pathname="",
            lineno=0,
            msg="no data",
            args=(),
            exc_info=None,
        )
        result = formatter.format(record)
        data = json.loads(result)

        assert "data" not in data

    def test_unicode_handling(self):
        formatter = _JsonFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="한국어 메시지",
            args=(),
            exc_info=None,
        )
        result = formatter.format(record)
        data = json.loads(result)
        assert data["message"] == "한국어 메시지"

    def test_output_is_valid_json(self):
        formatter = _JsonFormatter()
        record = logging.LogRecord(
            name="comadeye",
            level=logging.ERROR,
            pathname="test.py",
            lineno=42,
            msg="error occurred",
            args=(),
            exc_info=None,
        )
        result = formatter.format(record)
        # Should not raise
        parsed = json.loads(result)
        assert isinstance(parsed, dict)


# ---------------------------------------------------------------------------
# setup_logger
# ---------------------------------------------------------------------------

class TestSetupLogger:
    def test_creates_logger(self, tmp_path):
        logger = setup_logger(
            "test_logger_1",
            level="DEBUG",
            log_dir=str(tmp_path),
        )
        assert logger.name == "test_logger_1"
        assert logger.level == logging.DEBUG

    def test_idempotent_setup(self, tmp_path):
        logger1 = setup_logger(
            "test_logger_idempotent",
            level="INFO",
            log_dir=str(tmp_path),
        )
        handler_count = len(logger1.handlers)

        logger2 = setup_logger(
            "test_logger_idempotent",
            level="INFO",
            log_dir=str(tmp_path),
        )
        # Should not add more handlers
        assert len(logger2.handlers) == handler_count
        assert logger1 is logger2

    def test_creates_log_directory(self, tmp_path):
        log_dir = tmp_path / "nested" / "logs"
        setup_logger("test_logger_dir", log_dir=str(log_dir))
        assert log_dir.exists()

    def test_file_handler_creates_jsonl(self, tmp_path):
        name = "test_logger_file"
        logger = setup_logger(name, log_dir=str(tmp_path))
        logger.info("test message")

        # Flush handlers
        for handler in logger.handlers:
            handler.flush()

        jsonl_files = list(tmp_path.glob("comadeye_*.jsonl"))
        assert len(jsonl_files) >= 1

    def test_with_settings_object(self, tmp_path):
        """Test passing a LoggingSettings-like object."""
        # Clear any existing comadeye logger to avoid idempotency short-circuit
        existing = logging.getLogger("comadeye")
        existing.handlers.clear()

        mock_settings = type("MockSettings", (), {
            "level": "WARNING",
            "log_dir": str(tmp_path),
            "log_llm_calls": False,
        })()

        logger = setup_logger(mock_settings)
        assert logger.name == "comadeye"
        assert logger.level == logging.WARNING

    def test_with_llm_logging_enabled(self, tmp_path):
        name = "test_logger_llm"
        setup_logger(name, log_dir=str(tmp_path), log_llm_calls=True)

        llm_logger = logging.getLogger(f"{name}.llm")
        assert llm_logger.level == logging.DEBUG
        assert not llm_logger.propagate

    def test_custom_level(self, tmp_path):
        logger = setup_logger(
            "test_logger_level",
            level="WARNING",
            log_dir=str(tmp_path),
        )
        assert logger.level == logging.WARNING


# ---------------------------------------------------------------------------
# log_llm_call
# ---------------------------------------------------------------------------

class TestLogLlmCall:
    def test_logs_to_llm_logger(self, tmp_path):
        # Set up the llm logger first
        llm_logger = logging.getLogger("comadeye.llm")
        # Clear existing handlers to avoid test pollution
        llm_logger.handlers.clear()

        handler = logging.StreamHandler(StringIO())
        handler.setFormatter(_JsonFormatter())
        llm_logger.addHandler(handler)
        llm_logger.setLevel(logging.DEBUG)
        llm_logger.propagate = False

        log_llm_call(
            prompt="test prompt",
            response="test response",
            model="llama3.1:8b",
            tokens_in=100,
            tokens_out=50,
            duration_ms=1500,
        )

        output = handler.stream.getvalue()  # type: ignore
        data = json.loads(output.strip())
        assert data["message"] == "llm_call"
        assert data["data"]["model"] == "llama3.1:8b"
        assert data["data"]["tokens_in"] == 100
        assert data["data"]["duration_ms"] == 1500

        # Cleanup
        llm_logger.handlers.clear()


# ---------------------------------------------------------------------------
# get_console
# ---------------------------------------------------------------------------

class TestGetConsole:
    def test_returns_console(self):
        from rich.console import Console
        c = get_console()
        assert isinstance(c, Console)

    def test_returns_same_instance(self):
        c1 = get_console()
        c2 = get_console()
        assert c1 is c2

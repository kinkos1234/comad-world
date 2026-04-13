"""구조화 로깅 — JSON 포맷 + Rich 콘솔 연동"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.logging import RichHandler


_console = Console()


def setup_logger(
    name_or_settings: str | Any = "comadeye",
    level: str = "INFO",
    log_dir: str = "data/logs",
    log_llm_calls: bool = True,
) -> logging.Logger:
    """Rich 핸들러 + 파일 핸들러로 로거를 설정한다.

    LoggingSettings 객체 또는 개별 인자를 모두 받는다.
    """
    # LoggingSettings 객체가 전달된 경우 필드를 추출
    if not isinstance(name_or_settings, str) and hasattr(name_or_settings, "level"):
        settings = name_or_settings
        name = "comadeye"
        level = getattr(settings, "level", level)
        log_dir = getattr(settings, "log_dir", log_dir)
        log_llm_calls = getattr(settings, "log_llm_calls", log_llm_calls)
    else:
        name = name_or_settings

    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Rich 콘솔 핸들러
    rich_handler = RichHandler(
        console=_console,
        show_time=True,
        show_path=False,
        markup=True,
    )
    rich_handler.setLevel(logging.INFO)
    logger.addHandler(rich_handler)

    # 파일 핸들러 (JSONL)
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(
        log_path / f"comadeye_{datetime.now(timezone.utc).strftime('%Y%m%d')}.jsonl",
        encoding="utf-8",
    )
    file_handler.setFormatter(_JsonFormatter())
    logger.addHandler(file_handler)

    # LLM 전용 로거
    if log_llm_calls:
        llm_logger = logging.getLogger(f"{name}.llm")
        llm_handler = logging.FileHandler(
            log_path / f"llm_calls_{datetime.now(timezone.utc).strftime('%Y%m%d')}.jsonl",
            encoding="utf-8",
        )
        llm_handler.setFormatter(_JsonFormatter())
        llm_logger.addHandler(llm_handler)
        llm_logger.setLevel(logging.DEBUG)
        llm_logger.propagate = False

    return logger


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if hasattr(record, "data"):
            entry["data"] = record.data  # type: ignore[attr-defined]
        return json.dumps(entry, ensure_ascii=False)


def log_llm_call(
    prompt: str,
    response: str,
    model: str,
    tokens_in: int = 0,
    tokens_out: int = 0,
    duration_ms: int = 0,
) -> None:
    """LLM 호출을 전용 로거에 기록한다."""
    llm_logger = logging.getLogger("comadeye.llm")
    record = llm_logger.makeRecord(
        name="comadeye.llm",
        level=logging.INFO,
        fn="",
        lno=0,
        msg="llm_call",
        args=(),
        exc_info=None,
    )
    record.data = {  # type: ignore[attr-defined]
        "model": model,
        "prompt": prompt,
        "response": response,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "duration_ms": duration_ms,
    }
    llm_logger.handle(record)


def get_console() -> Console:
    return _console

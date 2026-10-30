from __future__ import annotations

import logging
import re
import sys
from collections.abc import Iterator
from logging.handlers import RotatingFileHandler
from pathlib import Path

import pytest

from level_bridge.logging_config import (
    LOG_BACKUP_COUNT,
    LOG_FILE_NAME,
    LOG_MAX_BYTES,
    EasternFormatter,
    configure_logging,
)

TIMESTAMP = r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}-0[45]:00"


@pytest.fixture
def restore_root_logging() -> Iterator[None]:
    root = logging.getLogger()
    level = root.level
    yield
    for handler in list(root.handlers):
        if isinstance(handler.formatter, EasternFormatter):
            root.removeHandler(handler)
            handler.close()
    root.setLevel(level)


def emit_sample() -> None:
    logging.getLogger("level_bridge.sample").info("sample message")


def test_root_has_exactly_one_handler_per_destination(
    tmp_path: Path, restore_root_logging: None
) -> None:
    log_dir = tmp_path / "logs"
    configure_logging(log_dir)
    configure_logging(log_dir)

    root = logging.getLogger()
    file_handlers = [h for h in root.handlers if isinstance(h, RotatingFileHandler)]
    stream_handlers = [
        h
        for h in root.handlers
        if type(h) is logging.StreamHandler and getattr(h, "stream", None) is sys.stdout
    ]
    assert len(root.handlers) == 2
    assert len(file_handlers) == 1
    assert len(stream_handlers) == 1

    file_handler = file_handlers[0]
    assert Path(file_handler.baseFilename) == log_dir / LOG_FILE_NAME
    assert file_handler.maxBytes == LOG_MAX_BYTES == 1_048_576
    assert file_handler.backupCount == LOG_BACKUP_COUNT == 3
    assert file_handler.level == logging.INFO
    assert stream_handlers[0].level == logging.INFO
    assert log_dir.is_dir()


def test_log_entries_have_eastern_timestamp_location_and_function(
    tmp_path: Path, restore_root_logging: None
) -> None:
    log_path = configure_logging(tmp_path / "logs")
    emit_sample()
    for handler in logging.getLogger().handlers:
        handler.flush()

    line = log_path.read_text(encoding="utf-8").strip().splitlines()[-1]
    pattern = rf"^{TIMESTAMP} \[INFO\] test_logging\.py:\d+ emit_sample - sample message$"
    assert re.match(pattern, line), line


def test_server_loggers_propagate_to_root(tmp_path: Path, restore_root_logging: None) -> None:
    logging.getLogger("uvicorn.error").addHandler(logging.NullHandler())
    configure_logging(tmp_path / "logs")
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        server_logger = logging.getLogger(name)
        assert server_logger.handlers == []
        assert server_logger.propagate is True

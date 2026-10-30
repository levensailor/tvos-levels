"""Root logger configuration: one rotating file handler and one stdout handler."""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from level_bridge.timeutil import eastern_isoformat

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LOG_DIR = PROJECT_ROOT / "logs"
LOG_FILE_NAME = "app.log"
LOG_MAX_BYTES = 1_048_576
LOG_BACKUP_COUNT = 3
LOG_LEVEL = logging.INFO
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(filename)s:%(lineno)d %(funcName)s - %(message)s"
SERVER_LOGGER_NAMES = ("uvicorn", "uvicorn.error", "uvicorn.access")


class EasternFormatter(logging.Formatter):
    """Formats record timestamps in America/New_York with millisecond precision."""

    def formatTime(self, record: logging.LogRecord, datefmt: str | None = None) -> str:
        return eastern_isoformat(record.created)


def configure_logging(log_dir: Path = DEFAULT_LOG_DIR) -> Path:
    """Replace root handlers with exactly one file handler and one stdout handler.

    Returns the path of the active log file.
    """
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / LOG_FILE_NAME
    formatter = EasternFormatter(LOG_FORMAT)

    file_handler = RotatingFileHandler(
        log_path, maxBytes=LOG_MAX_BYTES, backupCount=LOG_BACKUP_COUNT, encoding="utf-8"
    )
    file_handler.setLevel(LOG_LEVEL)
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(LOG_LEVEL)
    console_handler.setFormatter(formatter)

    root = logging.getLogger()
    for handler in list(root.handlers):
        root.removeHandler(handler)
        if isinstance(handler.formatter, EasternFormatter):
            handler.close()
    root.setLevel(LOG_LEVEL)
    root.addHandler(file_handler)
    root.addHandler(console_handler)

    for name in SERVER_LOGGER_NAMES:
        server_logger = logging.getLogger(name)
        for handler in list(server_logger.handlers):
            server_logger.removeHandler(handler)
        server_logger.propagate = True

    return log_path

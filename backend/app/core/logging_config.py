"""Application logging configuration with bounded rotating log files."""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
LOG_MAX_BYTES = 10 * 1024 * 1024
LOG_BACKUP_COUNT = 5


def _backend_root() -> Path:
    """Return the backend directory regardless of the current working dir."""
    return Path(__file__).resolve().parents[2]


def setup_logging(level: int = logging.INFO) -> Path:
    """Configure console + RotatingFileHandler logging idempotently.

    Log file: ``backend/logs/app.log``
    Rotation: 10 MB, 5 backups.
    """
    backend_root = _backend_root()
    log_dir = backend_root / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "app.log"

    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    formatter = logging.Formatter(LOG_FORMAT)

    # Remove duplicate handlers from repeated app imports during tests/reload.
    for handler in list(root_logger.handlers):
        if getattr(handler, "_smart_newspaper_handler", False):
            root_logger.removeHandler(handler)
            try:
                handler.close()
            except Exception:
                pass

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    console_handler._smart_newspaper_handler = True  # type: ignore[attr-defined]

    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=LOG_MAX_BYTES,
        backupCount=LOG_BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)
    file_handler._smart_newspaper_handler = True  # type: ignore[attr-defined]

    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)
    logging.getLogger(__name__).info("Logging configured with RotatingFileHandler at %s", log_file)
    return log_file

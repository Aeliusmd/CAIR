"""Configure application and submission tracking log files."""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from cair_integration.submission_log import LOGGER_NAME

DEFAULT_LOG_DIR = "logs"
SERVICE_LOG = "cair_service.log"
SUBMISSION_LOG = "cair_submissions.log"


def setup_logging(log_dir: str = DEFAULT_LOG_DIR) -> Path:
    """Set up console + service log + dedicated submission status log."""
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    submission_fmt = logging.Formatter("%(asctime)s | %(message)s")

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.handlers.clear()

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(fmt)
    root.addHandler(console)

    service_handler = RotatingFileHandler(
        log_path / SERVICE_LOG,
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    service_handler.setFormatter(fmt)
    root.addHandler(service_handler)

    submission_logger = logging.getLogger(LOGGER_NAME)
    submission_logger.setLevel(logging.INFO)
    submission_logger.handlers.clear()
    submission_logger.propagate = False

    submission_handler = RotatingFileHandler(
        log_path / SUBMISSION_LOG,
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    submission_handler.setFormatter(submission_fmt)
    submission_logger.addHandler(submission_handler)

    return log_path

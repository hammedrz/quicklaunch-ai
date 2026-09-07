"""Centralized logging configuration for QuickLaunch AI."""
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import sys
from typing import Optional

from .config import config

LOG_FORMAT = "%(asctime)s [%(levelname)-7s] [%(name)s] %(message)s"
DATE_FORMAT = "%H:%M:%S"

_logging_initialized = False


def get_log_file_path() -> Path:
    """Returns the persistent log file path in the app data directory."""
    return config.app_dir / "quicklaunch.log"


def setup_logging(level: Optional[str] = None) -> Path:
    """Configures application-wide logging to console and a rotating log file.

    Args:
        level: Optional log level string ("DEBUG", "INFO", "WARNING", "ERROR").
               Defaults to LOG_LEVEL env var, or "DEBUG" if not specified.

    Returns:
        The Path to the log file.
    """
    global _logging_initialized
    log_file = get_log_file_path()

    if _logging_initialized:
        return log_file

    raw_level = (level or os.getenv("LOG_LEVEL", "DEBUG")).upper().strip()
    log_level = getattr(logging, raw_level, logging.DEBUG)

    # Root logger configuration
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Remove any existing handlers to prevent duplicate output
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)

    formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)

    # 1. Console Handler (stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # 2. Rotating File Handler (persisted in config.app_dir)
    try:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=5 * 1024 * 1024,  # 5 MB
            backupCount=2,
            encoding="utf-8",
        )
        file_handler.setLevel(log_level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
    except Exception as err:
        print(f"[Warning] Failed to initialize log file at {log_file}: {err}", file=sys.stderr)

    _logging_initialized = True
    return log_file

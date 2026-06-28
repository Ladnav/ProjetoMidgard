"""Application logging configuration."""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOGGER_NAME = "midgard"


def configure_logging(log_directory: Path) -> Path:
    """Configure console and rotating-file logging and return the log path."""
    log_directory.mkdir(parents=True, exist_ok=True)
    log_path = log_directory / "midgard-studio.log"

    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    for handler in logger.handlers[:]:
        handler.close()
        logger.removeHandler(handler)

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    file_handler = RotatingFileHandler(
        log_path,
        maxBytes=1_000_000,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    return log_path


def get_logger(name: str) -> logging.Logger:
    """Return a child logger inside the Midgard logging namespace."""
    return logging.getLogger(f"{LOGGER_NAME}.{name}")

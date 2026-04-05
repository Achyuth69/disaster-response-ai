"""
agents/logger.py — Structured logging with structlog.
Provides consistent, machine-readable JSON logs for production
and human-readable colored logs for development.
"""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Any

try:
    import structlog
    _STRUCTLOG = True
except ImportError:
    _STRUCTLOG = False


def _ensure_log_dir() -> Path:
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    return log_dir


def get_logger(name: str = "disaster_response") -> Any:
    """Return a structured logger. Falls back to stdlib logging if structlog unavailable."""
    if not _STRUCTLOG:
        logger = logging.getLogger(name)
        if not logger.handlers:
            handler = logging.StreamHandler(sys.stdout)
            handler.setFormatter(logging.Formatter(
                "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
            ))
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
        return logger

    env = os.getenv("APP_ENV", "development")

    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]

    if env == "production":
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer(colors=True))

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    return structlog.get_logger(name)


# Module-level logger
log = get_logger("disaster_response")

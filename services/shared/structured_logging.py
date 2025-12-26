"""
Structured Logging Utilities

Provides utilities for structured logging with context throughout services.
"""

from __future__ import annotations

import logging
from typing import Any

# Configure structured logging format
STRUCTURED_FORMAT = "%(asctime)s [%(levelname)s] [%(name)s] [%(context)s] %(message)s"


class StructuredLoggerAdapter(logging.LoggerAdapter):
    """
    Logger adapter that adds structured context to log messages.

    Usage:
        logger = get_structured_logger(__name__, profile_id=123, job_id="abc")
        logger.info("Processing job")  # Logs with context
    """

    def __init__(self, logger: logging.Logger, **context: Any):
        """
        Initialize structured logger adapter.

        Args:
            logger: Base logger instance
            **context: Context fields to include in all log messages
        """
        super().__init__(logger, context)

    def process(self, msg: str, kwargs: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        """
        Process log message to add context.

        Args:
            msg: Log message
            kwargs: Logging keyword arguments

        Returns:
            Tuple of (formatted message, updated kwargs)
        """
        # Format context as key=value pairs
        context_parts = []
        for key, value in self.extra.items():
            if value is not None:
                context_parts.append(f"{key}={value}")

        context_str = " | ".join(context_parts) if context_parts else "none"

        # Add context to extra for formatter
        kwargs.setdefault("extra", {})["context"] = context_str

        return msg, kwargs


def get_structured_logger(name: str, **context: Any) -> StructuredLoggerAdapter:
    """
    Get a structured logger with context.

    Args:
        name: Logger name (typically __name__)
        **context: Context fields (e.g., profile_id=123, job_id="abc")

    Returns:
        StructuredLoggerAdapter instance
    """
    base_logger = logging.getLogger(name)
    return StructuredLoggerAdapter(base_logger, **context)


def log_with_context(logger: logging.Logger, level: int, msg: str, **context: Any) -> None:
    """
    Log a message with additional context fields.

    Convenience function for adding context to a single log message.

    Args:
        logger: Logger instance
        level: Log level (logging.INFO, logging.ERROR, etc.)
        msg: Log message
        **context: Additional context fields
    """
    # Format context
    context_parts = []
    for key, value in context.items():
        if value is not None:
            context_parts.append(f"{key}={value}")

    if context_parts:
        context_str = " | ".join(context_parts)
        full_msg = f"[{context_str}] {msg}"
    else:
        full_msg = msg

    logger.log(level, full_msg)

"""
Shared infrastructure for services.

This package contains shared building blocks used across multiple services,
such as database abstractions.
"""

from .database import Database, PostgreSQLDatabase, close_all_pools
from .metrics_recorder import MetricsRecorder

__all__ = [
    "Database",
    "PostgreSQLDatabase",
    "MetricsRecorder",
    "close_all_pools",
]

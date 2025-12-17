"""
Shared infrastructure for services.

This package contains shared building blocks used across multiple services,
such as database abstractions.
"""

from .database import Database, PostgreSQLDatabase

__all__ = [
    "Database",
    "PostgreSQLDatabase",
]



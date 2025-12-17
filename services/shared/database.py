"""Database abstraction layer for shared services."""

from typing import Protocol
from contextlib import contextmanager
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT


class Database(Protocol):
    """Protocol for database operations.
    
    This protocol defines the interface that database implementations must
    follow. It allows us to easily swap implementations (e.g., PostgreSQL,
    test mocks).
    """

    @contextmanager
    def get_cursor(self):
        """Get a database cursor as a context manager.
        
        Yields:
            A database cursor that can be used to execute queries.
            
        The connection is automatically closed when exiting the context.
        """
        ...


class PostgreSQLDatabase:
    """PostgreSQL implementation of Database protocol.
    
    This class provides a concrete implementation for PostgreSQL databases.
    It manages connection lifecycle and provides a clean cursor interface.
    """

    def __init__(self, connection_string: str):
        """Initialize PostgreSQL database connection.
        
        Args:
            connection_string: PostgreSQL connection string
                (e.g., "postgresql://user:password@host:port/dbname")
        
        Raises:
            ValueError: If connection_string is empty or None
        """
        if not connection_string:
            raise ValueError("Connection string is required")
        self.connection_string = connection_string

    @contextmanager
    def get_cursor(self):
        """Get a database cursor as a context manager.
        
        Creates a new connection, sets autocommit mode, and yields a cursor.
        The connection is automatically closed when exiting the context.
        
        Yields:
            A psycopg2 cursor for executing queries.
        
        Example:
            with db.get_cursor() as cur:
                cur.execute("SELECT * FROM table")
                results = cur.fetchall()
        """
        with psycopg2.connect(self.connection_string) as conn:
            conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
            with conn.cursor() as cur:
                yield cur



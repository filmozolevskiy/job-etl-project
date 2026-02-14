"""Database abstraction layer for shared services."""

import logging
import os
import threading
from contextlib import contextmanager
from typing import Protocol

import psycopg2
from psycopg2 import pool

logger = logging.getLogger(__name__)

# Module-level pool registry: connection_string -> ThreadedConnectionPool
# Shared across all PostgreSQLDatabase instances with the same connection string.
_pools: dict[str, pool.ThreadedConnectionPool] = {}
_pools_lock = threading.Lock()

# Default pool sizes; keep conservative to stay within DigitalOcean managed DB limits.
# DB_POOL_MIN_CONN: minimum connections per pool (default 1)
# DB_POOL_MAX_CONN: maximum connections per pool (default 5)
_DEFAULT_MIN_CONN = 1
_DEFAULT_MAX_CONN = 5


def _get_pool(connection_string: str) -> pool.ThreadedConnectionPool:
    """Get or create a ThreadedConnectionPool for the given connection string."""
    with _pools_lock:
        if connection_string not in _pools:
            minconn = int(os.getenv("DB_POOL_MIN_CONN", str(_DEFAULT_MIN_CONN)))
            maxconn = int(os.getenv("DB_POOL_MAX_CONN", str(_DEFAULT_MAX_CONN)))
            minconn = max(1, min(minconn, maxconn))
            maxconn = max(minconn, maxconn)
            _pools[connection_string] = pool.ThreadedConnectionPool(
                minconn, maxconn, connection_string
            )
            logger.debug(
                "Created connection pool for database (min=%s, max=%s)",
                minconn,
                maxconn,
            )
        return _pools[connection_string]


def close_all_pools() -> None:
    """Close all connection pools. Call on application shutdown for graceful cleanup."""
    with _pools_lock:
        for conn_str, p in list(_pools.items()):
            try:
                p.closeall()
            except Exception as e:  # noqa: BLE001
                logger.warning("Error closing pool for %s: %s", conn_str[:50], e)
        _pools.clear()


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
    """PostgreSQL implementation of Database protocol with connection pooling.

    Uses a shared ThreadedConnectionPool per connection string. Connections
    are reused instead of created per request, preventing "remaining connection
    slots are reserved" errors on managed databases (e.g., DigitalOcean).
    """

    def __init__(self, connection_string: str):
        """Initialize PostgreSQL database with connection pooling.

        Args:
            connection_string: PostgreSQL connection string
                (e.g., "postgresql://user:password@host:port/dbname")

        Raises:
            ValueError: If connection_string is empty or None
        """
        if not connection_string:
            raise ValueError("Connection string is required")
        self.connection_string = connection_string
        self._pool = _get_pool(connection_string)

    @contextmanager
    def get_cursor(self):
        """Get a database cursor as a context manager.

        Borrows a connection from the pool, sets autocommit mode, and yields
        a cursor. The connection is returned to the pool when exiting the context.
        If the connection is dead, it attempts to get a new one.

        Yields:
            A psycopg2 cursor for executing queries.

        Example:
            with db.get_cursor() as cur:
                cur.execute("SELECT * FROM table")
                results = cur.fetchall()
        """
        conn = None
        try:
            conn = self._pool.getconn()

            # Check if connection is still alive
            try:
                with conn.cursor() as check_cur:
                    check_cur.execute("SELECT 1")
            except (psycopg2.OperationalError, psycopg2.InterfaceError):
                # Connection is dead, try to get a new one
                logger.warning("Pooled connection is dead, attempting to get a new one")
                try:
                    self._pool.putconn(conn, close=True)
                except Exception:
                    pass
                conn = self._pool.getconn()

            # Ensure autocommit is set for the connection
            # Only set if not already set to avoid ProgrammingError in some environments
            if not conn.autocommit:
                try:
                    conn.autocommit = True
                except psycopg2.ProgrammingError as e:
                    if "inside a transaction" in str(e):
                        # If we're inside a transaction, we can't set autocommit.
                        # This shouldn't happen with getconn() unless the pool
                        # returned a connection in a weird state.
                        logger.warning("Could not set autocommit: %s", e)
                    else:
                        raise

            with conn.cursor() as cur:
                yield cur
        except Exception as e:
            logger.error("Database error in get_cursor: %s", e)
            raise
        finally:
            if conn:
                try:
                    # Always rollback to ensure no dangling transactions
                    # (though autocommit=True should prevent this)
                    conn.rollback()
                except Exception:  # noqa: BLE001
                    pass
                self._pool.putconn(conn)

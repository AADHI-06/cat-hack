"""Shared FastAPI dependencies."""

import sqlite3
from collections.abc import Iterator

from app.services.database import connect


def get_db() -> Iterator[sqlite3.Connection]:
    """One SQLite connection per request."""
    conn = connect()
    try:
        yield conn
    finally:
        conn.close()

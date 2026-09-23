"""
SQLite connection handling.

The database file defaults to backend/cat_hack.db (ignored by git via *.db).
Set CAT_DB_PATH to use a different file.
"""

import os
import sqlite3
from pathlib import Path

from app.services.database.schema import SCHEMA_SQL

BACKEND_DIR = Path(__file__).resolve().parents[3]
REPO_ROOT = BACKEND_DIR.parent

DEFAULT_DB_PATH = BACKEND_DIR / "cat_hack.db"


def get_db_path() -> Path:
    return Path(os.environ.get("CAT_DB_PATH", DEFAULT_DB_PATH))


def connect(db_path: str | Path | None = None) -> sqlite3.Connection:
    """
    Open a connection with foreign keys enforced and the schema in place.

    Creating the schema is idempotent, so an empty database is always
    queryable (it just returns no rows).
    """
    conn = sqlite3.connect(db_path or get_db_path(), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA_SQL)
    return conn

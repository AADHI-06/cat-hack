"""
Platform persistence layer (Claude B).

SQLite storage for the Module 1 operational datasets. Column names, order and
meaning come from docs/synthetic_data.md (Claude A owns the data semantics).
This package stores and reads that data; it contains no ML or safety logic.
"""

from app.services.database.connection import connect, get_db_path

__all__ = ["connect", "get_db_path"]

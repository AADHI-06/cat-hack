"""
Load Claude A's generated CSVs (data/generated/) into SQLite.

This only copies existing synthetic data into the database. It does not
generate data - run Claude A's generator first:

    python -m scripts.data_generation.generate          # from the repo root

Then, from backend/:

    python -m app.services.database.loader
    python -m app.services.database.loader --data ../data/generated --db cat_hack.db

Loading replaces the contents of all six tables, so it is safe to re-run.
"""

import argparse
import csv
import sqlite3
from pathlib import Path

from app.services.database.connection import REPO_ROOT, connect, get_db_path
from app.services.database.schema import TABLE_ORDER

DEFAULT_DATA_DIR = REPO_ROOT / "data" / "generated"

# Module 1 ingestion rules (docs/synthetic_data.md). These are stricter than
# the database schema on purpose: the schema also has to hold records that
# later modules create, while CSVs from the generator must be exactly this.
SYNTHETIC_MARKER = "synthetic"
NULLABLE_CSV_COLUMNS = {
    ("tasks", "depends_on_task_id"),
    ("telemetry", "injected_anomaly_type"),
}


class LoaderError(Exception):
    """Raised when a CSV does not match the documented schema."""


def table_columns(conn: sqlite3.Connection, table: str) -> list[tuple[str, str]]:
    """(column name, declared type) in schema order."""
    return [(row["name"], row["type"]) for row in conn.execute(f"PRAGMA table_info({table})")]


def _convert(value: str, sql_type: str):
    # The CSVs write the two nullable columns as empty strings.
    if value == "":
        return None
    if sql_type == "INTEGER":
        return int(value)
    if sql_type == "REAL":
        return float(value)
    return value


def _check_module1_row(table: str, record: dict, where: str) -> None:
    if record["data_source"] != SYNTHETIC_MARKER:
        raise LoaderError(
            f"{where}: data_source is {record['data_source']!r}, expected {SYNTHETIC_MARKER!r}. "
            "Only synthetic Module 1 data may be loaded from CSV."
        )
    for column, value in record.items():
        if value == "" and (table, column) not in NULLABLE_CSV_COLUMNS:
            raise LoaderError(f"{where}: {column} is blank but is not a nullable Module 1 column")


def _read_rows(path: Path, table: str, columns: list[tuple[str, str]]) -> list[tuple]:
    expected = [name for name, _ in columns]
    with open(path, newline="", encoding="utf-8") as handle:
        reader = csv.reader(handle)
        header = next(reader, None)
        if header != expected:
            raise LoaderError(f"{path.name}: columns {header} do not match schema {expected}")

        rows = []
        for line_no, values in enumerate(reader, start=2):
            if len(values) != len(columns):
                raise LoaderError(f"{path.name} line {line_no}: expected {len(columns)} values")
            _check_module1_row(table, dict(zip(expected, values)), f"{path.name} line {line_no}")
            try:
                rows.append(tuple(_convert(v, t) for v, (_, t) in zip(values, columns)))
            except ValueError as exc:
                raise LoaderError(f"{path.name} line {line_no}: {exc}") from exc
        return rows


def load_generated_data(conn: sqlite3.Connection, data_dir: str | Path = DEFAULT_DATA_DIR) -> dict[str, int]:
    """
    Replace all six operational tables with the CSVs in data_dir.

    Runs in one transaction: either every table loads, or nothing changes.
    Returns the row count loaded per table.
    """
    data_dir = Path(data_dir)
    missing = [t for t in TABLE_ORDER if not (data_dir / f"{t}.csv").is_file()]
    if missing:
        raise LoaderError(
            f"Missing CSVs in {data_dir}: {', '.join(f'{t}.csv' for t in missing)}. "
            "Run Claude A's generator first: python -m scripts.data_generation.generate"
        )

    counts = {}
    try:
        with conn:
            for table in reversed(TABLE_ORDER):
                conn.execute(f"DELETE FROM {table}")
            for table in TABLE_ORDER:
                columns = table_columns(conn, table)
                rows = _read_rows(data_dir / f"{table}.csv", table, columns)
                placeholders = ", ".join("?" for _ in columns)
                try:
                    conn.executemany(f"INSERT INTO {table} VALUES ({placeholders})", rows)
                except sqlite3.IntegrityError as exc:
                    raise LoaderError(f"{table}.csv rejected by the schema: {exc}") from exc
                counts[table] = len(rows)
    except sqlite3.IntegrityError as exc:
        # Deferred checks (tasks.depends_on_task_id) fail at commit time.
        raise LoaderError(f"Load rejected by the schema: {exc}") from exc
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description="Load synthetic CSVs into the platform SQLite database.")
    parser.add_argument("--data", default=str(DEFAULT_DATA_DIR), help="directory with the generated CSVs")
    parser.add_argument("--db", default=None, help="SQLite file (default: CAT_DB_PATH or backend/cat_hack.db)")
    args = parser.parse_args()

    db_path = args.db or get_db_path()
    conn = connect(db_path)
    try:
        counts = load_generated_data(conn, args.data)
    finally:
        conn.close()

    print(f"Loaded SYNTHETIC data (not real Caterpillar data) into {db_path}")
    for table, count in counts.items():
        print(f"  {table:15s} {count:6d} rows")


if __name__ == "__main__":
    main()

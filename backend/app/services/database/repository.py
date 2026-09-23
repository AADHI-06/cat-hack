"""
Read queries for the operational tables.

Plain SQL over sqlite3. Functions return dicts; the API layer turns them into
response models. Filter column names come from this module only - never from
the request - and all filter values are bound parameters.

No derived intelligence lives here: counting and filtering only. Predictions,
optimization, safety rules and anomaly scores belong to Claude A's services.
"""

import sqlite3


def _where(filters: dict) -> tuple[str, list]:
    active = {column: value for column, value in filters.items() if value is not None}
    if not active:
        return "", []
    clause = " AND ".join(f"{column} = ?" for column in active)
    return f" WHERE {clause}", list(active.values())


def _select(
    conn: sqlite3.Connection,
    table: str,
    order_by: str,
    filters: dict | None = None,
    limit: int | None = None,
    offset: int = 0,
) -> list[dict]:
    where, params = _where(filters or {})
    sql = f"SELECT * FROM {table}{where} ORDER BY {order_by}"
    if limit is not None:
        sql += " LIMIT ? OFFSET ?"
        params += [limit, offset]
    return [dict(row) for row in conn.execute(sql, params)]


def _get(conn: sqlite3.Connection, table: str, key: str, value: str) -> dict | None:
    row = conn.execute(f"SELECT * FROM {table} WHERE {key} = ?", (value,)).fetchone()
    return dict(row) if row else None


def count_by(conn: sqlite3.Connection, table: str, column: str, filters: dict | None = None) -> dict[str, int]:
    """Row counts grouped by one column, e.g. safety events per severity."""
    where, params = _where(filters or {})
    sql = f"SELECT {column} AS k, COUNT(*) AS n FROM {table}{where} GROUP BY {column} ORDER BY {column}"
    return {row["k"]: row["n"] for row in conn.execute(sql, params)}


def table_counts(conn: sqlite3.Connection, tables: list[str]) -> dict[str, int]:
    return {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in tables}


# --- operators --------------------------------------------------------------

def list_operators(conn, skill_level=None, primary_shift=None) -> list[dict]:
    return _select(conn, "operators", "operator_id",
                   {"skill_level": skill_level, "primary_shift": primary_shift})


def get_operator(conn, operator_id: str) -> dict | None:
    return _get(conn, "operators", "operator_id", operator_id)


# --- machines ---------------------------------------------------------------

def list_machines(conn, machine_type=None, home_zone=None) -> list[dict]:
    return _select(conn, "machines", "machine_id",
                   {"machine_type": machine_type, "home_zone": home_zone})


def get_machine(conn, machine_id: str) -> dict | None:
    return _get(conn, "machines", "machine_id", machine_id)


# --- tasks (pending backlog) ------------------------------------------------

def list_tasks(conn, status=None, priority=None, site_zone=None,
               required_machine_type=None, shift_date=None) -> list[dict]:
    return _select(conn, "tasks", "shift_date, task_id", {
        "status": status,
        "priority": priority,
        "site_zone": site_zone,
        "required_machine_type": required_machine_type,
        "shift_date": shift_date,
    })


def get_task(conn, task_id: str) -> dict | None:
    return _get(conn, "tasks", "task_id", task_id)


# --- task history (completed executions) ------------------------------------

def list_task_history(conn, operator_id=None, machine_id=None, limit=50, offset=0) -> list[dict]:
    return _select(conn, "task_history", "started_at DESC, history_id DESC",
                   {"operator_id": operator_id, "machine_id": machine_id}, limit, offset)


# --- telemetry --------------------------------------------------------------

def list_telemetry(conn, machine_id=None, operator_id=None, limit=50, offset=0) -> list[dict]:
    return _select(conn, "telemetry", "recorded_at DESC, telemetry_id DESC",
                   {"machine_id": machine_id, "operator_id": operator_id}, limit, offset)


# --- safety events ----------------------------------------------------------

def list_safety_events(conn, operator_id=None, machine_id=None, severity=None,
                       event_type=None, limit=50, offset=0) -> list[dict]:
    return _select(conn, "safety_events", "timestamp DESC, event_id DESC", {
        "operator_id": operator_id,
        "machine_id": machine_id,
        "severity": severity,
        "event_type": event_type,
    }, limit, offset)

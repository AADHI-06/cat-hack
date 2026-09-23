"""Platform persistence layer: schema, loader, relationships, synthetic marker."""

import copy
import sqlite3

import pytest

from app.services.database import connect, repository
from app.services.database.loader import LoaderError, load_generated_data, table_columns
from app.services.database.schema import TABLE_ORDER
from tests.conftest import DOCUMENTED_COLUMNS, SAMPLE_ROWS, write_csvs


def _load(tmp_path, rows):
    data_dir = tmp_path / "csv"
    data_dir.mkdir()
    write_csvs(data_dir, rows)
    conn = connect(tmp_path / "db.sqlite")
    return conn, data_dir


def test_database_initializes_with_all_tables(db_path):
    conn = connect(db_path)
    tables = {r["name"] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert set(TABLE_ORDER) <= tables
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    conn.close()


def test_incident_and_training_tables_not_defined_yet(db_path):
    """Incident contract is open (Module 6); training is Module 7."""
    conn = connect(db_path)
    tables = {r["name"] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert not tables & {"incidents", "training_modules", "training_progress"}
    conn.close()


@pytest.mark.parametrize("table", TABLE_ORDER)
def test_schema_matches_documented_columns(db_path, table):
    conn = connect(db_path)
    assert [name for name, _ in table_columns(conn, table)] == DOCUMENTED_COLUMNS[table]
    conn.close()


def test_connect_is_idempotent(loaded_db):
    """Re-opening an existing database keeps its data."""
    conn = connect(loaded_db)
    assert repository.table_counts(conn, TABLE_ORDER)["operators"] == 3
    conn.close()


def test_loader_loads_every_table(loaded_db):
    conn = connect(loaded_db)
    counts = repository.table_counts(conn, TABLE_ORDER)
    assert counts == {t: len(SAMPLE_ROWS[t]) for t in TABLE_ORDER}
    conn.close()


def test_loader_is_rerunnable(tmp_path):
    conn, data_dir = _load(tmp_path, SAMPLE_ROWS)
    load_generated_data(conn, data_dir)
    counts = load_generated_data(conn, data_dir)
    assert counts["tasks"] == 3
    assert repository.table_counts(conn, ["tasks"])["tasks"] == 3
    conn.close()


def test_loader_converts_types_and_nulls(loaded_db):
    conn = connect(loaded_db)
    t001 = repository.get_task(conn, "T001")
    assert t001["depends_on_task_id"] is None
    assert isinstance(t001["difficulty"], int)
    assert repository.get_task(conn, "T002")["depends_on_task_id"] == "T001"

    machine = repository.get_machine(conn, "M001")
    assert isinstance(machine["engine_hours"], float)

    normal, injected = repository.list_telemetry(conn, limit=10)[::-1]
    assert normal["injected_anomaly_type"] is None
    assert injected["injected_anomaly_type"] == "EXCESSIVE_IDLING"
    conn.close()


def test_every_row_keeps_synthetic_marker(loaded_db):
    conn = connect(loaded_db)
    for table in TABLE_ORDER:
        values = {r[0] for r in conn.execute(f"SELECT DISTINCT data_source FROM {table}")}
        assert values == {"synthetic"}, table
    conn.close()


@pytest.mark.parametrize("table", TABLE_ORDER)
def test_loader_rejects_non_synthetic_rows(tmp_path, table):
    rows = copy.deepcopy(SAMPLE_ROWS)
    rows[table][-1][-1] = "real"
    conn, data_dir = _load(tmp_path, rows)
    with pytest.raises(LoaderError, match=f"{table}.csv line .*expected 'synthetic'"):
        load_generated_data(conn, data_dir)
    assert repository.table_counts(conn, TABLE_ORDER) == {t: 0 for t in TABLE_ORDER}
    conn.close()


def test_failed_load_changes_nothing(tmp_path):
    conn, data_dir = _load(tmp_path, SAMPLE_ROWS)
    load_generated_data(conn, data_dir)

    rows = copy.deepcopy(SAMPLE_ROWS)
    rows["safety_events"][0][2] = "OP999"
    write_csvs(data_dir, rows)
    with pytest.raises(LoaderError):
        load_generated_data(conn, data_dir)
    assert repository.table_counts(conn, TABLE_ORDER)["safety_events"] == 3
    conn.close()


@pytest.mark.parametrize("table, index, bad_value", [
    ("task_history", 2, "OP999"),        # operator_id -> operators
    ("task_history", 3, "M999"),         # machine_id -> machines
    ("telemetry", 1, "TH99999"),         # history_id -> task_history
    ("safety_events", 4, "T9999"),       # task_id -> task_history
    ("tasks", 9, "T999"),                # depends_on_task_id -> tasks
])
def test_invalid_foreign_keys_are_rejected(tmp_path, table, index, bad_value):
    rows = copy.deepcopy(SAMPLE_ROWS)
    rows[table][-1][index] = bad_value
    conn, data_dir = _load(tmp_path, rows)
    with pytest.raises(LoaderError):
        load_generated_data(conn, data_dir)
    conn.close()


def test_task_cannot_depend_on_itself(tmp_path):
    rows = copy.deepcopy(SAMPLE_ROWS)
    rows["tasks"][0][9] = "T001"
    conn, data_dir = _load(tmp_path, rows)
    with pytest.raises(LoaderError):
        load_generated_data(conn, data_dir)
    conn.close()


def test_history_task_ids_do_not_reference_backlog(loaded_db):
    """task_history.task_id (T1001...) is a separate range from pending tasks (T001...)."""
    conn = connect(loaded_db)
    history_ids = {r["task_id"] for r in repository.list_task_history(conn)}
    assert all(repository.get_task(conn, t) is None for t in history_ids)
    conn.close()


def test_blank_in_required_column_is_rejected(tmp_path):
    rows = copy.deepcopy(SAMPLE_ROWS)
    rows["machines"][0][2] = ""
    conn, data_dir = _load(tmp_path, rows)
    with pytest.raises(LoaderError):
        load_generated_data(conn, data_dir)
    conn.close()


def test_wrong_header_is_rejected(tmp_path):
    conn, data_dir = _load(tmp_path, SAMPLE_ROWS)
    path = data_dir / "operators.csv"
    path.write_text(path.read_text().replace("data_source", "is_synthetic", 1))
    with pytest.raises(LoaderError, match="do not match schema"):
        load_generated_data(conn, data_dir)
    conn.close()


def test_bad_number_is_rejected(tmp_path):
    rows = copy.deepcopy(SAMPLE_ROWS)
    rows["operators"][0][3] = "fifteen"
    conn, data_dir = _load(tmp_path, rows)
    with pytest.raises(LoaderError, match="line 2"):
        load_generated_data(conn, data_dir)
    conn.close()


def test_missing_csv_names_the_generator(tmp_path):
    conn = connect(tmp_path / "db.sqlite")
    with pytest.raises(LoaderError, match="scripts.data_generation.generate"):
        load_generated_data(conn, tmp_path)
    conn.close()


def test_repository_filters_and_counts(loaded_db):
    conn = connect(loaded_db)
    assert [t["task_id"] for t in repository.list_tasks(conn, status="PENDING")] == ["T001", "T003"]
    assert [o["operator_id"] for o in repository.list_operators(conn, primary_shift="NIGHT")] == ["OP002"]
    assert repository.count_by(conn, "safety_events", "severity") == {"HIGH": 2, "LOW": 1}
    assert repository.count_by(conn, "safety_events", "severity", {"operator_id": "OP001"}) == {}
    assert len(repository.list_safety_events(conn, limit=2)) == 2
    conn.close()


# --- general persistence vs. Module 1 CSV ingestion -------------------------

def test_schema_allows_application_records_that_are_not_synthetic(loaded_db):
    """Later modules may store live/application records; only the CSV loader demands 'synthetic'."""
    conn = connect(loaded_db)
    conn.execute("INSERT INTO operators VALUES ('OP009', 'X', 'EXPERT', 3, 'DOZER_OP', 'DAY', 'live')")
    assert repository.get_operator(conn, "OP009")["data_source"] == "live"
    conn.close()


def test_schema_still_requires_a_data_source(loaded_db):
    conn = connect(loaded_db)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO operators VALUES ('OP009', 'X', 'EXPERT', 3, 'DOZER_OP', 'DAY', NULL)")
    conn.close()


def _insert_event(conn, task_id, history_id):
    conn.execute(
        "INSERT INTO safety_events VALUES ('SE9001', '2026-09-23T09:00:00', 'OP001', 'M001', ?, ?, "
        "'SEATBELT', 'HIGH', 'Seatbelt violation detected', 'live')",
        (task_id, history_id),
    )


def test_safety_event_may_have_no_task_or_history(loaded_db):
    """The Safety Event contract does not require task_id/history_id."""
    conn = connect(loaded_db)
    _insert_event(conn, None, None)
    event = repository.list_safety_events(conn, operator_id="OP001")[0]
    assert event["task_id"] is None and event["history_id"] is None
    conn.close()


def test_safety_event_links_still_enforced_when_present(loaded_db):
    conn = connect(loaded_db)
    with pytest.raises(sqlite3.IntegrityError):
        _insert_event(conn, None, "TH99999")
    with pytest.raises(sqlite3.IntegrityError):
        _insert_event(conn, "T9999", None)
    conn.close()


@pytest.mark.parametrize("table, index", [
    ("safety_events", 4),   # task_id: nullable in the schema, required in Module 1 CSVs
    ("safety_events", 5),   # history_id
    ("telemetry", 1),       # history_id
])
def test_loader_rejects_blanks_outside_documented_nullable_columns(tmp_path, table, index):
    rows = copy.deepcopy(SAMPLE_ROWS)
    rows[table][0][index] = ""
    conn, data_dir = _load(tmp_path, rows)
    with pytest.raises(LoaderError, match="not a nullable Module 1 column"):
        load_generated_data(conn, data_dir)
    conn.close()

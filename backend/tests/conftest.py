"""
Shared fixtures for the platform tests.

A tiny hand-written dataset in exactly the CSV format documented in
docs/synthetic_data.md, so tests never depend on Claude A's generated files.
"""

import csv

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_db
from app.main import app
from app.services.database import connect
from app.services.database.loader import load_generated_data

# Column order per docs/synthetic_data.md section 3 (and the generator).
DOCUMENTED_COLUMNS = {
    "operators": [
        "operator_id", "name", "skill_level", "experience_years",
        "certifications", "primary_shift", "data_source",
    ],
    "machines": [
        "machine_id", "machine_type", "model", "year_manufactured", "age_years",
        "engine_hours", "condition_rating", "capacity_units", "home_zone",
        "data_source",
    ],
    "tasks": [
        "task_id", "task_type", "difficulty", "quantity", "quantity_unit",
        "required_machine_type", "required_certification", "priority",
        "business_value", "depends_on_task_id", "site_zone", "terrain",
        "estimated_minutes", "status", "shift_date", "data_source",
    ],
    "task_history": [
        "history_id", "task_id", "operator_id", "machine_id", "task_type",
        "difficulty", "quantity", "quantity_unit", "required_machine_type",
        "terrain", "priority", "business_value", "shift", "shift_date",
        "started_at", "completed_at", "temperature", "rainfall", "humidity",
        "wind_speed", "visibility", "weather", "estimated_minutes",
        "actual_minutes", "data_source",
    ],
    "telemetry": [
        "telemetry_id", "history_id", "task_id", "machine_id", "operator_id",
        "recorded_at", "engine_hours_reading", "runtime_minutes",
        "idle_minutes", "idle_ratio", "fuel_used_liters", "fuel_per_unit",
        "load_cycles", "avg_load_pct", "load_variance", "engine_temp_c",
        "hydraulic_pressure_psi", "max_speed_kph", "seatbelt_fastened_pct",
        "min_proximity_m", "proximity_alerts_count", "injected_anomaly_type",
        "data_source",
    ],
    "safety_events": [
        "event_id", "timestamp", "operator_id", "machine_id", "task_id",
        "history_id", "event_type", "severity", "description", "data_source",
    ],
}

S = "synthetic"

SAMPLE_ROWS = {
    "operators": [
        ["OP001", "Test Operator A", "EXPERT", "15", "EXCAVATOR_OP|DOZER_OP", "DAY", S],
        ["OP002", "Test Operator B", "BEGINNER", "1", "LOADER_OP", "NIGHT", S],
        ["OP003", "Test Operator C", "INTERMEDIATE", "6", "HAUL_TRUCK_OP", "DAY", S],
    ],
    "machines": [
        ["M001", "EXCAVATOR", "CAT 320", "2018", "8", "5120.5", "0.78", "1.5", "ZONE_A", S],
        ["M002", "LOADER", "CAT 950", "2022", "4", "2011.0", "0.9", "3.2", "ZONE_B", S],
    ],
    "tasks": [
        ["T001", "EXCAVATION", "3", "80", "m3", "EXCAVATOR", "EXCAVATOR_OP", "HIGH",
         "900", "", "ZONE_A", "FLAT", "190", "PENDING", "2026-09-24", S],
        ["T002", "TRENCHING", "2", "40", "m", "EXCAVATOR", "EXCAVATOR_OP", "MEDIUM",
         "500", "T001", "ZONE_A", "SLOPED", "130", "BLOCKED", "2026-09-24", S],
        ["T003", "LOADING", "1", "60", "loads", "LOADER", "LOADER_OP", "LOW",
         "300", "", "ZONE_B", "ROUGH", "85", "PENDING", "2026-09-25", S],
    ],
    "task_history": [
        ["TH00001", "T1001", "OP001", "M001", "EXCAVATION", "3", "80", "m3", "EXCAVATOR",
         "FLAT", "HIGH", "900", "DAY", "2026-09-20", "2026-09-20T07:00:00",
         "2026-09-20T10:10:00", "24.0", "0.0", "55.0", "8.0", "9.5", "CLEAR", "180", "190.0", S],
        ["TH00002", "T1002", "OP002", "M002", "LOADING", "2", "90", "loads", "LOADER",
         "ROUGH", "MEDIUM", "450", "NIGHT", "2026-09-21", "2026-09-21T19:00:00",
         "2026-09-21T21:30:00", "18.5", "6.2", "80.0", "12.0", "4.1", "RAIN", "125", "150.0", S],
    ],
    "telemetry": [
        ["TM00001", "TH00001", "T1001", "M001", "OP001", "2026-09-20T10:10:00", "5117.3",
         "190.0", "20.0", "0.105", "60.0", "0.75", "80", "72.0", "8.0", "88.0", "3000.0",
         "18.0", "100.0", "6.0", "0", "", S],
        ["TM00002", "TH00002", "T1002", "M002", "OP002", "2026-09-21T21:30:00", "2009.5",
         "150.0", "75.0", "0.5", "55.0", "0.61", "90", "65.0", "9.0", "90.0", "2800.0",
         "31.0", "60.0", "1.2", "4", "EXCESSIVE_IDLING", S],
    ],
    "safety_events": [
        ["SE0001", "2026-09-21T21:30:00", "OP002", "M002", "T1002", "TH00002", "SEATBELT",
         "HIGH", "Seatbelt violation detected", S],
        ["SE0002", "2026-09-21T21:30:00", "OP002", "M002", "T1002", "TH00002", "PROXIMITY",
         "HIGH", "Potential proximity hazard detected", S],
        ["SE0003", "2026-09-21T21:30:00", "OP002", "M002", "T1002", "TH00002", "EXCESSIVE_IDLING",
         "LOW", "Excessive idling detected", S],
    ],
}


def write_csvs(directory, rows=None):
    """Write the sample dataset (or an override) as generator-style CSVs."""
    rows = rows or SAMPLE_ROWS
    for table, columns in DOCUMENTED_COLUMNS.items():
        with open(directory / f"{table}.csv", "w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle, lineterminator="\n")
            writer.writerow(columns)
            writer.writerows(rows[table])
    return directory


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "test.db"


@pytest.fixture
def loaded_db(tmp_path, db_path):
    """Path to a database loaded with the sample dataset."""
    data_dir = tmp_path / "generated"
    data_dir.mkdir()
    write_csvs(data_dir)
    conn = connect(db_path)
    load_generated_data(conn, data_dir)
    conn.close()
    return db_path


def _client_for(path):
    def override():
        conn = connect(path)
        try:
            yield conn
        finally:
            conn.close()

    app.dependency_overrides[get_db] = override
    return TestClient(app)


@pytest.fixture
def client(loaded_db):
    yield _client_for(loaded_db)
    app.dependency_overrides.clear()


@pytest.fixture
def empty_client(db_path):
    yield _client_for(db_path)
    app.dependency_overrides.clear()

"""
SQLite schema for the Module 1 operational tables.

Source of truth for columns: docs/synthetic_data.md section 3. Columns appear
in the same order as the generated CSVs so the loader can check headers
directly against this schema.

Not defined here (on purpose):
- incidents          -> contract still open, agreed in Module 6
- training_modules   -> Module 7
- training_progress  -> Module 7

Key relationships (docs/synthetic_data.md section 3):
- tasks.depends_on_task_id -> tasks.task_id, NULL when there is no dependency
- task_history.task_id is a separate id range (T1001-T4000) from the pending
  backlog (T001-T200), so it does NOT reference tasks
- telemetry / safety_events reference task_history (history_id and task_id)

safety_events.task_id / history_id are nullable here: the Safety Event
contract (docs/contracts.md 3) does not require them, so a future live event
need not belong to a completed execution. When present they must resolve.
"""

# Every row records where it came from. Module 1 rows are 'synthetic' (the
# loader enforces that for CSV ingestion); the schema itself only requires a
# value, so later modules can store application/live records too.
_DATA_SOURCE = "data_source TEXT NOT NULL"

SCHEMA_SQL = f"""
CREATE TABLE IF NOT EXISTS operators (
    operator_id       TEXT PRIMARY KEY,
    name              TEXT NOT NULL,
    skill_level       TEXT NOT NULL,
    experience_years  INTEGER NOT NULL,
    certifications    TEXT NOT NULL,
    primary_shift     TEXT NOT NULL,
    {_DATA_SOURCE}
);

CREATE TABLE IF NOT EXISTS machines (
    machine_id         TEXT PRIMARY KEY,
    machine_type       TEXT NOT NULL,
    model              TEXT NOT NULL,
    year_manufactured  INTEGER NOT NULL,
    age_years          INTEGER NOT NULL,
    engine_hours       REAL NOT NULL,
    condition_rating   REAL NOT NULL,
    capacity_units     REAL NOT NULL,
    home_zone          TEXT NOT NULL,
    {_DATA_SOURCE}
);

CREATE TABLE IF NOT EXISTS tasks (
    task_id                 TEXT PRIMARY KEY,
    task_type               TEXT NOT NULL,
    difficulty              INTEGER NOT NULL,
    quantity                INTEGER NOT NULL,
    quantity_unit           TEXT NOT NULL,
    required_machine_type   TEXT NOT NULL,
    required_certification  TEXT NOT NULL,
    priority                TEXT NOT NULL,
    business_value          INTEGER NOT NULL,
    depends_on_task_id      TEXT REFERENCES tasks (task_id)
                                 DEFERRABLE INITIALLY DEFERRED,
    site_zone               TEXT NOT NULL,
    terrain                 TEXT NOT NULL,
    estimated_minutes       INTEGER NOT NULL,
    status                  TEXT NOT NULL,
    shift_date              TEXT NOT NULL,
    {_DATA_SOURCE},
    CHECK (depends_on_task_id IS NULL OR depends_on_task_id <> task_id)
);

CREATE TABLE IF NOT EXISTS task_history (
    history_id             TEXT PRIMARY KEY,
    task_id                TEXT NOT NULL UNIQUE,
    operator_id            TEXT NOT NULL REFERENCES operators (operator_id),
    machine_id             TEXT NOT NULL REFERENCES machines (machine_id),
    task_type              TEXT NOT NULL,
    difficulty             INTEGER NOT NULL,
    quantity               INTEGER NOT NULL,
    quantity_unit          TEXT NOT NULL,
    required_machine_type  TEXT NOT NULL,
    terrain                TEXT NOT NULL,
    priority               TEXT NOT NULL,
    business_value         INTEGER NOT NULL,
    shift                  TEXT NOT NULL,
    shift_date             TEXT NOT NULL,
    started_at             TEXT NOT NULL,
    completed_at           TEXT NOT NULL,
    temperature            REAL NOT NULL,
    rainfall               REAL NOT NULL,
    humidity               REAL NOT NULL,
    wind_speed             REAL NOT NULL,
    visibility             REAL NOT NULL,
    weather                TEXT NOT NULL,
    estimated_minutes      INTEGER NOT NULL,
    actual_minutes         REAL NOT NULL,
    {_DATA_SOURCE}
);

CREATE TABLE IF NOT EXISTS telemetry (
    telemetry_id            TEXT PRIMARY KEY,
    history_id              TEXT NOT NULL UNIQUE
                                 REFERENCES task_history (history_id),
    task_id                 TEXT NOT NULL REFERENCES task_history (task_id),
    machine_id              TEXT NOT NULL REFERENCES machines (machine_id),
    operator_id             TEXT NOT NULL REFERENCES operators (operator_id),
    recorded_at             TEXT NOT NULL,
    engine_hours_reading    REAL NOT NULL,
    runtime_minutes         REAL NOT NULL,
    idle_minutes            REAL NOT NULL,
    idle_ratio              REAL NOT NULL,
    fuel_used_liters        REAL NOT NULL,
    fuel_per_unit           REAL NOT NULL,
    load_cycles             INTEGER NOT NULL,
    avg_load_pct            REAL NOT NULL,
    load_variance           REAL NOT NULL,
    engine_temp_c           REAL NOT NULL,
    hydraulic_pressure_psi  REAL NOT NULL,
    max_speed_kph           REAL NOT NULL,
    seatbelt_fastened_pct   REAL NOT NULL,
    min_proximity_m         REAL NOT NULL,
    proximity_alerts_count  INTEGER NOT NULL,
    injected_anomaly_type   TEXT,
    {_DATA_SOURCE}
);

CREATE TABLE IF NOT EXISTS safety_events (
    event_id     TEXT PRIMARY KEY,
    timestamp    TEXT NOT NULL,
    operator_id  TEXT NOT NULL REFERENCES operators (operator_id),
    machine_id   TEXT NOT NULL REFERENCES machines (machine_id),
    task_id      TEXT REFERENCES task_history (task_id),
    history_id   TEXT REFERENCES task_history (history_id),
    event_type   TEXT NOT NULL,
    severity     TEXT NOT NULL,
    description  TEXT NOT NULL,
    {_DATA_SOURCE}
);

CREATE INDEX IF NOT EXISTS ix_task_history_operator ON task_history (operator_id);
CREATE INDEX IF NOT EXISTS ix_task_history_machine  ON task_history (machine_id);
CREATE INDEX IF NOT EXISTS ix_telemetry_machine     ON telemetry (machine_id);
CREATE INDEX IF NOT EXISTS ix_safety_operator       ON safety_events (operator_id);
CREATE INDEX IF NOT EXISTS ix_safety_machine        ON safety_events (machine_id);
"""

# Load order: every table appears after the tables it references.
TABLE_ORDER = [
    "operators",
    "machines",
    "tasks",
    "task_history",
    "telemetry",
    "safety_events",
]

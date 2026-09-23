"""
Module 1 tests: synthetic data generation.

Generates into a temporary directory so the tests never depend on, or
overwrite, the checked-in output in data/generated.

Run from the repository root:
    python -m pytest scripts/data_generation/tests -v
"""

from __future__ import annotations

import csv
import json
from datetime import datetime

import pytest

from scripts.data_generation import config as C
from scripts.data_generation.generate import COLUMNS, generate_all
from scripts.data_generation.validate import validate


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def generated(tmp_path_factory):
    """Generate the full dataset once with the canonical seed."""
    out = tmp_path_factory.mktemp("seed42")
    manifest = generate_all(str(out), C.SEED)
    return str(out), manifest


@pytest.fixture(scope="module")
def data(generated):
    out, _ = generated
    tables = {}
    for name in C.DATASETS:
        with open(f"{out}/{name}.csv", newline="", encoding="utf-8") as handle:
            tables[name] = list(csv.DictReader(handle))
    return tables


# ---------------------------------------------------------------------------
# 1. files are generated
# ---------------------------------------------------------------------------

def test_all_datasets_are_written(generated):
    out, manifest = generated
    for name in C.DATASETS:
        assert (manifest["files"][f"{name}.csv"]["rows"] > 0)
    assert json.load(open(f"{out}/{C.MANIFEST_FILENAME}", encoding="utf-8"))["seed"] == C.SEED


# ---------------------------------------------------------------------------
# 2. schema
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name", C.DATASETS)
def test_schema_and_column_order(data, name):
    assert list(data[name][0].keys()) == COLUMNS[name]


# ---------------------------------------------------------------------------
# 3. row counts
# ---------------------------------------------------------------------------

def test_row_counts(data):
    assert len(data["operators"]) == C.N_OPERATORS
    assert len(data["machines"]) == C.N_MACHINES
    assert len(data["tasks"]) == C.N_PENDING_TASKS
    assert len(data["task_history"]) == C.N_HISTORY
    # exactly one telemetry record per completed execution
    assert len(data["telemetry"]) == C.N_HISTORY
    # safety events must be rarer than executions
    assert 0 < len(data["safety_events"]) < C.N_HISTORY


# ---------------------------------------------------------------------------
# 4. no impossible values
# ---------------------------------------------------------------------------

def test_no_negative_durations(data):
    for row in data["task_history"]:
        assert float(row["actual_minutes"]) >= C.MIN_TASK_MINUTES
        assert float(row["estimated_minutes"]) >= C.MIN_TASK_MINUTES


def test_no_negative_fuel_or_engine_hours(data):
    for row in data["telemetry"]:
        assert float(row["fuel_used_liters"]) > 0.0
        assert float(row["engine_hours_reading"]) >= 0.0
        assert float(row["idle_minutes"]) >= 0.0


def test_percentages_and_ratios_are_in_bounds(data):
    for row in data["telemetry"]:
        assert 0.0 <= float(row["idle_ratio"]) <= 1.0
        assert 0.0 <= float(row["avg_load_pct"]) <= 100.0
        assert 0.0 <= float(row["seatbelt_fastened_pct"]) <= 100.0


def test_environment_values_are_physically_possible(data):
    for row in data["task_history"]:
        assert C.HUMIDITY_RANGE_PCT[0] <= float(row["humidity"]) <= C.HUMIDITY_RANGE_PCT[1]
        assert C.RAINFALL_RANGE_MM[0] <= float(row["rainfall"]) <= C.RAINFALL_RANGE_MM[1]
        assert C.VISIBILITY_RANGE_KM[0] <= float(row["visibility"]) <= C.VISIBILITY_RANGE_KM[1]
        assert float(row["wind_speed"]) >= 0.0


def test_idle_never_exceeds_runtime(data):
    for row in data["telemetry"]:
        assert float(row["idle_minutes"]) <= float(row["runtime_minutes"])


# ---------------------------------------------------------------------------
# 5. identifiers and referential integrity
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name,key", [
    ("operators", "operator_id"),
    ("machines", "machine_id"),
    ("tasks", "task_id"),
    ("task_history", "history_id"),
    ("telemetry", "telemetry_id"),
    ("safety_events", "event_id"),
])
def test_ids_are_unique(data, name, key):
    ids = [row[key] for row in data[name]]
    assert len(ids) == len(set(ids))


def test_pending_and_historical_task_ids_are_disjoint(data):
    """No leakage: the backlog must not appear in the training set."""
    pending = {row["task_id"] for row in data["tasks"]}
    historical = {row["task_id"] for row in data["task_history"]}
    assert not (pending & historical)


def test_references_resolve(data):
    operators = {r["operator_id"] for r in data["operators"]}
    machines = {r["machine_id"] for r in data["machines"]}
    histories = {r["history_id"] for r in data["task_history"]}

    for row in data["task_history"]:
        assert row["operator_id"] in operators
        assert row["machine_id"] in machines
    for row in data["telemetry"]:
        assert row["history_id"] in histories
        assert row["machine_id"] in machines
    for row in data["safety_events"]:
        assert row["history_id"] in histories


def test_task_dependencies_are_acyclic_and_resolve(data):
    tasks = {row["task_id"]: row["depends_on_task_id"] for row in data["tasks"]}
    for task_id, parent in tasks.items():
        assert parent != task_id
        if parent:
            assert parent in tasks
            # dependencies always point at a lower-numbered task, so the
            # graph cannot contain a cycle
            assert int(parent[1:]) < int(task_id[1:])


# ---------------------------------------------------------------------------
# 6. timestamps
# ---------------------------------------------------------------------------

def test_timestamps_are_iso_and_ordered(data):
    for row in data["task_history"]:
        start = datetime.fromisoformat(row["started_at"])
        end = datetime.fromisoformat(row["completed_at"])
        assert end > start
        span = (end - start).total_seconds() / 60.0
        assert abs(span - float(row["actual_minutes"])) <= 1.0


def test_engine_hours_accumulate_over_time(data):
    """The reading is taken at completion, so it must never go backwards."""
    per_machine: dict[str, list[float]] = {}
    for row in sorted(data["telemetry"], key=lambda r: r["recorded_at"]):
        per_machine.setdefault(row["machine_id"], []).append(
            float(row["engine_hours_reading"]))
    for machine_id, series in per_machine.items():
        assert series == sorted(series), machine_id


# ---------------------------------------------------------------------------
# 7. synthetic marker
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name", C.DATASETS)
def test_every_record_is_marked_synthetic(data, name):
    values = {row[C.SYNTHETIC_MARKER_COLUMN] for row in data[name]}
    assert values == {C.SYNTHETIC_MARKER}


def test_manifest_carries_the_disclaimer(generated):
    _, manifest = generated
    assert "SYNTHETIC" in manifest["disclaimer"].upper()
    assert "not real caterpillar" in manifest["disclaimer"].lower()


# ---------------------------------------------------------------------------
# 8. logical relationships
# ---------------------------------------------------------------------------

def _mean(values):
    return sum(values) / len(values)


def test_beginners_take_longer_than_experts(data):
    skill_of = {r["operator_id"]: r["skill_level"] for r in data["operators"]}
    ratios: dict[str, list[float]] = {s: [] for s in C.SKILL_LEVELS}
    for row in data["task_history"]:
        ratios[skill_of[row["operator_id"]]].append(
            float(row["actual_minutes"]) / float(row["estimated_minutes"]))
    assert _mean(ratios["BEGINNER"]) > _mean(ratios["INTERMEDIATE"]) > _mean(ratios["EXPERT"])


def test_harder_tasks_take_longer(data):
    """Normalised by the task type's own work content to isolate difficulty."""
    by_difficulty: dict[int, list[float]] = {}
    for row in data["task_history"]:
        baseline = float(row["quantity"]) * C.TASK_TYPES[row["task_type"]]["rate_per_unit"]
        by_difficulty.setdefault(int(row["difficulty"]), []).append(
            float(row["actual_minutes"]) / baseline)
    means = {d: _mean(v) for d, v in by_difficulty.items()}
    assert all(means[d] < means[d + 1] for d in range(1, 5)), means


def test_rain_extends_duration(data):
    dry = [float(r["actual_minutes"]) / float(r["estimated_minutes"])
           for r in data["task_history"] if float(r["rainfall"]) == 0.0]
    wet = [float(r["actual_minutes"]) / float(r["estimated_minutes"])
           for r in data["task_history"] if float(r["rainfall"]) >= 5.0]
    assert dry and wet
    assert _mean(wet) > _mean(dry)


def test_worn_machines_are_slower(data):
    condition = {r["machine_id"]: float(r["condition_rating"]) for r in data["machines"]}
    worn = [float(r["actual_minutes"]) / float(r["estimated_minutes"])
            for r in data["task_history"] if condition[r["machine_id"]] < 0.75]
    good = [float(r["actual_minutes"]) / float(r["estimated_minutes"])
            for r in data["task_history"] if condition[r["machine_id"]] >= 0.90]
    assert worn and good
    assert _mean(worn) > _mean(good)


def test_more_load_cycles_burns_more_fuel(data):
    rows = sorted(data["telemetry"], key=lambda r: int(r["load_cycles"]))
    decile = max(1, len(rows) // 10)
    low = _mean([float(r["fuel_used_liters"]) for r in rows[:decile]])
    high = _mean([float(r["fuel_used_liters"]) for r in rows[-decile:]])
    assert high > low


def test_business_value_rises_with_priority(data):
    values: dict[str, list[float]] = {p: [] for p in C.PRIORITIES}
    for row in data["tasks"]:
        values[row["priority"]].append(float(row["business_value"]))
    means = {p: _mean(v) for p, v in values.items()}
    assert means["CRITICAL"] > means["HIGH"] > means["MEDIUM"] > means["LOW"]


def test_experience_rises_with_skill(data):
    exp: dict[str, list[int]] = {s: [] for s in C.SKILL_LEVELS}
    for row in data["operators"]:
        exp[row["skill_level"]].append(int(row["experience_years"]))
    assert _mean(exp["EXPERT"]) > _mean(exp["INTERMEDIATE"]) > _mean(exp["BEGINNER"])


def test_machine_type_matches_task_requirement(data):
    machine_type = {r["machine_id"]: r["machine_type"] for r in data["machines"]}
    for row in data["task_history"]:
        assert machine_type[row["machine_id"]] == row["required_machine_type"]


# ---------------------------------------------------------------------------
# 9. anomalies and safety events
# ---------------------------------------------------------------------------

def test_injected_anomalies_are_present_but_rare(data):
    injected = [r for r in data["telemetry"] if r["injected_anomaly_type"]]
    rate = len(injected) / len(data["telemetry"])
    assert 0.01 < rate < 0.15, rate


def test_excessive_idling_is_separable_from_normal(data):
    injected = [float(r["idle_ratio"]) for r in data["telemetry"]
                if r["injected_anomaly_type"] == "EXCESSIVE_IDLING"]
    normal = [float(r["idle_ratio"]) for r in data["telemetry"]
              if not r["injected_anomaly_type"]]
    assert injected and normal
    assert min(injected) > max(normal)


def test_safety_events_are_rare(data):
    affected = {r["history_id"] for r in data["safety_events"]}
    rate = len(affected) / len(data["task_history"])
    assert 0.01 < rate < 0.25, rate


def test_every_safety_event_traces_to_an_observable_condition(data):
    telemetry = {r["history_id"]: r for r in data["telemetry"]}
    for event in data["safety_events"]:
        row = telemetry[event["history_id"]]
        kind = event["event_type"]
        if kind == "SEATBELT":
            assert float(row["seatbelt_fastened_pct"]) < C.SEATBELT_THRESHOLD_PCT
        elif kind == "PROXIMITY":
            assert float(row["min_proximity_m"]) < C.PROXIMITY_THRESHOLD_M
        elif kind == "OVERSPEED":
            assert float(row["max_speed_kph"]) > C.SPEED_LIMIT_KPH
        elif kind == "EXCESSIVE_IDLING":
            assert float(row["idle_ratio"]) > C.IDLE_EVENT_THRESHOLD
        else:
            assert kind == "UNCERTIFIED_OPERATION"


def test_uncertified_events_match_operator_certifications(data):
    certs = {r["operator_id"]: set(r["certifications"].split("|"))
             for r in data["operators"]}
    machine_type = {r["machine_id"]: r["machine_type"] for r in data["machines"]}
    for event in data["safety_events"]:
        if event["event_type"] != "UNCERTIFIED_OPERATION":
            continue
        required = C.MACHINE_TYPE_CERT[machine_type[event["machine_id"]]]
        assert required not in certs[event["operator_id"]]


def test_safety_descriptions_stay_observational(data):
    approved = set(C.EVENT_DESCRIPTIONS.values())
    for event in data["safety_events"]:
        assert event["description"] in approved


def test_severities_use_the_canonical_vocabulary(data):
    for event in data["safety_events"]:
        assert event["severity"] in C.SEVERITIES


# ---------------------------------------------------------------------------
# 10. reproducibility
# ---------------------------------------------------------------------------

def test_same_seed_produces_identical_files(tmp_path):
    """Two independent runs with seed=42 must be byte-identical."""
    first = generate_all(str(tmp_path / "a"), 42)
    second = generate_all(str(tmp_path / "b"), 42)
    for name in C.DATASETS:
        key = f"{name}.csv"
        assert first["files"][key]["sha256"] == second["files"][key]["sha256"], name
        assert (tmp_path / "a" / key).read_bytes() == (tmp_path / "b" / key).read_bytes()


def test_different_seed_produces_different_data(tmp_path):
    """Guards against a seed that is accepted but ignored."""
    a = generate_all(str(tmp_path / "s42"), 42)
    b = generate_all(str(tmp_path / "s7"), 7)
    assert a["files"]["task_history.csv"]["sha256"] != b["files"]["task_history.csv"]["sha256"]


# ---------------------------------------------------------------------------
# 11. the full validation suite
# ---------------------------------------------------------------------------

def test_validation_suite_passes(generated):
    out, _ = generated
    report = validate(out)
    assert report.ok, [f"{name}: {detail}" for _, name, detail in report.failures]


def test_validation_suite_is_not_vacuous(generated):
    """A suite that runs no checks would trivially 'pass'."""
    out, _ = generated
    report = validate(out)
    assert len(report.results) > 100

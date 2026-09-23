"""
Validation for the generated synthetic datasets.

Checks schema, types, nulls, uniqueness, numeric ranges, categorical values,
timestamp validity, referential integrity, the synthetic marker, and the
logical relationships the generator is supposed to produce.

Reports only what it actually measures. No check is assumed to pass.

Usage
-----
    python -m scripts.data_generation.validate
    python -m scripts.data_generation.validate --data data/generated
"""

from __future__ import annotations

import argparse
import csv
import json
import os
from collections import Counter, defaultdict
from datetime import datetime

from scripts.data_generation import config as C
from scripts.data_generation.generate import COLUMNS


class Report:
    """Collects pass/fail results so every check is reported, not just the first."""

    def __init__(self) -> None:
        self.results: list[tuple[bool, str, str]] = []

    def check(self, ok: bool, name: str, detail: str = "") -> bool:
        self.results.append((bool(ok), name, detail))
        return bool(ok)

    @property
    def failures(self) -> list[tuple[bool, str, str]]:
        return [r for r in self.results if not r[0]]

    @property
    def passed(self) -> int:
        return sum(1 for ok, _, _ in self.results if ok)

    def printout(self) -> None:
        for ok, name, detail in self.results:
            mark = "PASS" if ok else "FAIL"
            line = f"[{mark}] {name}"
            if detail:
                line += f" - {detail}"
            print(line)
        print()
        print(f"{self.passed}/{len(self.results)} checks passed")
        if self.failures:
            print(f"{len(self.failures)} FAILED")

    @property
    def ok(self) -> bool:
        return not self.failures


def read_csv(path: str) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _is_float(value: str) -> bool:
    try:
        float(value)
        return True
    except (TypeError, ValueError):
        return False


def _is_int(value: str) -> bool:
    try:
        int(value)
        return True
    except (TypeError, ValueError):
        return False


def _numeric_range(rows, column, low, high):
    """Return (ok, detail) for a numeric column bounded by [low, high]."""
    bad = []
    lo_seen, hi_seen = None, None
    for row in rows:
        if not _is_float(row[column]):
            bad.append(row[column])
            continue
        value = float(row[column])
        lo_seen = value if lo_seen is None else min(lo_seen, value)
        hi_seen = value if hi_seen is None else max(hi_seen, value)
        if value < low or value > high:
            bad.append(value)
    if bad:
        return False, f"{len(bad)} out-of-range values, e.g. {bad[:3]}"
    return True, f"observed [{lo_seen}, {hi_seen}] within [{low}, {high}]"


def _categorical(rows, column, allowed, allow_blank=False):
    seen = Counter(row[column] for row in rows)
    bad = {v: n for v, n in seen.items()
           if v not in allowed and not (allow_blank and v == "")}
    if bad:
        return False, f"unexpected values: {dict(list(bad.items())[:4])}"
    return True, f"{len(seen)} distinct, all allowed"


# ---------------------------------------------------------------------------
# checks
# ---------------------------------------------------------------------------

def validate(data_dir: str) -> Report:
    report = Report()

    # --- files exist ------------------------------------------------------
    paths = {name: os.path.join(data_dir, f"{name}.csv") for name in C.DATASETS}
    for name, path in paths.items():
        report.check(os.path.exists(path), f"file exists: {name}.csv", path)
    if report.failures:
        return report

    data = {name: read_csv(path) for name, path in paths.items()}

    manifest_path = os.path.join(data_dir, C.MANIFEST_FILENAME)
    report.check(os.path.exists(manifest_path), "file exists: manifest.json")
    manifest = {}
    if os.path.exists(manifest_path):
        with open(manifest_path, encoding="utf-8") as handle:
            manifest = json.load(handle)
        report.check(manifest.get("seed") == C.SEED,
                     "manifest records the seed", f"seed={manifest.get('seed')}")
        report.check("SYNTHETIC" in manifest.get("disclaimer", "").upper(),
                     "manifest carries a synthetic-data disclaimer")

    # --- schema -----------------------------------------------------------
    for name, rows in data.items():
        expected = COLUMNS[name]
        actual = list(rows[0].keys()) if rows else []
        report.check(actual == expected, f"schema matches: {name}",
                     "exact column order" if actual == expected
                     else f"expected {expected}, got {actual}")

    # --- row counts -------------------------------------------------------
    report.check(len(data["operators"]) == C.N_OPERATORS,
                 "row count: operators", f"{len(data['operators'])}")
    report.check(len(data["machines"]) == C.N_MACHINES,
                 "row count: machines", f"{len(data['machines'])}")
    report.check(len(data["tasks"]) == C.N_PENDING_TASKS,
                 "row count: tasks", f"{len(data['tasks'])}")
    report.check(len(data["task_history"]) == C.N_HISTORY,
                 "row count: task_history", f"{len(data['task_history'])}")
    report.check(len(data["telemetry"]) == C.N_HISTORY,
                 "row count: telemetry (one per execution)", f"{len(data['telemetry'])}")
    report.check(0 < len(data["safety_events"]) < C.N_HISTORY,
                 "row count: safety_events non-empty and rarer than executions",
                 f"{len(data['safety_events'])} events for {C.N_HISTORY} executions")

    # --- nulls ------------------------------------------------------------
    nullable = {
        "tasks": {"depends_on_task_id"},
        "telemetry": {"injected_anomaly_type"},
    }
    for name, rows in data.items():
        allowed_blank = nullable.get(name, set())
        empty = defaultdict(int)
        for row in rows:
            for column, value in row.items():
                if value is None or value == "":
                    if column not in allowed_blank:
                        empty[column] += 1
        report.check(not empty, f"no unexpected nulls: {name}",
                     "all required fields populated" if not empty else dict(empty))

    # --- unique ids -------------------------------------------------------
    unique_keys = {
        "operators": "operator_id",
        "machines": "machine_id",
        "tasks": "task_id",
        "task_history": "history_id",
        "telemetry": "telemetry_id",
        "safety_events": "event_id",
    }
    for name, key in unique_keys.items():
        ids = [row[key] for row in data[name]]
        report.check(len(ids) == len(set(ids)), f"unique {key}: {name}",
                     f"{len(set(ids))} distinct of {len(ids)}")

    history_task_ids = [row["task_id"] for row in data["task_history"]]
    report.check(len(history_task_ids) == len(set(history_task_ids)),
                 "unique task_id: task_history",
                 f"{len(set(history_task_ids))} distinct")

    # --- pending vs historical task ids must not overlap ------------------
    overlap = set(row["task_id"] for row in data["tasks"]) & set(history_task_ids)
    report.check(not overlap, "no task_id overlap between tasks and task_history",
                 "disjoint id ranges" if not overlap else f"{len(overlap)} shared ids")

    # --- referential integrity -------------------------------------------
    operator_ids = {row["operator_id"] for row in data["operators"]}
    machine_ids = {row["machine_id"] for row in data["machines"]}
    history_ids = {row["history_id"] for row in data["task_history"]}

    for name, column, valid in [
        ("task_history", "operator_id", operator_ids),
        ("task_history", "machine_id", machine_ids),
        ("telemetry", "operator_id", operator_ids),
        ("telemetry", "machine_id", machine_ids),
        ("telemetry", "history_id", history_ids),
        ("safety_events", "operator_id", operator_ids),
        ("safety_events", "machine_id", machine_ids),
        ("safety_events", "history_id", history_ids),
    ]:
        bad = [row[column] for row in data[name] if row[column] not in valid]
        report.check(not bad, f"referential integrity: {name}.{column}",
                     "all references resolve" if not bad else f"{len(bad)} dangling")

    dep_ids = {row["depends_on_task_id"] for row in data["tasks"]} - {""}
    task_ids = {row["task_id"] for row in data["tasks"]}
    report.check(dep_ids <= task_ids, "referential integrity: tasks.depends_on_task_id",
                 f"{len(dep_ids)} dependencies all resolve")

    no_self_dep = [r for r in data["tasks"] if r["depends_on_task_id"] == r["task_id"]]
    report.check(not no_self_dep, "no task depends on itself")

    # --- data types -------------------------------------------------------
    int_columns = {
        "operators": ["experience_years"],
        "machines": ["year_manufactured", "age_years"],
        "tasks": ["difficulty", "quantity", "business_value", "estimated_minutes"],
        "task_history": ["difficulty", "quantity", "business_value", "estimated_minutes"],
        "telemetry": ["load_cycles", "proximity_alerts_count"],
    }
    float_columns = {
        "machines": ["engine_hours", "condition_rating", "capacity_units"],
        "task_history": ["temperature", "rainfall", "humidity", "wind_speed",
                         "visibility", "actual_minutes"],
        "telemetry": ["engine_hours_reading", "runtime_minutes", "idle_minutes",
                      "idle_ratio", "fuel_used_liters", "fuel_per_unit",
                      "avg_load_pct", "load_variance", "engine_temp_c",
                      "hydraulic_pressure_psi", "max_speed_kph",
                      "seatbelt_fastened_pct", "min_proximity_m"],
    }
    for name, columns in int_columns.items():
        bad = [(c, r[c]) for r in data[name] for c in columns if not _is_int(r[c])]
        report.check(not bad, f"integer columns parse: {name}",
                     ", ".join(columns) if not bad else str(bad[:3]))
    for name, columns in float_columns.items():
        bad = [(c, r[c]) for r in data[name] for c in columns if not _is_float(r[c])]
        report.check(not bad, f"float columns parse: {name}",
                     f"{len(columns)} columns" if not bad else str(bad[:3]))

    # --- numeric ranges: no impossible values ----------------------------
    ranges = [
        ("task_history", "actual_minutes", C.MIN_TASK_MINUTES, 1500.0),
        ("task_history", "estimated_minutes", C.MIN_TASK_MINUTES, 1500.0),
        ("task_history", "temperature", *C.TEMPERATURE_RANGE_C),
        ("task_history", "rainfall", *C.RAINFALL_RANGE_MM),
        ("task_history", "humidity", *C.HUMIDITY_RANGE_PCT),
        ("task_history", "wind_speed", *C.WIND_SPEED_RANGE_KPH),
        ("task_history", "visibility", *C.VISIBILITY_RANGE_KM),
        ("task_history", "quantity", 1, 1000),
        ("task_history", "difficulty", 1, 5),
        ("tasks", "difficulty", 1, 5),
        ("tasks", "quantity", 1, 1000),
        ("tasks", "business_value", 1, 100000),
        ("tasks", "estimated_minutes", C.MIN_TASK_MINUTES, 1500.0),
        ("machines", "condition_rating", *C.CONDITION_RANGE),
        ("machines", "age_years", *C.MACHINE_AGE_RANGE_YEARS),
        ("machines", "engine_hours", 0.0, 60000.0),
        ("operators", "experience_years", 0, 40),
        ("telemetry", "idle_ratio", *C.IDLE_RATIO_BOUNDS),
        ("telemetry", "runtime_minutes", C.MIN_TASK_MINUTES, 1500.0),
        ("telemetry", "idle_minutes", 0.0, 1500.0),
        ("telemetry", "fuel_used_liters", 0.0, 2000.0),
        ("telemetry", "fuel_per_unit", 0.0, 500.0),
        ("telemetry", "load_cycles", 1, 5000),
        ("telemetry", "avg_load_pct", *C.AVG_LOAD_PCT_BOUNDS),
        ("telemetry", "engine_temp_c", *C.ENGINE_TEMP_BOUNDS_C),
        ("telemetry", "hydraulic_pressure_psi", *C.HYDRAULIC_PRESSURE_BOUNDS_PSI),
        ("telemetry", "max_speed_kph", 0.0, 60.0),
        ("telemetry", "seatbelt_fastened_pct", 0.0, 100.0),
        ("telemetry", "min_proximity_m", 0.0, 100.0),
        ("telemetry", "engine_hours_reading", 0.0, 60000.0),
        ("telemetry", "proximity_alerts_count", 0, 20),
    ]
    for name, column, low, high in ranges:
        ok, detail = _numeric_range(data[name], column, low, high)
        report.check(ok, f"range: {name}.{column}", detail)

    # --- categorical values ----------------------------------------------
    categoricals = [
        ("operators", "skill_level", set(C.SKILL_LEVELS), False),
        ("operators", "primary_shift", {"DAY", "NIGHT"}, False),
        ("machines", "machine_type", set(C.MACHINE_TYPES), False),
        ("machines", "home_zone", set(C.SITE_ZONES), False),
        ("tasks", "task_type", set(C.TASK_TYPES), False),
        ("tasks", "priority", set(C.PRIORITIES), False),
        ("tasks", "terrain", set(C.TERRAINS), False),
        ("tasks", "status", set(C.TASK_STATUSES), False),
        ("tasks", "site_zone", set(C.SITE_ZONES), False),
        ("tasks", "required_machine_type", set(C.MACHINE_TYPES), False),
        ("tasks", "quantity_unit", set(C.LOAD_CYCLES_PER_UNIT), False),
        ("task_history", "task_type", set(C.TASK_TYPES), False),
        ("task_history", "priority", set(C.PRIORITIES), False),
        ("task_history", "terrain", set(C.TERRAINS), False),
        ("task_history", "weather", set(C.WEATHER_CONDITIONS), False),
        ("task_history", "shift", {"DAY", "NIGHT"}, False),
        ("telemetry", "injected_anomaly_type", set(C.ANOMALY_TYPES), True),
        ("safety_events", "event_type", set(C.EVENT_TYPES), False),
        ("safety_events", "severity", set(C.SEVERITIES), False),
    ]
    for name, column, allowed, allow_blank in categoricals:
        ok, detail = _categorical(data[name], column, allowed, allow_blank)
        report.check(ok, f"categorical: {name}.{column}", detail)

    # --- certifications are drawn from the known vocabulary --------------
    bad_certs = set()
    for row in data["operators"]:
        bad_certs |= set(row["certifications"].split("|")) - set(C.CERTIFICATIONS)
    report.check(not bad_certs, "categorical: operators.certifications",
                 "all known" if not bad_certs else str(bad_certs))

    # --- timestamps -------------------------------------------------------
    def parse_all(rows, column):
        bad = []
        parsed = []
        for row in rows:
            try:
                parsed.append(datetime.fromisoformat(row[column]))
            except ValueError:
                bad.append(row[column])
        return parsed, bad

    for name, column in [("task_history", "started_at"),
                         ("task_history", "completed_at"),
                         ("telemetry", "recorded_at"),
                         ("safety_events", "timestamp")]:
        parsed, bad = parse_all(data[name], column)
        report.check(not bad, f"timestamp parses (ISO-8601): {name}.{column}",
                     f"{len(parsed)} valid" if not bad else str(bad[:3]))

    bad_order = 0
    for row in data["task_history"]:
        start = datetime.fromisoformat(row["started_at"])
        end = datetime.fromisoformat(row["completed_at"])
        if end <= start:
            bad_order += 1
    report.check(bad_order == 0, "completed_at is after started_at",
                 f"{len(data['task_history'])} rows ordered correctly")

    # duration must equal the timestamp span
    mismatch = 0
    for row in data["task_history"]:
        start = datetime.fromisoformat(row["started_at"])
        end = datetime.fromisoformat(row["completed_at"])
        span = (end - start).total_seconds() / 60.0
        if abs(span - float(row["actual_minutes"])) > 1.0:
            mismatch += 1
    report.check(mismatch == 0, "actual_minutes matches the timestamp span",
                 f"within 1 minute on all {len(data['task_history'])} rows")

    # --- synthetic marker -------------------------------------------------
    for name, rows in data.items():
        values = {row[C.SYNTHETIC_MARKER_COLUMN] for row in rows}
        report.check(values == {C.SYNTHETIC_MARKER},
                     f"synthetic marker on every row: {name}",
                     f"{C.SYNTHETIC_MARKER_COLUMN}={values}")

    # --- logical relationships -------------------------------------------
    # Duration per unit of work isolates operator/condition effects from the
    # sheer amount of work, so these comparisons are meaningful.
    skill_of = {r["operator_id"]: r["skill_level"] for r in data["operators"]}
    per_unit_by_skill = defaultdict(list)
    for row in data["task_history"]:
        ratio = float(row["actual_minutes"]) / float(row["estimated_minutes"])
        per_unit_by_skill[skill_of[row["operator_id"]]].append(ratio)

    means = {skill: sum(v) / len(v) for skill, v in per_unit_by_skill.items()}
    report.check(
        means["BEGINNER"] > means["INTERMEDIATE"] > means["EXPERT"],
        "relationship: beginners take longer than experts",
        "actual/estimated means - "
        + ", ".join(f"{k}={means[k]:.3f}" for k in ("BEGINNER", "INTERMEDIATE", "EXPERT")),
    )

    # Normalise by the task type's own baseline work content (quantity x rate)
    # so the comparison isolates difficulty instead of the task-type mix.
    by_difficulty = defaultdict(list)
    for row in data["task_history"]:
        baseline = float(row["quantity"]) * C.TASK_TYPES[row["task_type"]]["rate_per_unit"]
        by_difficulty[int(row["difficulty"])].append(float(row["actual_minutes"]) / baseline)
    diff_means = {d: sum(v) / len(v) for d, v in sorted(by_difficulty.items())}
    ordered = all(diff_means[d] < diff_means[d + 1] for d in range(1, 5))
    report.check(ordered, "relationship: harder tasks take longer per unit of work",
                 ", ".join(f"d{d}={m:.3f}" for d, m in diff_means.items()))

    within_type = defaultdict(lambda: defaultdict(list))
    for row in data["task_history"]:
        within_type[row["task_type"]][int(row["quantity"])].append(float(row["actual_minutes"]))
    positive = 0
    for task_type, by_qty in within_type.items():
        pairs = sorted((q, sum(v) / len(v)) for q, v in by_qty.items())
        if len(pairs) >= 10:
            low = sum(m for _, m in pairs[:5]) / 5
            high = sum(m for _, m in pairs[-5:]) / 5
            if high > low:
                positive += 1
    report.check(positive == len(within_type),
                 "relationship: larger quantity takes longer (per task type)",
                 f"{positive}/{len(within_type)} task types show the trend")

    dry = [float(r["actual_minutes"]) / float(r["estimated_minutes"])
           for r in data["task_history"] if float(r["rainfall"]) == 0.0]
    wet = [float(r["actual_minutes"]) / float(r["estimated_minutes"])
           for r in data["task_history"] if float(r["rainfall"]) >= 5.0]
    dry_mean = sum(dry) / len(dry)
    wet_mean = sum(wet) / len(wet)
    report.check(wet_mean > dry_mean,
                 "relationship: rain extends duration",
                 f"dry={dry_mean:.3f} (n={len(dry)}) vs wet={wet_mean:.3f} (n={len(wet)})")

    condition_of = {r["machine_id"]: float(r["condition_rating"]) for r in data["machines"]}
    worn = [float(r["actual_minutes"]) / float(r["estimated_minutes"])
            for r in data["task_history"] if condition_of[r["machine_id"]] < 0.75]
    good = [float(r["actual_minutes"]) / float(r["estimated_minutes"])
            for r in data["task_history"] if condition_of[r["machine_id"]] >= 0.90]
    if worn and good:
        worn_mean, good_mean = sum(worn) / len(worn), sum(good) / len(good)
        report.check(worn_mean > good_mean,
                     "relationship: worn machines are slower",
                     f"worn={worn_mean:.3f} (n={len(worn)}) vs good={good_mean:.3f} (n={len(good)})")

    # fuel should rise with load cycles
    tel = data["telemetry"]
    by_cycles = sorted(tel, key=lambda r: int(r["load_cycles"]))
    tenth = max(1, len(by_cycles) // 10)
    low_fuel = sum(float(r["fuel_used_liters"]) for r in by_cycles[:tenth]) / tenth
    high_fuel = sum(float(r["fuel_used_liters"]) for r in by_cycles[-tenth:]) / tenth
    report.check(high_fuel > low_fuel,
                 "relationship: more load cycles means more fuel",
                 f"bottom decile={low_fuel:.1f} L vs top decile={high_fuel:.1f} L")

    # idle time is a share of runtime, so it can never exceed it
    bad_idle = [r for r in tel if float(r["idle_minutes"]) > float(r["runtime_minutes"])]
    report.check(not bad_idle, "idle_minutes never exceeds runtime_minutes",
                 f"{len(tel)} rows consistent")

    # telemetry runtime must match the execution it belongs to
    actual_by_history = {r["history_id"]: float(r["actual_minutes"]) for r in data["task_history"]}
    runtime_mismatch = [r for r in tel
                        if abs(float(r["runtime_minutes"]) - actual_by_history[r["history_id"]]) > 0.11]
    report.check(not runtime_mismatch, "telemetry runtime matches task_history duration",
                 f"{len(tel)} rows agree")

    # engine hours accumulate monotonically per machine over time
    readings = defaultdict(list)
    for row in sorted(tel, key=lambda r: r["recorded_at"]):
        readings[row["machine_id"]].append(float(row["engine_hours_reading"]))
    non_monotonic = sum(
        1 for series in readings.values()
        for a, b in zip(series, series[1:]) if b < a
    )
    report.check(non_monotonic == 0, "engine_hours_reading is non-decreasing per machine",
                 f"{len(readings)} machines checked")

    # machines.engine_hours equals the latest telemetry reading
    final_reading = {m: max(series) for m, series in readings.items()}
    hours_mismatch = [
        m["machine_id"] for m in data["machines"]
        if m["machine_id"] in final_reading
        and abs(float(m["engine_hours"]) - final_reading[m["machine_id"]]) > 0.11
    ]
    report.check(not hours_mismatch, "machines.engine_hours matches final telemetry reading",
                 "consistent" if not hours_mismatch else str(hours_mismatch[:3]))

    # injected anomalies are present but rare
    injected = Counter(r["injected_anomaly_type"] for r in tel)
    n_injected = sum(v for k, v in injected.items() if k)
    rate = n_injected / len(tel)
    report.check(0.01 < rate < 0.15, "injected anomalies present but rare",
                 f"{n_injected}/{len(tel)} = {rate:.1%}")

    # injected excessive idling really does show a high idle ratio
    idle_injected = [float(r["idle_ratio"]) for r in tel
                     if r["injected_anomaly_type"] == "EXCESSIVE_IDLING"]
    idle_normal = [float(r["idle_ratio"]) for r in tel if not r["injected_anomaly_type"]]
    if idle_injected:
        report.check(
            min(idle_injected) > max(idle_normal),
            "relationship: injected excessive idling is separable from normal",
            f"injected min={min(idle_injected):.3f} > normal max={max(idle_normal):.3f}",
        )

    # --- safety events ----------------------------------------------------
    events = data["safety_events"]
    executions_with_events = len({r["history_id"] for r in events})
    event_rate = executions_with_events / len(data["task_history"])
    report.check(0.01 < event_rate < 0.25,
                 "safety events are rare but present",
                 f"{executions_with_events} of {len(data['task_history'])} "
                 f"executions = {event_rate:.1%}")

    # every safety event must trace back to an observable telemetry condition
    tel_by_history = {r["history_id"]: r for r in tel}
    unexplained = []
    for event in events:
        row = tel_by_history.get(event["history_id"])
        if row is None:
            unexplained.append(event["event_id"])
            continue
        kind = event["event_type"]
        if kind == "SEATBELT":
            ok = float(row["seatbelt_fastened_pct"]) < C.SEATBELT_THRESHOLD_PCT
        elif kind == "PROXIMITY":
            ok = float(row["min_proximity_m"]) < C.PROXIMITY_THRESHOLD_M
        elif kind == "OVERSPEED":
            ok = float(row["max_speed_kph"]) > C.SPEED_LIMIT_KPH
        elif kind == "EXCESSIVE_IDLING":
            ok = float(row["idle_ratio"]) > C.IDLE_EVENT_THRESHOLD
        elif kind == "UNCERTIFIED_OPERATION":
            ok = True          # verified against operator certifications below
        else:
            ok = False
        if not ok:
            unexplained.append(event["event_id"])
    report.check(not unexplained,
                 "every safety event traces to an observable condition",
                 f"{len(events)} events verified against telemetry"
                 if not unexplained else f"{len(unexplained)} unexplained")

    # uncertified-operation events must match the operator's certifications
    certs_of = {r["operator_id"]: set(r["certifications"].split("|"))
                for r in data["operators"]}
    machine_type_of = {r["machine_id"]: r["machine_type"] for r in data["machines"]}
    wrong = []
    for event in events:
        if event["event_type"] != "UNCERTIFIED_OPERATION":
            continue
        required = C.MACHINE_TYPE_CERT[machine_type_of[event["machine_id"]]]
        if required in certs_of[event["operator_id"]]:
            wrong.append(event["event_id"])
    report.check(not wrong, "UNCERTIFIED_OPERATION events match operator certifications",
                 "verified" if not wrong else f"{len(wrong)} contradictory")

    # event descriptions stay observational
    allowed_descriptions = set(C.EVENT_DESCRIPTIONS.values())
    bad_desc = {e["description"] for e in events} - allowed_descriptions
    report.check(not bad_desc, "safety descriptions use approved observational wording",
                 "all approved" if not bad_desc else str(bad_desc))

    # --- distributions are sensible, not uniform noise -------------------
    priority_counts = Counter(r["priority"] for r in data["tasks"])
    report.check(
        priority_counts["MEDIUM"] > priority_counts["CRITICAL"],
        "distribution: task priority is logical (MEDIUM common, CRITICAL rare)",
        str(dict(priority_counts)),
    )

    value_by_priority = defaultdict(list)
    for row in data["tasks"]:
        value_by_priority[row["priority"]].append(float(row["business_value"]))
    vmeans = {k: sum(v) / len(v) for k, v in value_by_priority.items()}
    report.check(
        vmeans["CRITICAL"] > vmeans["HIGH"] > vmeans["MEDIUM"] > vmeans["LOW"],
        "relationship: business value rises with priority",
        ", ".join(f"{k}={vmeans[k]:.0f}" for k in C.PRIORITIES),
    )

    skills = Counter(r["skill_level"] for r in data["operators"])
    report.check(len(skills) == 3, "all three skill levels present", str(dict(skills)))

    exp_by_skill = defaultdict(list)
    for row in data["operators"]:
        exp_by_skill[row["skill_level"]].append(int(row["experience_years"]))
    emeans = {k: sum(v) / len(v) for k, v in exp_by_skill.items()}
    report.check(emeans["EXPERT"] > emeans["INTERMEDIATE"] > emeans["BEGINNER"],
                 "relationship: experience rises with skill level",
                 ", ".join(f"{k}={emeans[k]:.1f}y" for k in C.SKILL_LEVELS))

    # machine assignment must respect the required machine type
    wrong_machine = [r for r in data["task_history"]
                     if machine_type_of[r["machine_id"]] != r["required_machine_type"]]
    report.check(not wrong_machine, "machine type matches the task requirement",
                 f"{len(data['task_history'])} executions compatible")

    # history must be spread across the intended window
    days = {r["shift_date"] for r in data["task_history"]}
    report.check(len(days) > C.HISTORY_DAYS * 0.8,
                 "history spans the intended date window",
                 f"{len(days)} distinct days over {C.HISTORY_DAYS}")

    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate generated synthetic data.")
    parser.add_argument("--data", default=C.OUTPUT_DIR, help="directory holding the CSVs")
    args = parser.parse_args()

    print(f"Validating SYNTHETIC data in {args.data}\n")
    report = validate(args.data)
    report.printout()
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

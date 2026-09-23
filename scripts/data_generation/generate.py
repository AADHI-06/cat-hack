"""
Synthetic data generator for the CAT Smart Operator Assistant.

SYNTHETIC DATA ONLY. Every record carries data_source="synthetic". This is not
real Caterpillar operational data and must never be presented as such.

Design notes
------------
* Reproducible: one seeded random.Random(SEED) drives everything, and the
  datasets are generated in a fixed order. Same seed -> byte-identical CSVs.
* Correlated, not independent: durations, fuel, load cycles and safety events
  are all derived from shared underlying facts (skill, difficulty, quantity,
  machine condition, weather) with bounded noise on top.
* Latent factors stay internal: the multipliers used to build a duration are
  never written to the CSV, so a model trained on task_history cannot read the
  answer off a feature column.
* Pending tasks and historical tasks use disjoint task_id ranges, so there is
  no overlap between the backlog and the training set.

Usage
-----
    python -m scripts.data_generation.generate
    python -m scripts.data_generation.generate --out data/generated --seed 42
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import random
from datetime import date, datetime, timedelta

from scripts.data_generation import config as C


# ---------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------

def _round(value: float, places: int = 2) -> float:
    """Round for output. Keeps CSVs stable and readable."""
    return round(value + 0.0, places)


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _weighted(rng: random.Random, options, weights):
    return rng.choices(options, weights=weights, k=1)[0]


def _bounded_noise(rng: random.Random) -> float:
    """Lognormal variation, clipped so it can never produce absurd output."""
    factor = math.exp(rng.gauss(0.0, C.NOISE_SIGMA))
    return _clamp(factor, C.NOISE_MIN, C.NOISE_MAX)


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%S")


# ---------------------------------------------------------------------------
# environment
# ---------------------------------------------------------------------------

def _make_environment(rng: random.Random) -> dict:
    """
    Observed conditions for one task execution.

    Field names match the `environment` block of the task prediction contract
    in docs/contracts.md. Rainfall, humidity and visibility are correlated:
    rain implies higher humidity and reduced visibility.
    """
    raining = rng.random() < C.P_RAIN
    if raining:
        rainfall = _clamp(rng.expovariate(1 / 6.0), 0.2, C.RAINFALL_RANGE_MM[1])
    else:
        rainfall = 0.0

    # Humidity rises with rainfall.
    humidity_base = rng.uniform(25.0, 80.0)
    humidity = _clamp(humidity_base + rainfall * 1.6, *C.HUMIDITY_RANGE_PCT)

    # Visibility falls with rainfall; fog is possible without rain.
    visibility = C.VISIBILITY_RANGE_KM[1] - rainfall * 0.22
    if not raining and rng.random() < 0.05:
        visibility = rng.uniform(0.5, 2.5)          # fog
    visibility = _clamp(visibility + rng.gauss(0, 0.6), *C.VISIBILITY_RANGE_KM)

    # Rain cools things down a little.
    temperature = _clamp(rng.gauss(28.0, 6.0) - rainfall * 0.15, *C.TEMPERATURE_RANGE_C)
    wind_speed = _clamp(abs(rng.gauss(12.0, 7.0)) + rainfall * 0.3, *C.WIND_SPEED_RANGE_KPH)

    if rainfall >= 12.0:
        weather = "HEAVY_RAIN"
    elif rainfall > 0.0:
        weather = "RAIN"
    elif visibility < C.POOR_VISIBILITY_KM:
        weather = "FOG"
    elif humidity > 70.0:
        weather = "CLOUDY"
    else:
        weather = "CLEAR"

    return {
        "temperature": _round(temperature, 1),
        "rainfall": _round(rainfall, 1),
        "humidity": _round(humidity, 1),
        "wind_speed": _round(wind_speed, 1),
        "visibility": _round(visibility, 1),
        "weather": weather,
    }


def _weather_multiplier(env: dict) -> float:
    """Adverse conditions can extend a task. Derived from observed values."""
    multiplier = 1.0
    multiplier *= 1.0 + min(env["rainfall"], C.RAINFALL_PENALTY_CAP_MM) * C.RAINFALL_PENALTY_PER_MM
    if env["visibility"] < C.POOR_VISIBILITY_KM:
        multiplier *= C.POOR_VISIBILITY_MULTIPLIER
    elif env["visibility"] < C.LOW_VISIBILITY_KM:
        multiplier *= C.LOW_VISIBILITY_MULTIPLIER
    if env["wind_speed"] > C.HIGH_WIND_KPH:
        multiplier *= C.HIGH_WIND_MULTIPLIER
    if env["temperature"] > C.HOT_TEMPERATURE_C:
        multiplier *= C.HOT_MULTIPLIER
    elif env["temperature"] < C.COLD_TEMPERATURE_C:
        multiplier *= C.COLD_MULTIPLIER
    return multiplier


# ---------------------------------------------------------------------------
# operators
# ---------------------------------------------------------------------------

FIRST_NAMES = [
    "Arun", "Bhavya", "Chen", "Devi", "Ethan", "Farah", "Gopal", "Hana",
    "Imran", "Jyoti", "Karan", "Lena", "Manoj", "Nadia", "Omar", "Priya",
    "Quinn", "Rahul", "Sara", "Tariq", "Uma", "Vikram", "Wei", "Xiomara",
    "Yusuf", "Zara", "Ananya", "Bilal", "Carlos", "Divya", "Elena", "Faisal",
    "Gita", "Hugo", "Ishaan", "Jana", "Kiran", "Luca", "Meera", "Niko",
]
LAST_NAMES = [
    "Anand", "Baptiste", "Chowdhury", "Diaz", "Eriksen", "Fernandes",
    "Gupta", "Haddad", "Iyer", "Johansson", "Kapoor", "Lopez", "Mehta",
    "Novak", "Okafor", "Patel", "Qureshi", "Rao", "Silva", "Tanaka",
]


def generate_operators(rng: random.Random) -> list[dict]:
    """Operators. Experience and certifications follow skill level."""
    rows = []
    for i in range(1, C.N_OPERATORS + 1):
        skill = _weighted(rng, C.SKILL_LEVELS, C.SKILL_WEIGHTS)
        exp_low, exp_high = C.EXPERIENCE_YEARS_BY_SKILL[skill]
        experience = rng.randint(exp_low, exp_high)

        n_low, n_high = C.N_MACHINE_CERTS_BY_SKILL[skill]
        machine_certs = rng.sample(
            sorted(C.MACHINE_TYPE_CERT.values()), rng.randint(n_low, n_high)
        )
        certs = list(machine_certs)
        for extra in ("CONFINED_SPACE", "BLASTING_AWARE"):
            if rng.random() < C.P_EXTRA_CERT[skill]:
                certs.append(extra)

        rows.append({
            "operator_id": f"OP{i:03d}",
            "name": f"{FIRST_NAMES[(i - 1) % len(FIRST_NAMES)]} "
                    f"{LAST_NAMES[(i * 7) % len(LAST_NAMES)]}",
            "skill_level": skill,
            "experience_years": experience,
            "certifications": "|".join(sorted(certs)),
            "primary_shift": _weighted(rng, ["DAY", "NIGHT"], [0.65, 0.35]),
            C.SYNTHETIC_MARKER_COLUMN: C.SYNTHETIC_MARKER,
        })
    return rows


# ---------------------------------------------------------------------------
# machines
# ---------------------------------------------------------------------------

def generate_machines(rng: random.Random, reference: date) -> list[dict]:
    """
    Machines. Older machines have more engine hours and a lower condition
    rating, which later slows tasks down and raises fuel burn.

    condition_rating is derived from age only and held constant across the
    history window, so there is no circular dependency with accumulated hours.
    """
    rows = []
    for i in range(1, C.N_MACHINES + 1):
        machine_type = C.MACHINE_TYPES[(i - 1) % len(C.MACHINE_TYPES)]
        age = rng.randint(*C.MACHINE_AGE_RANGE_YEARS)
        hours_per_year = rng.randint(*C.MACHINE_START_HOURS_PER_YEAR)

        condition = _clamp(
            1.0 - C.AGE_CONDITION_DECAY * age + rng.gauss(0, C.CONDITION_NOISE),
            *C.CONDITION_RANGE,
        )
        cap_low, cap_high = C.MACHINE_CAPACITY_UNITS[machine_type]

        rows.append({
            "machine_id": f"M{i:03d}",
            "machine_type": machine_type,
            "model": f"CAT {rng.choice(C.MACHINE_MODELS[machine_type])}",
            "year_manufactured": reference.year - age,
            "age_years": age,
            # placeholder; replaced with the final telemetry reading below
            "engine_hours": _round(age * hours_per_year, 1),
            "condition_rating": _round(condition, 3),
            "capacity_units": _round(rng.uniform(cap_low, cap_high), 1),
            "home_zone": rng.choice(C.SITE_ZONES),
            C.SYNTHETIC_MARKER_COLUMN: C.SYNTHETIC_MARKER,
        })
    return rows


# ---------------------------------------------------------------------------
# duration model
# ---------------------------------------------------------------------------

def _work_minutes(task_type: str, quantity: float, difficulty: int) -> float:
    """Baseline work content, before operator/machine/weather effects."""
    rate = C.TASK_TYPES[task_type]["rate_per_unit"]
    difficulty_multiplier = 1.0 + C.DIFFICULTY_STEP * (difficulty - 1)
    return quantity * rate * difficulty_multiplier


def _estimated_minutes(rng: random.Random, task_type: str, quantity: float,
                       difficulty: int) -> float:
    """
    The planner's pre-task estimate. Deliberately blind to operator skill and
    weather - that gap is what a trained model can close.
    """
    base = _work_minutes(task_type, quantity, difficulty)
    noise = rng.uniform(C.ESTIMATE_NOISE_MIN, C.ESTIMATE_NOISE_MAX)
    return max(C.MIN_TASK_MINUTES, base * noise + C.ESTIMATE_SETUP_MINUTES)


def _actual_minutes(rng: random.Random, task_type: str, quantity: float,
                    difficulty: int, skill: str, condition: float,
                    terrain: str, env: dict, shift: str) -> float:
    """Observed duration. Every factor below is documented in config.py."""
    minutes = _work_minutes(task_type, quantity, difficulty)
    minutes *= C.SKILL_MULTIPLIER[skill]
    minutes *= 1.0 + C.CONDITION_PENALTY * (1.0 - condition)
    minutes *= C.TERRAIN_MULTIPLIER[terrain]
    minutes *= _weather_multiplier(env)
    if shift == "NIGHT":
        minutes *= C.NIGHT_SHIFT_MULTIPLIER
    minutes *= _bounded_noise(rng)
    minutes += rng.randint(*C.SETUP_MINUTES_RANGE)
    return max(C.MIN_TASK_MINUTES, minutes)


def _start_datetime(rng: random.Random, day: date, shift: str) -> datetime:
    low, high = C.SHIFTS[shift]
    hour = rng.randint(low, high - 1)
    minute = rng.choice([0, 15, 30, 45])
    return datetime(day.year, day.month, day.day) + timedelta(hours=hour, minutes=minute)


# ---------------------------------------------------------------------------
# pending tasks (forward-looking backlog)
# ---------------------------------------------------------------------------

def generate_tasks(rng: random.Random, reference: date) -> list[dict]:
    """
    The planned backlog the optimizer and dashboards work from.

    task_id range T001.. is disjoint from the historical range (T1001..), so
    nothing in this file appears in task_history.
    """
    rows = []
    zone_tasks: dict[str, list[str]] = {zone: [] for zone in C.SITE_ZONES}

    for i in range(1, C.N_PENDING_TASKS + 1):
        task_type = rng.choice(sorted(C.TASK_TYPES.keys()))
        spec = C.TASK_TYPES[task_type]
        quantity = rng.randint(*spec["qty_range"])
        difficulty = _weighted(rng, C.DIFFICULTY_LEVELS, C.DIFFICULTY_WEIGHTS)
        priority = _weighted(rng, C.PRIORITIES, C.PRIORITY_WEIGHTS)
        terrain = _weighted(rng, C.TERRAINS, C.TERRAIN_WEIGHTS)
        zone = rng.choice(C.SITE_ZONES)

        # Business value rises with priority and with the amount of work.
        priority_weight = {"LOW": 1.0, "MEDIUM": 1.8, "HIGH": 3.0, "CRITICAL": 4.5}[priority]
        value = 200 * priority_weight + quantity * 3.0 * priority_weight * 0.25
        value *= rng.uniform(0.85, 1.15)

        # Dependencies point at an earlier task in the same zone only, which
        # keeps the graph acyclic by construction.
        depends_on = ""
        if zone_tasks[zone] and rng.random() < 0.15:
            depends_on = rng.choice(zone_tasks[zone])

        task_id = f"T{i:03d}"
        zone_tasks[zone].append(task_id)

        rows.append({
            "task_id": task_id,
            "task_type": task_type,
            "difficulty": difficulty,
            "quantity": quantity,
            "quantity_unit": spec["unit"],
            "required_machine_type": spec["machine_type"],
            "required_certification": C.MACHINE_TYPE_CERT[spec["machine_type"]],
            "priority": priority,
            "business_value": int(round(value)),
            "depends_on_task_id": depends_on,
            "site_zone": zone,
            "terrain": terrain,
            "estimated_minutes": int(round(_estimated_minutes(rng, task_type, quantity, difficulty))),
            "status": _weighted(rng, C.TASK_STATUSES, C.TASK_STATUS_WEIGHTS),
            "shift_date": (reference + timedelta(days=rng.randint(0, C.PLANNING_DAYS - 1))).isoformat(),
            C.SYNTHETIC_MARKER_COLUMN: C.SYNTHETIC_MARKER,
        })
    return rows


# ---------------------------------------------------------------------------
# task history + telemetry + safety events
# ---------------------------------------------------------------------------

def _pick_machine(rng: random.Random, machines: list[dict], machine_type: str) -> dict:
    candidates = [m for m in machines if m["machine_type"] == machine_type]
    return rng.choice(candidates)


def _pick_operator(rng: random.Random, operators: list[dict], required_cert: str):
    """
    Normally assign a certified operator. Rarely (P_UNCERTIFIED_ASSIGNMENT)
    assign one without the certification, which the safety rules then detect.
    """
    certified = [o for o in operators if required_cert in o["certifications"].split("|")]
    uncertified = [o for o in operators if required_cert not in o["certifications"].split("|")]

    if uncertified and rng.random() < C.P_UNCERTIFIED_ASSIGNMENT:
        return rng.choice(uncertified), False
    if certified:
        return rng.choice(certified), True
    return rng.choice(operators), False


def _telemetry_for(rng: random.Random, history: dict, machine: dict,
                   engine_hours_reading: float) -> dict:
    """
    Machine telemetry for one completed execution.

    Fuel, load cycles and idle time are all derived from the same execution
    facts, so the dataset holds real structure for anomaly detection rather
    than independent noise.
    """
    runtime = history["actual_minutes"]
    machine_type = machine["machine_type"]
    condition = machine["condition_rating"]

    injected = ""
    if rng.random() < C.P_INJECTED_ANOMALY:
        injected = _weighted(rng, C.ANOMALY_TYPES, C.ANOMALY_WEIGHTS)

    # --- idle -------------------------------------------------------------
    if injected == "EXCESSIVE_IDLING":
        idle_ratio = rng.uniform(*C.ANOMALY_IDLE_RATIO)
    else:
        idle_ratio = rng.uniform(*C.IDLE_RATIO_NORMAL)
    idle_ratio = _clamp(idle_ratio, *C.IDLE_RATIO_BOUNDS)
    idle_minutes = runtime * idle_ratio
    working_minutes = runtime - idle_minutes

    # --- load -------------------------------------------------------------
    avg_load = _clamp(rng.uniform(*C.AVG_LOAD_PCT_NORMAL), *C.AVG_LOAD_PCT_BOUNDS)
    if injected == "LOAD_CYCLE_ANOMALY":
        load_variance = rng.uniform(*C.ANOMALY_LOAD_VARIANCE)
    else:
        load_variance = rng.uniform(*C.LOAD_VARIANCE_NORMAL)

    cycles_per_unit = C.LOAD_CYCLES_PER_UNIT[history["quantity_unit"]]
    load_cycles = history["quantity"] * cycles_per_unit * rng.uniform(*C.LOAD_CYCLE_NOISE)
    if injected == "LOAD_CYCLE_ANOMALY":
        load_cycles *= rng.uniform(*C.ANOMALY_LOAD_CYCLE_FACTOR)
    load_cycles = max(1, int(round(load_cycles)))

    # --- fuel -------------------------------------------------------------
    base_lph = C.FUEL_LPH_BY_TYPE[machine_type]
    load_factor = C.FUEL_LOAD_FLOOR + (1.0 - C.FUEL_LOAD_FLOOR) * (avg_load / 100.0)
    wear_factor = 1.0 + C.FUEL_CONDITION_PENALTY * (1.0 - condition)
    fuel = base_lph * (working_minutes / 60.0) * load_factor * wear_factor
    fuel += base_lph * C.FUEL_IDLE_FRACTION * (idle_minutes / 60.0) * wear_factor
    if injected == "FUEL_ANOMALY":
        fuel *= rng.uniform(*C.ANOMALY_FUEL_FACTOR)
    fuel = max(0.1, fuel * rng.uniform(0.95, 1.05))

    # --- temperature / pressure ------------------------------------------
    if injected == "OVERHEATING":
        engine_temp = rng.uniform(*C.ANOMALY_ENGINE_TEMP_C)
    else:
        engine_temp = rng.uniform(*C.ENGINE_TEMP_NORMAL_C) + (avg_load - 65.0) * 0.08
    engine_temp = _clamp(engine_temp, *C.ENGINE_TEMP_BOUNDS_C)

    hydraulic = _clamp(
        rng.uniform(*C.HYDRAULIC_PRESSURE_NORMAL_PSI) * (0.92 + 0.12 * condition),
        *C.HYDRAULIC_PRESSURE_BOUNDS_PSI,
    )

    # --- safety-relevant observables -------------------------------------
    if rng.random() < C.P_SEATBELT_LAPSE:
        seatbelt_pct = rng.uniform(*C.SEATBELT_LAPSE_PCT)
    else:
        seatbelt_pct = C.SEATBELT_NORMAL_PCT

    if rng.random() < C.P_CLOSE_PROXIMITY:
        min_proximity = rng.uniform(*C.PROXIMITY_CLOSE_M)
        proximity_alerts = rng.randint(1, 4)
    else:
        min_proximity = rng.uniform(*C.PROXIMITY_NORMAL_M)
        proximity_alerts = 0

    if rng.random() < C.P_OVERSPEED:
        max_speed = rng.uniform(*C.OVERSPEED_KPH)
    else:
        max_speed = rng.uniform(*C.MAX_SPEED_NORMAL_KPH)

    return {
        "telemetry_id": "",                      # assigned by the caller
        "history_id": history["history_id"],
        "task_id": history["task_id"],
        "machine_id": machine["machine_id"],
        "operator_id": history["operator_id"],
        "recorded_at": history["completed_at"],
        "engine_hours_reading": _round(engine_hours_reading, 1),
        "runtime_minutes": _round(runtime, 1),
        "idle_minutes": _round(idle_minutes, 1),
        "idle_ratio": _round(idle_ratio, 3),
        "fuel_used_liters": _round(fuel, 2),
        "fuel_per_unit": _round(fuel / max(1.0, history["quantity"]), 4),
        "load_cycles": load_cycles,
        "avg_load_pct": _round(avg_load, 1),
        "load_variance": _round(load_variance, 2),
        "engine_temp_c": _round(engine_temp, 1),
        "hydraulic_pressure_psi": _round(hydraulic, 0),
        "max_speed_kph": _round(max_speed, 1),
        "seatbelt_fastened_pct": _round(seatbelt_pct, 1),
        "min_proximity_m": _round(min_proximity, 2),
        "proximity_alerts_count": proximity_alerts,
        "injected_anomaly_type": injected,
        C.SYNTHETIC_MARKER_COLUMN: C.SYNTHETIC_MARKER,
    }


def _safety_events_for(telemetry: dict, certified: bool, next_index: int) -> list[dict]:
    """
    Derive safety events from observable telemetry thresholds.

    This is data generation, not the Module 4 safety engine: it produces the
    historical safety_events records. Descriptions state only the observed
    condition.
    """
    events = []

    def add(event_type: str, severity: str):
        nonlocal next_index
        events.append({
            "event_id": f"SE{next_index:04d}",
            "timestamp": telemetry["recorded_at"],
            "operator_id": telemetry["operator_id"],
            "machine_id": telemetry["machine_id"],
            "task_id": telemetry["task_id"],
            "history_id": telemetry["history_id"],
            "event_type": event_type,
            "severity": severity,
            "description": C.EVENT_DESCRIPTIONS[event_type],
            C.SYNTHETIC_MARKER_COLUMN: C.SYNTHETIC_MARKER,
        })
        next_index += 1

    seatbelt = telemetry["seatbelt_fastened_pct"]
    if seatbelt < C.SEATBELT_THRESHOLD_PCT:
        if seatbelt < C.SEATBELT_HIGH_PCT:
            add("SEATBELT", "HIGH")
        elif seatbelt < C.SEATBELT_MEDIUM_PCT:
            add("SEATBELT", "MEDIUM")
        else:
            add("SEATBELT", "LOW")

    proximity = telemetry["min_proximity_m"]
    if proximity < C.PROXIMITY_THRESHOLD_M:
        if proximity < C.PROXIMITY_HIGH_M:
            add("PROXIMITY", "HIGH")
        elif proximity < C.PROXIMITY_MEDIUM_M:
            add("PROXIMITY", "MEDIUM")
        else:
            add("PROXIMITY", "LOW")

    speed = telemetry["max_speed_kph"]
    if speed > C.SPEED_LIMIT_KPH:
        if speed > C.OVERSPEED_HIGH_KPH:
            add("OVERSPEED", "HIGH")
        elif speed > C.OVERSPEED_MEDIUM_KPH:
            add("OVERSPEED", "MEDIUM")
        else:
            add("OVERSPEED", "LOW")

    if telemetry["idle_ratio"] > C.IDLE_EVENT_THRESHOLD:
        severity = "MEDIUM" if telemetry["idle_ratio"] > C.IDLE_EVENT_MEDIUM else "LOW"
        add("EXCESSIVE_IDLING", severity)

    if not certified:
        add("UNCERTIFIED_OPERATION", "HIGH")

    return events


def generate_history(rng: random.Random, operators: list[dict],
                     machines: list[dict], reference: date):
    """
    Generate completed task executions, their telemetry, and the safety
    events those telemetry readings imply.

    Returns (task_history, telemetry, safety_events).
    """
    history_rows: list[dict] = []
    telemetry_rows: list[dict] = []
    safety_rows: list[dict] = []

    # Engine hours accumulate per machine in chronological order.
    engine_hours = {m["machine_id"]: float(m["engine_hours"]) for m in machines}
    by_machine = {m["machine_id"]: m for m in machines}

    # Build executions first so they can be sorted by time before telemetry
    # readings are accumulated.
    draft: list[dict] = []
    for i in range(1, C.N_HISTORY + 1):
        task_type = rng.choice(sorted(C.TASK_TYPES.keys()))
        spec = C.TASK_TYPES[task_type]
        quantity = rng.randint(*spec["qty_range"])
        difficulty = _weighted(rng, C.DIFFICULTY_LEVELS, C.DIFFICULTY_WEIGHTS)
        terrain = _weighted(rng, C.TERRAINS, C.TERRAIN_WEIGHTS)
        priority = _weighted(rng, C.PRIORITIES, C.PRIORITY_WEIGHTS)

        machine = _pick_machine(rng, machines, spec["machine_type"])
        required_cert = C.MACHINE_TYPE_CERT[spec["machine_type"]]
        operator, certified = _pick_operator(rng, operators, required_cert)

        shift = operator["primary_shift"]
        day = reference - timedelta(days=rng.randint(1, C.HISTORY_DAYS))
        started_at = _start_datetime(rng, day, shift)

        env = _make_environment(rng)
        actual = _actual_minutes(
            rng, task_type, quantity, difficulty, operator["skill_level"],
            machine["condition_rating"], terrain, env, shift,
        )
        estimated = _estimated_minutes(rng, task_type, quantity, difficulty)

        priority_weight = {"LOW": 1.0, "MEDIUM": 1.8, "HIGH": 3.0, "CRITICAL": 4.5}[priority]
        value = (200 * priority_weight + quantity * 3.0 * priority_weight * 0.25) * rng.uniform(0.85, 1.15)

        draft.append({
            "history_id": "",                       # assigned after sorting
            "task_id": f"T{1000 + i}",              # disjoint from the backlog
            "operator_id": operator["operator_id"],
            "machine_id": machine["machine_id"],
            "task_type": task_type,
            "difficulty": difficulty,
            "quantity": quantity,
            "quantity_unit": spec["unit"],
            "required_machine_type": spec["machine_type"],
            "terrain": terrain,
            "priority": priority,
            "business_value": int(round(value)),
            "shift": shift,
            "started_at": started_at,
            "temperature": env["temperature"],
            "rainfall": env["rainfall"],
            "humidity": env["humidity"],
            "wind_speed": env["wind_speed"],
            "visibility": env["visibility"],
            "weather": env["weather"],
            "estimated_minutes": int(round(estimated)),
            "actual_minutes": _round(actual, 1),
            "_certified": certified,
        })

    draft.sort(key=lambda r: r["started_at"])

    # Pass 1: assign ids and timestamps in start order.
    certified_by_history = {}
    for index, row in enumerate(draft, start=1):
        certified_by_history[f"TH{index:05d}"] = row.pop("_certified")
        started_at = row["started_at"]
        completed_at = started_at + timedelta(minutes=row["actual_minutes"])

        row["history_id"] = f"TH{index:05d}"
        row["started_at"] = _iso(started_at)
        row["completed_at"] = _iso(completed_at)
        row["shift_date"] = started_at.date().isoformat()
        row[C.SYNTHETIC_MARKER_COLUMN] = C.SYNTHETIC_MARKER
        history_rows.append(row)

    # Pass 2: accumulate engine hours in COMPLETION order, because the reading
    # is taken when the task finishes. A long task that started earlier can
    # finish after a short one that started later, so accumulating in start
    # order would make the readings go backwards in time.
    reading_at_completion = {}
    for row in sorted(history_rows, key=lambda r: r["completed_at"]):
        engine_hours[row["machine_id"]] += row["actual_minutes"] / 60.0
        reading_at_completion[row["history_id"]] = engine_hours[row["machine_id"]]

    # Pass 3: telemetry and the safety events its readings imply.
    for index, row in enumerate(history_rows, start=1):
        machine = by_machine[row["machine_id"]]
        telemetry = _telemetry_for(rng, row, machine, reading_at_completion[row["history_id"]])
        telemetry["telemetry_id"] = f"TM{index:05d}"
        telemetry_rows.append(telemetry)

        events = _safety_events_for(
            telemetry, certified_by_history[row["history_id"]], len(safety_rows) + 1
        )
        safety_rows.extend(events)

    # Publish the final accumulated reading as each machine's current hours.
    for machine in machines:
        machine["engine_hours"] = _round(engine_hours[machine["machine_id"]], 1)

    return history_rows, telemetry_rows, safety_rows


# ---------------------------------------------------------------------------
# output
# ---------------------------------------------------------------------------

# Fixed column order per dataset. Keeps CSVs stable and diffable.
COLUMNS = {
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


def write_csv(path: str, rows: list[dict], columns: list[str]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row[key] for key in columns})


def _sha256(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def generate_all(out_dir: str = C.OUTPUT_DIR, seed: int = C.SEED) -> dict:
    """
    Generate every dataset and write it to out_dir.

    Returns the manifest dict (also written as manifest.json).
    """
    rng = random.Random(seed)
    reference = date.fromisoformat(C.REFERENCE_DATE)

    operators = generate_operators(rng)
    machines = generate_machines(rng, reference)
    tasks = generate_tasks(rng, reference)
    history, telemetry, safety_events = generate_history(rng, operators, machines, reference)

    datasets = {
        "operators": operators,
        "machines": machines,
        "tasks": tasks,
        "task_history": history,
        "telemetry": telemetry,
        "safety_events": safety_events,
    }

    os.makedirs(out_dir, exist_ok=True)
    files = {}
    for name in C.DATASETS:
        path = os.path.join(out_dir, f"{name}.csv")
        write_csv(path, datasets[name], COLUMNS[name])
        files[f"{name}.csv"] = {
            "rows": len(datasets[name]),
            "columns": len(COLUMNS[name]),
            "sha256": _sha256(path),
        }

    manifest = {
        "project": "CAT Smart Operator Assistant",
        "module": "Module 1 - Synthetic Data Generation",
        "data_source": C.SYNTHETIC_MARKER,
        "disclaimer": (
            "SYNTHETIC DATA. Generated for a hackathon prototype. This is not "
            "real Caterpillar operational data and must not be presented as such."
        ),
        "seed": seed,
        "reference_date": C.REFERENCE_DATE,
        "generator": "scripts/data_generation/generate.py",
        "files": files,
    }
    with open(os.path.join(out_dir, C.MANIFEST_FILENAME), "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2)
        handle.write("\n")

    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate synthetic CAT operator data.")
    parser.add_argument("--out", default=C.OUTPUT_DIR, help="output directory")
    parser.add_argument("--seed", type=int, default=C.SEED, help="random seed")
    args = parser.parse_args()

    manifest = generate_all(args.out, args.seed)

    print(f"SYNTHETIC DATA generated with seed={manifest['seed']} -> {args.out}")
    for name, info in manifest["files"].items():
        print(f"  {name:22s} {info['rows']:6d} rows x {info['columns']:2d} cols")


if __name__ == "__main__":
    main()

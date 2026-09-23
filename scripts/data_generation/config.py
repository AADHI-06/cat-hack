"""
Configuration for synthetic data generation.

All tunable constants live here so the whole team can see, in one place, what
drives the generated data. Every relationship encoded below is documented in
docs/synthetic_data.md.

SYNTHETIC DATA ONLY. Nothing here describes real Caterpillar machines,
operators or operations.
"""

# ---------------------------------------------------------------------------
# Reproducibility
# ---------------------------------------------------------------------------

SEED = 42

# Value written to the `data_source` column of every generated record.
# Matches the marker already used by backend/app/main.py.
SYNTHETIC_MARKER = "synthetic"
SYNTHETIC_MARKER_COLUMN = "data_source"

# ---------------------------------------------------------------------------
# Dataset sizes - sized for a hackathon prototype, not production
# ---------------------------------------------------------------------------

N_OPERATORS = 40
N_MACHINES = 25
N_PENDING_TASKS = 200      # forward-looking backlog for the optimizer/dashboards
N_HISTORY = 3000           # completed executions - the ML training set

# ---------------------------------------------------------------------------
# Time window
# ---------------------------------------------------------------------------

# "Today" for the generated world. Fixed so output stays reproducible.
REFERENCE_DATE = "2026-09-23"

HISTORY_DAYS = 180         # history spans the 180 days before REFERENCE_DATE
PLANNING_DAYS = 3          # pending tasks are scheduled across 3 upcoming days

SHIFT_MINUTES = 480        # 8-hour shift capacity

SHIFTS = {
    # shift name -> (earliest start hour, latest start hour)
    "DAY": (6, 12),
    "NIGHT": (22, 28),     # 28 == 04:00 next day
}

# ---------------------------------------------------------------------------
# Categorical vocabularies
# ---------------------------------------------------------------------------

SKILL_LEVELS = ["BEGINNER", "INTERMEDIATE", "EXPERT"]
SKILL_WEIGHTS = [0.25, 0.45, 0.30]

MACHINE_TYPES = ["EXCAVATOR", "DOZER", "LOADER", "HAUL_TRUCK", "GRADER"]

# Plausible CAT-style model designations. Synthetic, illustrative only.
MACHINE_MODELS = {
    "EXCAVATOR": ["320", "325", "336"],
    "DOZER": ["D5", "D6", "D8"],
    "LOADER": ["950", "966", "980"],
    "HAUL_TRUCK": ["770", "773", "777"],
    "GRADER": ["120", "140", "150"],
}

TERRAINS = ["FLAT", "SLOPED", "ROUGH"]
TERRAIN_WEIGHTS = [0.50, 0.30, 0.20]

PRIORITIES = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
# Logical distribution: most work is routine, critical work is rare.
PRIORITY_WEIGHTS = [0.22, 0.46, 0.25, 0.07]

SITE_ZONES = ["ZONE_A", "ZONE_B", "ZONE_C", "ZONE_D"]

TASK_STATUSES = ["PENDING", "IN_PROGRESS", "COMPLETED", "BLOCKED"]
TASK_STATUS_WEIGHTS = [0.70, 0.08, 0.16, 0.06]

WEATHER_CONDITIONS = ["CLEAR", "CLOUDY", "RAIN", "HEAVY_RAIN", "FOG"]

CERTIFICATIONS = [
    "EXCAVATOR_OP",
    "DOZER_OP",
    "LOADER_OP",
    "HAUL_TRUCK_OP",
    "GRADER_OP",
    "CONFINED_SPACE",
    "BLASTING_AWARE",
]

# Certification required to operate each machine type.
MACHINE_TYPE_CERT = {
    "EXCAVATOR": "EXCAVATOR_OP",
    "DOZER": "DOZER_OP",
    "LOADER": "LOADER_OP",
    "HAUL_TRUCK": "HAUL_TRUCK_OP",
    "GRADER": "GRADER_OP",
}

# ---------------------------------------------------------------------------
# Task types
#   rate_per_unit : baseline minutes of work per unit of quantity
#   unit          : unit of measure for `quantity`
#   machine_type  : machine type the task requires
#   qty_range     : inclusive quantity range
# ---------------------------------------------------------------------------

TASK_TYPES = {
    "EXCAVATION":    {"rate_per_unit": 1.8, "unit": "m3",    "machine_type": "EXCAVATOR",  "qty_range": (20, 160)},
    "TRENCHING":     {"rate_per_unit": 2.6, "unit": "m",     "machine_type": "EXCAVATOR",  "qty_range": (15, 90)},
    "LOADING":       {"rate_per_unit": 1.2, "unit": "loads", "machine_type": "LOADER",     "qty_range": (30, 180)},
    "HAULING":       {"rate_per_unit": 3.5, "unit": "trips", "machine_type": "HAUL_TRUCK", "qty_range": (10, 70)},
    "GRADING":       {"rate_per_unit": 0.9, "unit": "m2",    "machine_type": "GRADER",     "qty_range": (60, 400)},
    "BACKFILL":      {"rate_per_unit": 1.4, "unit": "m3",    "machine_type": "DOZER",      "qty_range": (25, 150)},
    "SITE_CLEARING": {"rate_per_unit": 1.1, "unit": "m2",    "machine_type": "DOZER",      "qty_range": (80, 350)},
}

# ---------------------------------------------------------------------------
# Duration model multipliers
#
# actual_minutes = quantity * rate_per_unit
#                  * difficulty * skill * machine_condition * terrain
#                  * weather * shift
#                  * bounded_noise
#                + setup_minutes
# ---------------------------------------------------------------------------

DIFFICULTY_LEVELS = [1, 2, 3, 4, 5]
DIFFICULTY_WEIGHTS = [0.14, 0.26, 0.31, 0.19, 0.10]

# difficulty 1..5 -> 1.00, 1.15, 1.30, 1.45, 1.60  (harder => longer)
DIFFICULTY_STEP = 0.15

# Less experience => longer duration.
SKILL_MULTIPLIER = {
    "BEGINNER": 1.30,
    "INTERMEDIATE": 1.10,
    "EXPERT": 0.95,
}

TERRAIN_MULTIPLIER = {
    "FLAT": 1.00,
    "SLOPED": 1.08,
    "ROUGH": 1.18,
}

NIGHT_SHIFT_MULTIPLIER = 1.06

# A machine in poorer condition works more slowly.
# multiplier = 1 + CONDITION_PENALTY * (1 - condition_rating)
CONDITION_PENALTY = 0.35

# Weather effects, applied from the observed environment values.
RAINFALL_PENALTY_PER_MM = 0.008   # capped by RAINFALL_PENALTY_CAP_MM
RAINFALL_PENALTY_CAP_MM = 25.0
LOW_VISIBILITY_KM = 5.0
POOR_VISIBILITY_KM = 2.0
LOW_VISIBILITY_MULTIPLIER = 1.05
POOR_VISIBILITY_MULTIPLIER = 1.12
HIGH_WIND_KPH = 30.0
HIGH_WIND_MULTIPLIER = 1.06
HOT_TEMPERATURE_C = 38.0
HOT_MULTIPLIER = 1.07
COLD_TEMPERATURE_C = 8.0
COLD_MULTIPLIER = 1.04

# Bounded random variation, so relationships are not perfectly deterministic.
NOISE_SIGMA = 0.08
NOISE_MIN = 0.85
NOISE_MAX = 1.20

SETUP_MINUTES_RANGE = (8, 20)
MIN_TASK_MINUTES = 5          # hard floor - never emit implausibly short work

# The planner's pre-task estimate ignores skill and weather, which is exactly
# why a model trained on history can beat it.
ESTIMATE_NOISE_MIN = 0.92
ESTIMATE_NOISE_MAX = 1.08
ESTIMATE_SETUP_MINUTES = 12

# ---------------------------------------------------------------------------
# Environment ranges (physically possible values only)
# ---------------------------------------------------------------------------

TEMPERATURE_RANGE_C = (5.0, 45.0)
HUMIDITY_RANGE_PCT = (20.0, 98.0)
WIND_SPEED_RANGE_KPH = (0.0, 45.0)
VISIBILITY_RANGE_KM = (0.5, 10.0)
RAINFALL_RANGE_MM = (0.0, 40.0)

# Probability that a task execution sees any rain at all.
P_RAIN = 0.22

# ---------------------------------------------------------------------------
# Machines
# ---------------------------------------------------------------------------

MACHINE_AGE_RANGE_YEARS = (0, 14)
MACHINE_START_HOURS_PER_YEAR = (900, 1600)

# condition_rating = 1 - AGE_CONDITION_DECAY * age_years + noise, clamped
AGE_CONDITION_DECAY = 0.030
CONDITION_NOISE = 0.05
CONDITION_RANGE = (0.55, 1.00)

MACHINE_CAPACITY_UNITS = {
    "EXCAVATOR": (1.0, 3.5),
    "DOZER": (3.0, 9.0),
    "LOADER": (2.5, 6.5),
    "HAUL_TRUCK": (36.0, 100.0),
    "GRADER": (3.0, 5.0),
}

# ---------------------------------------------------------------------------
# Operators
# ---------------------------------------------------------------------------

EXPERIENCE_YEARS_BY_SKILL = {
    "BEGINNER": (0, 2),
    "INTERMEDIATE": (3, 8),
    "EXPERT": (9, 25),
}

# How many machine-type certifications an operator holds, by skill level.
N_MACHINE_CERTS_BY_SKILL = {
    "BEGINNER": (1, 1),
    "INTERMEDIATE": (1, 3),
    "EXPERT": (2, 5),
}

P_EXTRA_CERT = {           # non-machine certifications
    "BEGINNER": 0.10,
    "INTERMEDIATE": 0.35,
    "EXPERT": 0.60,
}

# ---------------------------------------------------------------------------
# Telemetry
# ---------------------------------------------------------------------------

# Normal operating ranges.
IDLE_RATIO_NORMAL = (0.05, 0.25)
AVG_LOAD_PCT_NORMAL = (45.0, 85.0)
LOAD_VARIANCE_NORMAL = (3.0, 12.0)
ENGINE_TEMP_NORMAL_C = (78.0, 98.0)
HYDRAULIC_PRESSURE_NORMAL_PSI = (2200.0, 3400.0)

# Physical bounds - values are clamped into these, never outside.
IDLE_RATIO_BOUNDS = (0.0, 0.95)
ENGINE_TEMP_BOUNDS_C = (60.0, 120.0)
HYDRAULIC_PRESSURE_BOUNDS_PSI = (1500.0, 4200.0)
AVG_LOAD_PCT_BOUNDS = (0.0, 100.0)

# Baseline fuel burn under load, litres per engine hour, by machine type.
FUEL_LPH_BY_TYPE = {
    "EXCAVATOR": 18.0,
    "DOZER": 24.0,
    "LOADER": 20.0,
    "HAUL_TRUCK": 32.0,
    "GRADER": 16.0,
}
FUEL_IDLE_FRACTION = 0.25      # idling burns 25% of the loaded rate
FUEL_LOAD_FLOOR = 0.45         # burn at 0% load is 45% of the loaded rate
FUEL_CONDITION_PENALTY = 0.25  # worn machines burn more

# Load cycles scale with the amount of work moved.
LOAD_CYCLES_PER_UNIT = {
    "m3": 0.9,
    "m": 0.5,
    "loads": 1.0,
    "trips": 1.0,
    "m2": 0.25,
}
LOAD_CYCLE_NOISE = (0.85, 1.15)

SPEED_LIMIT_KPH = 25.0         # site speed limit used by the overspeed rule
MAX_SPEED_NORMAL_KPH = (8.0, 24.0)

# ---------------------------------------------------------------------------
# Injected machine anomalies
#
# Ground truth for Module 5 to find. Recorded in the
# `injected_anomaly_type` column, which is documentation and validation
# material - NOT a model feature.
# ---------------------------------------------------------------------------

P_INJECTED_ANOMALY = 0.05

ANOMALY_TYPES = [
    "EXCESSIVE_IDLING",
    "FUEL_ANOMALY",
    "LOAD_CYCLE_ANOMALY",
    "OVERHEATING",
]
ANOMALY_WEIGHTS = [0.35, 0.28, 0.20, 0.17]

ANOMALY_IDLE_RATIO = (0.40, 0.70)
ANOMALY_FUEL_FACTOR = (1.50, 2.20)
ANOMALY_LOAD_CYCLE_FACTOR = (0.35, 0.60)
ANOMALY_LOAD_VARIANCE = (18.0, 34.0)
ANOMALY_ENGINE_TEMP_C = (105.0, 118.0)

# ---------------------------------------------------------------------------
# Safety conditions
#
# Safety events are DERIVED from these observable telemetry thresholds, so
# every event traces back to a measurable condition. Rates are deliberately
# low: safety events must be rare to be meaningful.
# ---------------------------------------------------------------------------

# Seatbelt: fastened share of runtime.
P_SEATBELT_LAPSE = 0.030
SEATBELT_NORMAL_PCT = 100.0
SEATBELT_LAPSE_PCT = (60.0, 94.0)
SEATBELT_THRESHOLD_PCT = 95.0
SEATBELT_MEDIUM_PCT = 85.0
SEATBELT_HIGH_PCT = 70.0

# Proximity: closest detected object during the task, in metres.
P_CLOSE_PROXIMITY = 0.025
PROXIMITY_NORMAL_M = (4.0, 15.0)
PROXIMITY_CLOSE_M = (0.8, 2.9)
PROXIMITY_THRESHOLD_M = 3.0
PROXIMITY_MEDIUM_M = 2.5
PROXIMITY_HIGH_M = 1.5

# Overspeed.
P_OVERSPEED = 0.020
OVERSPEED_KPH = (25.5, 38.0)
OVERSPEED_MEDIUM_KPH = 30.0
OVERSPEED_HIGH_KPH = 35.0

# Excessive idling raises a safety/efficiency event above this ratio.
IDLE_EVENT_THRESHOLD = 0.35
IDLE_EVENT_MEDIUM = 0.50

# Operating a machine class the operator is not certified for.
P_UNCERTIFIED_ASSIGNMENT = 0.010

# Observable, non-judgemental event wording. Never characterises the operator.
EVENT_DESCRIPTIONS = {
    "SEATBELT": "Seatbelt violation detected",
    "PROXIMITY": "Potential proximity hazard detected",
    "EXCESSIVE_IDLING": "Excessive idling detected",
    "OVERSPEED": "Speed above site limit detected",
    "UNCERTIFIED_OPERATION": "Machine operated outside certified machine class",
}

SEVERITIES = ["LOW", "MEDIUM", "HIGH"]
EVENT_TYPES = list(EVENT_DESCRIPTIONS.keys())

# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

OUTPUT_DIR = "data/generated"

DATASETS = [
    "operators",
    "machines",
    "tasks",
    "task_history",
    "telemetry",
    "safety_events",
]

MANIFEST_FILENAME = "manifest.json"

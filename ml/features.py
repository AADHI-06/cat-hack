"""
Feature definitions and leakage guards for task duration prediction (Module 2).

The feature set is fixed here, in one place, so the leakage decisions are
auditable and testable rather than scattered through the training script.

Every feature below is known BEFORE the task runs and is resolvable at
inference from the task prediction contract's three ids plus `environment`.

SYNTHETIC DATA ONLY. Any metric measured with these features describes
performance on synthetic data and says nothing about real-world Caterpillar
performance.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Target
# ---------------------------------------------------------------------------

TARGET = "actual_minutes"

# Nothing shorter is plausible; matches the generator's floor.
MIN_PREDICTED_MINUTES = 5.0

# Guards against a runaway prediction. The observed maximum in the Module 1
# history is 941 minutes, so this is a generous ceiling, not a tuning knob.
MAX_PREDICTED_MINUTES = 2000.0

# ---------------------------------------------------------------------------
# Features
# ---------------------------------------------------------------------------

# Resolved from tasks(task_id)
TASK_FEATURES = ["task_type", "difficulty", "quantity", "terrain", "estimated_minutes"]

# Resolved from operators(operator_id)
OPERATOR_FEATURES = ["skill_level", "experience_years"]

# Resolved from machines(machine_id)
MACHINE_FEATURES = ["machine_type", "age_years", "condition_rating"]

# Resolved from the contract's `environment` block
ENVIRONMENT_FEATURES = ["temperature", "rainfall", "humidity", "wind_speed", "visibility"]

CATEGORICAL_FEATURES = ["task_type", "terrain", "skill_level", "machine_type"]

NUMERIC_FEATURES = [
    "difficulty",            # ordinal 1-5, used as numeric
    "quantity",
    "estimated_minutes",
    "experience_years",
    "age_years",
    "condition_rating",
    "temperature",
    "rainfall",
    "humidity",
    "wind_speed",
    "visibility",
]

FEATURES = TASK_FEATURES + OPERATOR_FEATURES + MACHINE_FEATURES + ENVIRONMENT_FEATURES

# Ablation variant: same model without the planner's estimate, to measure how
# much the model contributes independently of the incumbent estimate.
FEATURES_NO_ESTIMATE = [f for f in FEATURES if f != "estimated_minutes"]

# ---------------------------------------------------------------------------
# Leakage guards
#
# These lists are asserted in the tests. Adding any of them to FEATURES is a
# test failure, not a silent regression.
# ---------------------------------------------------------------------------

# Known only AFTER the task completes.
POST_COMPLETION_COLUMNS = [
    "actual_minutes",           # the target itself
    "completed_at",
    # telemetry.csv is recorded at completion - the whole table is post-hoc.
    "telemetry_id", "recorded_at", "engine_hours_reading", "runtime_minutes",
    "idle_minutes", "idle_ratio", "fuel_used_liters", "fuel_per_unit",
    "load_cycles", "avg_load_pct", "load_variance", "engine_temp_c",
    "hydraulic_pressure_psi", "max_speed_kph", "seatbelt_fastened_pct",
    "min_proximity_m", "proximity_alerts_count", "injected_anomaly_type",
    # safety_events.csv is derived from that telemetry.
    "event_id", "event_type", "severity", "description",
]

# machines.engine_hours is the FINAL accumulated reading after all history, so
# using it for an earlier task reads a future value. Verified: it equals the
# maximum telemetry reading for 25/25 machines.
TEMPORAL_LEAKAGE_COLUMNS = ["engine_hours"]

# High-cardinality identifiers invite memorisation instead of generalisation.
# They are join keys only.
IDENTIFIER_COLUMNS = [
    "history_id", "task_id", "operator_id", "machine_id", "name",
]

# Used to build the chronological split; never a feature.
SPLIT_ONLY_COLUMNS = ["shift_date", "started_at"]

FORBIDDEN_COLUMNS = (
    POST_COMPLETION_COLUMNS
    + TEMPORAL_LEAKAGE_COLUMNS
    + IDENTIFIER_COLUMNS
    + SPLIT_ONLY_COLUMNS
)

# ---------------------------------------------------------------------------
# Documented exclusions that are NOT leakage
# ---------------------------------------------------------------------------

EXCLUSION_REASONS = {
    # redundant
    "quantity_unit": "determined 1:1 by task_type (7 pairs for 7 task types)",
    "required_machine_type": "identical to the machine's machine_type on all rows",
    "weather": (
        "deterministic function of the five environment values, and NOT a field "
        "in the prediction contract's input - using it would force the serving "
        "layer to replicate a generator rule"
    ),
    "model": "redundant with machine_type",
    "home_zone": "no duration effect",
    "capacity_units": "no duration effect",
    "primary_shift": "not a reliable inference-time representation of the actual shift",
    # dropped by coordinator decision for v1
    "shift": (
        "not available on tasks.csv and not in the contract input; "
        "operators.primary_shift is not a reliable substitute at inference time"
    ),
    # non-causal
    "priority": "the generator applies no duration effect from priority",
    "business_value": "derived from priority x quantity - a noisy proxy for quantity",
    "certifications": "gates whether an operator may run a machine, not how fast",
    # deferred
    "historical_efficiency": "needs an expanding window to avoid leakage - not in v1",
}


def assert_no_leakage(features: list[str]) -> None:
    """
    Fail loudly if a forbidden column reaches the feature set.

    Called by the training script before fitting, so a leaking feature can
    never silently produce a flattering metric.
    """
    forbidden = sorted(set(features) & set(FORBIDDEN_COLUMNS))
    if forbidden:
        raise ValueError(
            f"leakage guard: forbidden columns in feature set: {forbidden}"
        )


def build_preprocessor(features: list[str]):
    """
    ColumnTransformer for the given feature list.

    One-hot for categoricals with handle_unknown="ignore" so an unseen category
    at inference degrades gracefully instead of raising. StandardScaler for
    numerics, which Linear Regression needs and the forest simply ignores.

    Fitted on training data only - the caller must never fit on validation or
    test.
    """
    from sklearn.compose import ColumnTransformer
    from sklearn.preprocessing import OneHotEncoder, StandardScaler

    categorical = [f for f in features if f in CATEGORICAL_FEATURES]
    numeric = [f for f in features if f in NUMERIC_FEATURES]

    return ColumnTransformer(
        transformers=[
            ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), categorical),
            ("num", StandardScaler(), numeric),
        ],
        remainder="drop",
    )

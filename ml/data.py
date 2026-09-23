"""
Data loading and the chronological split for Module 2.

Reads the Module 1 synthetic datasets, joins the operator and machine
attributes the model needs, and splits by date.

Module 1 is read-only here. Nothing in this file writes to data/generated/.

SYNTHETIC DATA ONLY.
"""

from __future__ import annotations

import os

import pandas as pd

DATA_DIR = "data/generated"

# ---------------------------------------------------------------------------
# Chronological split
#
# Hardcoded boundaries, not recomputed quantiles, so the split is reproducible
# across runs and machines. Derived once from the seed-42 Module 1 output at a
# 60/20/20 target and then fixed.
# ---------------------------------------------------------------------------

TRAIN_END = "2026-07-12"     # train  = shift_date <  TRAIN_END
VAL_END = "2026-08-17"       # val    = TRAIN_END <= shift_date < VAL_END
                             # test   = shift_date >= VAL_END

EXPECTED_SPLIT_SIZES = {"train": 1797, "validation": 598, "test": 605}

# Columns taken from each reference table. Deliberately narrow: engine_hours is
# excluded because it is a post-history value (see features.py).
OPERATOR_COLUMNS = ["operator_id", "skill_level", "experience_years"]
MACHINE_COLUMNS = ["machine_id", "machine_type", "age_years", "condition_rating"]

HISTORY_COLUMNS = [
    "history_id", "task_id", "operator_id", "machine_id",
    "task_type", "difficulty", "quantity", "terrain",
    "temperature", "rainfall", "humidity", "wind_speed", "visibility",
    "estimated_minutes", "actual_minutes",
    "shift_date",                      # split only
]


class DataNotGeneratedError(FileNotFoundError):
    """Raised when the Module 1 datasets are missing."""


def _require(path: str) -> str:
    if not os.path.exists(path):
        raise DataNotGeneratedError(
            f"{path} not found. Generate the Module 1 data first:\n"
            f"    python -m scripts.data_generation.generate"
        )
    return path


def load_reference_tables(data_dir: str = DATA_DIR):
    """Load the operators and machines lookups used to enrich a task."""
    operators = pd.read_csv(_require(os.path.join(data_dir, "operators.csv")))
    machines = pd.read_csv(_require(os.path.join(data_dir, "machines.csv")))
    return operators[OPERATOR_COLUMNS], machines[MACHINE_COLUMNS]


def load_tasks(data_dir: str = DATA_DIR) -> pd.DataFrame:
    """Load the pending task backlog (used by inference, not by training)."""
    return pd.read_csv(_require(os.path.join(data_dir, "tasks.csv")))


def load_dataset(data_dir: str = DATA_DIR) -> pd.DataFrame:
    """
    Load task_history joined with the operator and machine attributes.

    Only the columns the model may see are read. telemetry.csv and
    safety_events.csv are never loaded here - both are post-completion.
    """
    history = pd.read_csv(_require(os.path.join(data_dir, "task_history.csv")))
    history = history[HISTORY_COLUMNS]

    operators, machines = load_reference_tables(data_dir)

    frame = history.merge(operators, on="operator_id", how="left", validate="many_to_one")
    frame = frame.merge(machines, on="machine_id", how="left", validate="many_to_one")

    if frame[["skill_level", "machine_type"]].isna().any().any():
        raise ValueError("join produced nulls: an operator or machine id did not resolve")

    return frame


def split_chronologically(frame: pd.DataFrame):
    """
    Split by shift_date: earlier -> train, middle -> validation, latest -> test.

    Chronological rather than random, because the deployment question is
    "predict next week from what we have seen", and because a random split
    would scatter the same period across all three sets.

    Each task appears exactly once in task_history, so no task can straddle
    two splits.
    """
    dates = frame["shift_date"].astype(str)
    train = frame[dates < TRAIN_END].copy()
    validation = frame[(dates >= TRAIN_END) & (dates < VAL_END)].copy()
    test = frame[dates >= VAL_END].copy()
    return train, validation, test


def split_summary(train, validation, test) -> dict:
    """Describe the split for the metadata artifact and the report."""
    total = len(train) + len(validation) + len(test)

    def describe(name, part):
        return {
            "rows": int(len(part)),
            "share": round(len(part) / total, 4),
            "first_date": str(part["shift_date"].min()),
            "last_date": str(part["shift_date"].max()),
        }

    return {
        "strategy": "chronological by shift_date",
        "train_end_exclusive": TRAIN_END,
        "validation_end_exclusive": VAL_END,
        "train": describe("train", train),
        "validation": describe("validation", validation),
        "test": describe("test", test),
    }

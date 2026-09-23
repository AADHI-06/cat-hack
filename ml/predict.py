"""
Module 2 - task duration prediction: inference.

Implements the task prediction contract from docs/contracts.md section 1.

    INPUT   {"task_id", "operator_id", "machine_id",
             "environment": {"temperature", "rainfall", "humidity",
                             "wind_speed", "visibility"}}

    OUTPUT  {"task_id", "predicted_minutes", "lower_bound", "upper_bound"}

Durations are in MINUTES.

This module is a pure function over a loaded model plus the reference tables.
It opens no HTTP connection and no database session. Serving integration
(wiring this into backend/app/) is a later coordinated module - nothing here
belongs to Claude B.

SYNTHETIC DATA ONLY. Predictions come from a model trained on synthetic data.
"""

from __future__ import annotations

import json
import os

import joblib
import pandas as pd

from ml import data as D
from ml import features as F
from ml.training.train_task_duration import (
    IMPORTANCE_FILENAME,
    METADATA_FILENAME,
    MODEL_DIR,
    MODEL_FILENAME,
)

# The five environment keys the contract carries.
ENVIRONMENT_KEYS = F.ENVIRONMENT_FEATURES

CONTRACT_OUTPUT_KEYS = ["task_id", "predicted_minutes", "lower_bound", "upper_bound"]


class ModelNotTrainedError(FileNotFoundError):
    """Raised when the model artifact is missing."""


class UnknownEntityError(KeyError):
    """Raised when a task, operator or machine id does not resolve."""


class InvalidRequestError(ValueError):
    """Raised when the request does not match the contract."""


class TaskDurationPredictor:
    """
    Loads the trained pipeline and resolves contract ids into model features.

    The contract passes ids, not feature vectors, so this class owns the
    lookup: task attributes from tasks.csv, operator attributes from
    operators.csv, machine attributes from machines.csv, and the five
    environment values straight from the request.
    """

    def __init__(self, model, metadata: dict, tasks: pd.DataFrame,
                 operators: pd.DataFrame, machines: pd.DataFrame):
        self.model = model
        self.metadata = metadata
        self.features = metadata["features"]
        self.ratio_lower = metadata["uncertainty"]["ratio_lower"]
        self.ratio_upper = metadata["uncertainty"]["ratio_upper"]

        self._tasks = tasks.set_index("task_id", drop=False)
        self._operators = operators.set_index("operator_id", drop=False)
        self._machines = machines.set_index("machine_id", drop=False)

    # -- loading ----------------------------------------------------------

    @classmethod
    def load(cls, model_dir: str = MODEL_DIR, data_dir: str = D.DATA_DIR):
        model_path = os.path.join(model_dir, MODEL_FILENAME)
        metadata_path = os.path.join(model_dir, METADATA_FILENAME)
        if not os.path.exists(model_path) or not os.path.exists(metadata_path):
            raise ModelNotTrainedError(
                f"model artifact not found in {model_dir}. Train it first:\n"
                f"    python -m ml.training.train_task_duration"
            )
        with open(metadata_path, encoding="utf-8") as handle:
            metadata = json.load(handle)

        operators, machines = D.load_reference_tables(data_dir)
        tasks = D.load_tasks(data_dir)
        return cls(joblib.load(model_path), metadata, tasks, operators, machines)

    # -- request handling -------------------------------------------------

    @staticmethod
    def _validate(request: dict) -> None:
        for key in ("task_id", "operator_id", "machine_id", "environment"):
            if key not in request:
                raise InvalidRequestError(f"missing required field: {key}")
        environment = request["environment"]
        if not isinstance(environment, dict):
            raise InvalidRequestError("environment must be an object")
        for key in ENVIRONMENT_KEYS:
            if key not in environment:
                raise InvalidRequestError(f"missing environment field: {key}")
            try:
                float(environment[key])
            except (TypeError, ValueError):
                raise InvalidRequestError(f"environment.{key} must be numeric") from None

    def _resolve(self, request: dict) -> pd.DataFrame:
        """Turn contract ids + environment into a one-row feature frame."""
        task_id = request["task_id"]
        operator_id = request["operator_id"]
        machine_id = request["machine_id"]

        if task_id not in self._tasks.index:
            raise UnknownEntityError(f"unknown task_id: {task_id}")
        if operator_id not in self._operators.index:
            raise UnknownEntityError(f"unknown operator_id: {operator_id}")
        if machine_id not in self._machines.index:
            raise UnknownEntityError(f"unknown machine_id: {machine_id}")

        task = self._tasks.loc[task_id]
        operator = self._operators.loc[operator_id]
        machine = self._machines.loc[machine_id]

        row = {}
        for name in self.features:
            if name in ENVIRONMENT_KEYS:
                row[name] = float(request["environment"][name])
            elif name in task.index:
                row[name] = task[name]
            elif name in operator.index:
                row[name] = operator[name]
            elif name in machine.index:
                row[name] = machine[name]
            else:
                raise InvalidRequestError(f"feature {name} could not be resolved")
        return pd.DataFrame([row], columns=self.features)

    # -- prediction -------------------------------------------------------

    def predict(self, request: dict) -> dict:
        """
        Predict one task's duration.

        Returns exactly the four contract fields. Guarantees:
            predicted_minutes > 0
            lower_bound > 0
            lower_bound <= predicted_minutes <= upper_bound
        """
        self._validate(request)
        frame = self._resolve(request)

        raw = float(self.model.predict(frame)[0])
        predicted = min(max(raw, F.MIN_PREDICTED_MINUTES), F.MAX_PREDICTED_MINUTES)

        lower = max(predicted * self.ratio_lower, F.MIN_PREDICTED_MINUTES)
        upper = min(predicted * self.ratio_upper, F.MAX_PREDICTED_MINUTES)

        # The contract's example uses whole minutes. Round, then re-clamp so
        # rounding can never invert the ordering.
        predicted_out = int(round(predicted))
        lower_out = min(int(round(lower)), predicted_out)
        upper_out = max(int(round(upper)), predicted_out)
        lower_out = max(lower_out, 1)

        return {
            "task_id": request["task_id"],
            "predicted_minutes": predicted_out,
            "lower_bound": lower_out,
            "upper_bound": upper_out,
        }

    def predict_batch(self, requests: list[dict]) -> list[dict]:
        """Convenience wrapper. Same contract, one result per request."""
        return [self.predict(request) for request in requests]

    # -- explanation ------------------------------------------------------

    def explain(self, model_dir: str = MODEL_DIR, top_n: int = 5) -> list[dict]:
        """
        The model's most important features, for the future AI assistant.

        Deterministic model information - permutation importance measured at
        training time, not an LLM's guess.
        """
        path = os.path.join(model_dir, IMPORTANCE_FILENAME)
        if not os.path.exists(path):
            return []
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)["permutation_importance"][:top_n]


def predict(request: dict, predictor: TaskDurationPredictor) -> dict:
    """Module-level convenience wrapper around TaskDurationPredictor.predict."""
    return predictor.predict(request)

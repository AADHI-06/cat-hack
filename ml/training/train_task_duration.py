"""
Module 2 - task duration prediction: training entrypoint.

Trains and compares:
    Baseline 0  the planner's estimated_minutes (no training - the incumbent)
    Baseline 1  train-mean predictor (the R2 = 0 reference)
    Baseline 2  Linear Regression
    Candidate   RandomForestRegressor

Model selection uses the VALIDATION split only. The test split is scored once,
at the end, and never used for any choice.

Writes to ml/models/:
    task_duration_model.joblib       the fitted pipeline
    task_duration_metadata.json      split, features, metrics, uncertainty
    feature_importance.json          importances + permutation importances

SYNTHETIC DATA ONLY. Every metric below is measured on synthetic data and says
nothing about real-world Caterpillar performance.

Usage
-----
    python -m ml.training.train_task_duration
    python -m ml.training.train_task_duration --data data/generated --out ml/models
"""

from __future__ import annotations

import argparse
import json
import os
import platform
from datetime import datetime, timezone

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.ensemble import RandomForestRegressor
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LinearRegression
from sklearn.metrics import (
    mean_absolute_error,
    mean_absolute_percentage_error,
    mean_squared_error,
    r2_score,
)
from sklearn.pipeline import Pipeline

from ml import data as D
from ml import features as F

SEED = 42

MODEL_DIR = "ml/models"
MODEL_FILENAME = "task_duration_model.joblib"
METADATA_FILENAME = "task_duration_metadata.json"
IMPORTANCE_FILENAME = "feature_importance.json"

# Nominal coverage of the prediction interval.
LOWER_QUANTILE = 0.10
UPPER_QUANTILE = 0.90

# Small grid, searched on validation. Kept deliberately modest: this is a
# prototype, not a hyperparameter study.
RF_GRID = [
    {"n_estimators": n, "max_depth": d, "min_samples_leaf": leaf}
    for n in (200, 400)
    for d in (None, 12, 20)
    for leaf in (1, 2, 4)
]

# The configuration that wins the validation-MAE search is recorded and scored
# in full, but it is NOT the artifact we ship: unpruned trees with
# min_samples_leaf=1 produce a ~65 MB joblib file.
#
# The deployment configuration below was chosen by explicit human decision for
# a ~10x smaller artifact at a measured cost of roughly 0.2 minutes of test
# MAE. Both configurations are trained, scored and written to the metadata so
# the tradeoff stays visible rather than hidden.
DEPLOYMENT_PARAMS = {"n_estimators": 200, "max_depth": None, "min_samples_leaf": 4}

DEPLOYMENT_RATIONALE = (
    "Compact configuration chosen for deployment by human decision: roughly a "
    "10x smaller artifact for a measured test-MAE cost of about 0.2 minutes "
    "(~11 seconds), which is negligible for this prototype and materially "
    "easier to deploy, demo and distribute. The validation-selected "
    "configuration is recorded in full under "
    "models.candidate_random_forest_validation_selected."
)


# ---------------------------------------------------------------------------
# metrics
# ---------------------------------------------------------------------------

def metrics(y_true, y_pred) -> dict:
    """MAE, RMSE, R2 as primary; MAPE as a secondary readable figure."""
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    return {
        "MAE": float(mean_absolute_error(y_true, y_pred)),
        "RMSE": float(np.sqrt(mean_squared_error(y_true, y_pred))),
        "R2": float(r2_score(y_true, y_pred)),
        "MAPE": float(mean_absolute_percentage_error(y_true, y_pred)),
        "n": int(len(y_true)),
    }


def _fmt(name: str, m: dict) -> str:
    return (f"  {name:34s} MAE={m['MAE']:7.2f}  RMSE={m['RMSE']:7.2f}  "
            f"R2={m['R2']:7.4f}  MAPE={m['MAPE'] * 100:6.2f}%  n={m['n']}")


# ---------------------------------------------------------------------------
# models
# ---------------------------------------------------------------------------

def build_linear(feature_list):
    return Pipeline([
        ("preprocess", F.build_preprocessor(feature_list)),
        ("model", LinearRegression()),
    ])


def build_forest(feature_list, params):
    return Pipeline([
        ("preprocess", F.build_preprocessor(feature_list)),
        ("model", RandomForestRegressor(random_state=SEED, n_jobs=-1, **params)),
    ])


def _predict_clipped(pipeline, frame, feature_list):
    """Predictions clipped to a plausible duration range."""
    raw = pipeline.predict(frame[feature_list])
    return np.clip(raw, F.MIN_PREDICTED_MINUTES, F.MAX_PREDICTED_MINUTES)


# ---------------------------------------------------------------------------
# uncertainty
# ---------------------------------------------------------------------------

def calibrate_interval(y_true, y_pred) -> dict:
    """
    Multiplicative residual quantiles from the VALIDATION split.

    ratio_i = actual_i / predicted_i
    q_lo    = P10(ratio),  q_hi = P90(ratio)

    Multiplicative rather than additive because error scales with duration: a
    fixed +/-40 minutes is absurd for a 60-minute task and trivial for a
    900-minute one. It also guarantees lower_bound > 0 whenever the prediction
    is positive.

    The quantiles are clamped so q_lo <= 1 <= q_hi, which makes the interval
    always contain the point prediction.
    """
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    ratios = y_true / np.maximum(y_pred, 1e-9)

    q_lo = float(np.quantile(ratios, LOWER_QUANTILE))
    q_hi = float(np.quantile(ratios, UPPER_QUANTILE))

    return {
        "method": "empirical multiplicative residual quantiles from the validation split",
        "lower_quantile": LOWER_QUANTILE,
        "upper_quantile": UPPER_QUANTILE,
        "nominal_coverage": UPPER_QUANTILE - LOWER_QUANTILE,
        "ratio_lower": min(q_lo, 1.0),
        "ratio_upper": max(q_hi, 1.0),
        "calibrated_on": "validation",
        "validation_ratio_mean": float(ratios.mean()),
    }


def interval_coverage(y_true, y_pred, interval: dict) -> dict:
    """Measured share of actuals falling inside the interval. Honest reporting."""
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    lower = y_pred * interval["ratio_lower"]
    upper = y_pred * interval["ratio_upper"]
    inside = (y_true >= lower) & (y_true <= upper)
    return {
        "nominal": interval["nominal_coverage"],
        "measured": float(inside.mean()),
        "mean_width_minutes": float((upper - lower).mean()),
        "n": int(len(y_true)),
    }


# ---------------------------------------------------------------------------
# training
# ---------------------------------------------------------------------------

def train(data_dir: str = D.DATA_DIR, out_dir: str = MODEL_DIR) -> dict:
    """Run the full Module 2 training and evaluation. Returns the metadata."""
    F.assert_no_leakage(F.FEATURES)
    F.assert_no_leakage(F.FEATURES_NO_ESTIMATE)

    frame = D.load_dataset(data_dir)
    train_df, val_df, test_df = D.split_chronologically(frame)
    split = D.split_summary(train_df, val_df, test_df)

    y_train = train_df[F.TARGET].to_numpy(dtype=float)
    y_val = val_df[F.TARGET].to_numpy(dtype=float)
    y_test = test_df[F.TARGET].to_numpy(dtype=float)

    print("Split (chronological by shift_date)")
    for name in ("train", "validation", "test"):
        part = split[name]
        print(f"  {name:11s} {part['rows']:5d} rows  {part['share']:6.1%}  "
              f"{part['first_date']} .. {part['last_date']}")
    print(f"\nFeatures: {len(F.FEATURES)} "
          f"({len([f for f in F.FEATURES if f in F.CATEGORICAL_FEATURES])} categorical, "
          f"{len([f for f in F.FEATURES if f in F.NUMERIC_FEATURES])} numeric)")
    print()

    results = {}

    # --- Baseline 0: the planner's estimate (the incumbent) --------------
    results["baseline_0_planner_estimate"] = {
        "description": "predict tasks.estimated_minutes directly (no training)",
        "validation": metrics(y_val, val_df["estimated_minutes"]),
        "test": metrics(y_test, test_df["estimated_minutes"]),
    }

    # --- Baseline 1: train mean (R2 = 0 reference) -----------------------
    mean_pred = float(y_train.mean())
    results["baseline_1_train_mean"] = {
        "description": f"predict the training mean ({mean_pred:.1f} minutes)",
        "validation": metrics(y_val, np.full(len(y_val), mean_pred)),
        "test": metrics(y_test, np.full(len(y_test), mean_pred)),
    }

    # --- Baseline 2: Linear Regression ----------------------------------
    linear = build_linear(F.FEATURES)
    linear.fit(train_df[F.FEATURES], y_train)
    results["baseline_2_linear_regression"] = {
        "description": "OneHot + StandardScaler + LinearRegression",
        "train": metrics(y_train, _predict_clipped(linear, train_df, F.FEATURES)),
        "validation": metrics(y_val, _predict_clipped(linear, val_df, F.FEATURES)),
        "test": metrics(y_test, _predict_clipped(linear, test_df, F.FEATURES)),
    }

    # --- Candidate: Random Forest, selected on validation ---------------
    print(f"Searching {len(RF_GRID)} Random Forest configurations on validation...")
    search = []
    best = None
    for params in RF_GRID:
        pipeline = build_forest(F.FEATURES, params)
        pipeline.fit(train_df[F.FEATURES], y_train)
        val_mae = float(mean_absolute_error(y_val, _predict_clipped(pipeline, val_df, F.FEATURES)))
        search.append({"params": params, "validation_MAE": val_mae})
        if best is None or val_mae < best["validation_MAE"]:
            best = {"params": params, "validation_MAE": val_mae, "pipeline": pipeline}
    search.sort(key=lambda r: r["validation_MAE"])
    print(f"  best: {best['params']}  validation MAE={best['validation_MAE']:.2f}\n")

    forest = best["pipeline"]
    results["candidate_random_forest_validation_selected"] = {
        "description": (
            "OneHot + StandardScaler + RandomForestRegressor - the "
            "validation-MAE winner of the grid search. Scored in full but NOT "
            "shipped: the artifact is ~10x larger for a negligible gain."
        ),
        "selected_params": best["params"],
        "selection_metric": "validation MAE",
        "shipped": False,
        "artifact_bytes": _artifact_size_bytes(forest),
        "train": metrics(y_train, _predict_clipped(forest, train_df, F.FEATURES)),
        "validation": metrics(y_val, _predict_clipped(forest, val_df, F.FEATURES)),
        "test": metrics(y_test, _predict_clipped(forest, test_df, F.FEATURES)),
    }

    # --- Deployment model: the compact configuration we actually ship ----
    print(f"Training the compact deployment configuration {DEPLOYMENT_PARAMS}...")
    compact = build_forest(F.FEATURES, DEPLOYMENT_PARAMS)
    compact.fit(train_df[F.FEATURES], y_train)
    results["deployment_random_forest_compact"] = {
        "description": (
            "OneHot + StandardScaler + RandomForestRegressor - the compact "
            "configuration shipped as the serving artifact."
        ),
        "selected_params": dict(DEPLOYMENT_PARAMS),
        "selection_metric": "human decision on the artifact-size/accuracy tradeoff",
        "rationale": DEPLOYMENT_RATIONALE,
        "shipped": True,
        "artifact_bytes": _artifact_size_bytes(compact),
        "train": metrics(y_train, _predict_clipped(compact, train_df, F.FEATURES)),
        "validation": metrics(y_val, _predict_clipped(compact, val_df, F.FEATURES)),
        "test": metrics(y_test, _predict_clipped(compact, test_df, F.FEATURES)),
    }

    # --- Ablation: the same forest without the planner's estimate -------
    ablation = build_forest(F.FEATURES_NO_ESTIMATE, DEPLOYMENT_PARAMS)
    ablation.fit(train_df[F.FEATURES_NO_ESTIMATE], y_train)
    results["ablation_random_forest_no_estimate"] = {
        "description": (
            "same configuration without estimated_minutes - shows how much the "
            "model contributes independently of the planner's estimate"
        ),
        "features": len(F.FEATURES_NO_ESTIMATE),
        "validation": metrics(y_val, _predict_clipped(ablation, val_df, F.FEATURES_NO_ESTIMATE)),
        "test": metrics(y_test, _predict_clipped(ablation, test_df, F.FEATURES_NO_ESTIMATE)),
    }

    # --- Final model -----------------------------------------------------
    # The shipped model is the compact deployment configuration. This is a
    # documented human decision about artifact size, not a metric win: the
    # validation-selected configuration above scores marginally better and is
    # recorded in full alongside it.
    final_name = "deployment_random_forest_compact"
    final_model, final_features = compact, F.FEATURES

    # The final model stays fitted on TRAIN ONLY. Refitting on train+validation
    # would invalidate the validation-derived interval quantiles.
    val_pred = _predict_clipped(final_model, val_df, final_features)
    test_pred = _predict_clipped(final_model, test_df, final_features)

    interval = calibrate_interval(y_val, val_pred)
    coverage = {
        "validation": interval_coverage(y_val, val_pred, interval),
        "test": interval_coverage(y_test, test_pred, interval),
    }

    # --- Explainability ---------------------------------------------------
    importance = _feature_importance(final_model, final_features, val_df, y_val)

    # --- Print report -----------------------------------------------------
    print("VALIDATION (used for model selection)")
    for key, res in results.items():
        if "validation" in res:
            print(_fmt(key, res["validation"]))
    print("\nTEST (held out - scored once)")
    for key, res in results.items():
        if "test" in res:
            print(_fmt(key, res["test"]))
    print("\nCONFIGURATION CHOICE")
    vs = results["candidate_random_forest_validation_selected"]
    ds = results["deployment_random_forest_compact"]
    print(f"  validation-selected  {vs['selected_params']}")
    print(f"       val MAE={vs['validation']['MAE']:.2f}  test MAE={vs['test']['MAE']:.2f}  "
          f"artifact={vs['artifact_bytes'] / 1e6:.1f} MB  shipped=No")
    print(f"  deployment (compact) {ds['selected_params']}")
    print(f"       val MAE={ds['validation']['MAE']:.2f}  test MAE={ds['test']['MAE']:.2f}  "
          f"artifact={ds['artifact_bytes'] / 1e6:.1f} MB  shipped=YES")
    print(f"  tradeoff: +{ds['test']['MAE'] - vs['test']['MAE']:.2f} min test MAE for a "
          f"{vs['artifact_bytes'] / max(ds['artifact_bytes'], 1):.1f}x smaller artifact")

    print(f"\nFinal model: {final_name}")
    print(f"Interval: x{interval['ratio_lower']:.4f} .. x{interval['ratio_upper']:.4f} "
          f"(nominal {interval['nominal_coverage']:.0%})")
    print(f"  measured coverage  validation={coverage['validation']['measured']:.1%}  "
          f"test={coverage['test']['measured']:.1%}")
    print(f"  mean interval width test={coverage['test']['mean_width_minutes']:.1f} minutes")
    print("\nTop features (permutation importance on validation)")
    for row in importance["permutation_importance"][:8]:
        print(f"  {row['feature']:20s} {row['importance']:8.2f}")

    # --- Artifacts --------------------------------------------------------
    os.makedirs(out_dir, exist_ok=True)

    metadata = {
        "project": "CAT Smart Operator Assistant",
        "module": "Module 2 - Task Duration Prediction",
        "data_source": "synthetic",
        "disclaimer": (
            "SYNTHETIC DATA. All metrics describe performance on synthetic data "
            "generated for a hackathon prototype. They do not represent "
            "real-world Caterpillar performance."
        ),
        "trained_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "seed": SEED,
        "target": F.TARGET,
        "target_units": "minutes",
        "target_transform": "none (raw minutes)",
        "features": final_features,
        "feature_count": len(final_features),
        "categorical_features": [f for f in final_features if f in F.CATEGORICAL_FEATURES],
        "numeric_features": [f for f in final_features if f in F.NUMERIC_FEATURES],
        "excluded_columns": F.EXCLUSION_REASONS,
        "leakage_guard": {
            "post_completion": F.POST_COMPLETION_COLUMNS,
            "temporal_leakage": F.TEMPORAL_LEAKAGE_COLUMNS,
            "identifiers": F.IDENTIFIER_COLUMNS,
            "split_only": F.SPLIT_ONLY_COLUMNS,
        },
        "split": split,
        "models": results,
        "rf_search": search,
        "configuration_choice": {
            "validation_selected": {
                "params": best["params"],
                "chosen_by": "lowest validation MAE across the grid",
                "validation_MAE": results["candidate_random_forest_validation_selected"]["validation"]["MAE"],
                "test_MAE": results["candidate_random_forest_validation_selected"]["test"]["MAE"],
                "artifact_bytes": results["candidate_random_forest_validation_selected"]["artifact_bytes"],
                "shipped": False,
            },
            "deployment_selected": {
                "params": dict(DEPLOYMENT_PARAMS),
                "chosen_by": "human decision on the artifact-size/accuracy tradeoff",
                "validation_MAE": results["deployment_random_forest_compact"]["validation"]["MAE"],
                "test_MAE": results["deployment_random_forest_compact"]["test"]["MAE"],
                "artifact_bytes": results["deployment_random_forest_compact"]["artifact_bytes"],
                "shipped": True,
            },
            "measured_tradeoff": {
                "test_MAE_cost_minutes": (
                    results["deployment_random_forest_compact"]["test"]["MAE"]
                    - results["candidate_random_forest_validation_selected"]["test"]["MAE"]
                ),
                "artifact_size_reduction_factor": (
                    results["candidate_random_forest_validation_selected"]["artifact_bytes"]
                    / max(results["deployment_random_forest_compact"]["artifact_bytes"], 1)
                ),
            },
            "rationale": DEPLOYMENT_RATIONALE,
        },
        "final_model": final_name,
        "final_model_fitted_on": "train only (so the validation-derived interval stays valid)",
        "uncertainty": interval,
        "interval_coverage": coverage,
        "prediction_bounds": {
            "min_predicted_minutes": F.MIN_PREDICTED_MINUTES,
            "max_predicted_minutes": F.MAX_PREDICTED_MINUTES,
        },
        "environment": {
            "python": platform.python_version(),
            "scikit_learn": sklearn.__version__,
            "numpy": np.__version__,
            "pandas": pd.__version__,
        },
        "source_data": _source_data_fingerprint(data_dir),
    }

    joblib.dump(final_model, os.path.join(out_dir, MODEL_FILENAME))
    _write_json(os.path.join(out_dir, METADATA_FILENAME), metadata)
    _write_json(os.path.join(out_dir, IMPORTANCE_FILENAME), importance)

    print(f"\nArtifacts written to {out_dir}/")
    for name in (MODEL_FILENAME, METADATA_FILENAME, IMPORTANCE_FILENAME):
        path = os.path.join(out_dir, name)
        print(f"  {name:32s} {os.path.getsize(path):8d} bytes")

    return metadata


# ---------------------------------------------------------------------------
# explainability
# ---------------------------------------------------------------------------

def _feature_importance(pipeline, feature_list, val_df, y_val) -> dict:
    """
    Deterministic model explanation.

    Two views, no SHAP:
      * the estimator's own importances (tree) or coefficients (linear)
      * permutation importance on validation, which is more trustworthy and
        already lives in sklearn
    """
    model = pipeline.named_steps["model"]
    encoded_names = list(pipeline.named_steps["preprocess"].get_feature_names_out())

    native = []
    if hasattr(model, "feature_importances_"):
        native_kind = "random_forest_feature_importances"
        for name, value in zip(encoded_names, model.feature_importances_):
            native.append({"encoded_feature": name, "importance": float(value)})
    else:
        native_kind = "linear_regression_coefficients"
        for name, value in zip(encoded_names, np.ravel(model.coef_)):
            native.append({"encoded_feature": name, "coefficient": float(value)})
    native.sort(key=lambda r: abs(r.get("importance", r.get("coefficient", 0.0))), reverse=True)

    result = permutation_importance(
        pipeline, val_df[feature_list], y_val,
        n_repeats=10, random_state=SEED, scoring="neg_mean_absolute_error",
    )
    permutation = [
        {
            "feature": feature,
            "importance": float(mean),
            "std": float(std),
        }
        for feature, mean, std in zip(feature_list, result.importances_mean, result.importances_std)
    ]
    permutation.sort(key=lambda r: r["importance"], reverse=True)

    return {
        "note": (
            "Permutation importance is the increase in validation MAE (minutes) "
            "when a feature is shuffled. Measured on synthetic data."
        ),
        "native_kind": native_kind,
        "native": native,
        "permutation_importance": permutation,
    }


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _artifact_size_bytes(pipeline) -> int:
    """
    Serialised size of a fitted pipeline, measured rather than estimated.

    Dumped to a temporary file so the size recorded in the metadata is the
    real joblib footprint, not a guess.
    """
    import tempfile

    handle = tempfile.NamedTemporaryFile(suffix=".joblib", delete=False)
    handle.close()
    try:
        joblib.dump(pipeline, handle.name)
        return int(os.path.getsize(handle.name))
    finally:
        os.unlink(handle.name)


def _source_data_fingerprint(data_dir: str) -> dict:
    """Record which Module 1 output this model was trained on."""
    path = os.path.join(data_dir, "manifest.json")
    if not os.path.exists(path):
        return {"manifest": "not found"}
    with open(path, encoding="utf-8") as handle:
        manifest = json.load(handle)
    return {
        "seed": manifest.get("seed"),
        "reference_date": manifest.get("reference_date"),
        "task_history_sha256": manifest.get("files", {}).get("task_history.csv", {}).get("sha256"),
    }


def _write_json(path: str, payload: dict) -> None:
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Train the task duration model.")
    parser.add_argument("--data", default=D.DATA_DIR, help="directory holding the Module 1 CSVs")
    parser.add_argument("--out", default=MODEL_DIR, help="artifact output directory")
    args = parser.parse_args()
    train(args.data, args.out)


if __name__ == "__main__":
    main()

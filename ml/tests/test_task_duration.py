"""
Module 2 tests: task duration prediction.

Training happens into a temporary directory, so these tests never depend on or
overwrite the artifact in ml/models/. The hyperparameter grid is narrowed for
speed; everything else runs exactly as in production training.

Run from the repository root:
    python -m pytest ml/tests -v
"""

from __future__ import annotations

import json
import os

import numpy as np
import pytest

from ml import data as D
from ml import features as F
from ml import predict as P
from ml.training import train_task_duration as T

# Narrow grid: the real search showed all 18 configs within 0.14 MAE, so two
# are enough to exercise the selection path.
FAST_GRID = [
    {"n_estimators": 60, "max_depth": 12, "min_samples_leaf": 4},
    {"n_estimators": 60, "max_depth": None, "min_samples_leaf": 2},
]


@pytest.fixture(scope="module")
def trained(tmp_path_factory):
    """Run the real training pipeline once, into a temp directory."""
    out = tmp_path_factory.mktemp("models")
    original = T.RF_GRID
    T.RF_GRID = FAST_GRID
    try:
        metadata = T.train(D.DATA_DIR, str(out))
    finally:
        T.RF_GRID = original
    return str(out), metadata


@pytest.fixture(scope="module")
def predictor(trained):
    out, _ = trained
    return P.TaskDurationPredictor.load(out, D.DATA_DIR)


@pytest.fixture(scope="module")
def frame():
    return D.load_dataset()


@pytest.fixture(scope="module")
def reference():
    operators, machines = D.load_reference_tables()
    tasks = D.load_tasks()
    return tasks, operators, machines


def _request(task_id, operator_id, machine_id, **env):
    environment = {"temperature": 29.0, "rainfall": 0.0, "humidity": 65.0,
                   "wind_speed": 8.0, "visibility": 9.5}
    environment.update(env)
    return {"task_id": task_id, "operator_id": operator_id,
            "machine_id": machine_id, "environment": environment}


# ---------------------------------------------------------------------------
# 1. data loading
# ---------------------------------------------------------------------------

def test_dataset_loads_with_expected_rows(frame):
    assert len(frame) == 3000


def test_joined_attributes_have_no_nulls(frame):
    for column in ("skill_level", "experience_years", "machine_type",
                   "age_years", "condition_rating"):
        assert frame[column].notna().all(), column


def test_target_present_and_positive(frame):
    assert F.TARGET in frame.columns
    assert (frame[F.TARGET] > 0).all()


def test_telemetry_and_safety_are_never_loaded(frame):
    """The loader must not pull post-completion tables into the feature frame."""
    forbidden = {"runtime_minutes", "idle_minutes", "fuel_used_liters",
                 "engine_hours", "completed_at", "event_type", "severity"}
    assert not (set(frame.columns) & forbidden)


def test_missing_data_raises_a_clear_error(tmp_path):
    with pytest.raises(D.DataNotGeneratedError):
        D.load_dataset(str(tmp_path))


# ---------------------------------------------------------------------------
# 2. split integrity
# ---------------------------------------------------------------------------

def test_split_sizes_and_dates(frame):
    train, validation, test = D.split_chronologically(frame)
    assert len(train) == D.EXPECTED_SPLIT_SIZES["train"] == 1797
    assert len(validation) == D.EXPECTED_SPLIT_SIZES["validation"] == 598
    assert len(test) == D.EXPECTED_SPLIT_SIZES["test"] == 605
    assert len(train) + len(validation) + len(test) == len(frame)


def test_split_is_chronological_and_non_overlapping(frame):
    train, validation, test = D.split_chronologically(frame)
    assert train["shift_date"].max() < D.TRAIN_END
    assert validation["shift_date"].min() >= D.TRAIN_END
    assert validation["shift_date"].max() < D.VAL_END
    assert test["shift_date"].min() >= D.VAL_END
    assert train["shift_date"].max() < validation["shift_date"].min()
    assert validation["shift_date"].max() < test["shift_date"].min()


def test_no_task_appears_in_two_splits(frame):
    train, validation, test = D.split_chronologically(frame)
    a, b, c = (set(part["task_id"]) for part in (train, validation, test))
    assert not (a & b) and not (b & c) and not (a & c)


def test_every_categorical_level_is_present_in_train(frame):
    train, validation, test = D.split_chronologically(frame)
    for column in F.CATEGORICAL_FEATURES:
        unseen = (set(validation[column]) | set(test[column])) - set(train[column])
        assert not unseen, f"{column}: unseen in train -> {unseen}"


# ---------------------------------------------------------------------------
# 3. leakage guards
# ---------------------------------------------------------------------------

def test_feature_set_contains_no_forbidden_column():
    F.assert_no_leakage(F.FEATURES)
    F.assert_no_leakage(F.FEATURES_NO_ESTIMATE)


def test_leakage_guard_actually_fires():
    """A guard that never fails is not a guard."""
    for leaking in ("actual_minutes", "runtime_minutes", "engine_hours",
                    "completed_at", "task_id", "operator_id", "shift_date",
                    "idle_ratio", "fuel_used_liters"):
        with pytest.raises(ValueError, match="leakage guard"):
            F.assert_no_leakage(F.FEATURES + [leaking])


def test_target_is_not_a_feature():
    assert F.TARGET not in F.FEATURES


def test_dropped_and_excluded_columns_are_documented():
    for column in ("shift", "weather", "priority", "business_value",
                   "quantity_unit", "required_machine_type", "primary_shift"):
        assert column in F.EXCLUSION_REASONS, column
        assert column not in F.FEATURES


def test_feature_counts():
    assert len(F.FEATURES) == 15
    assert len(F.FEATURES_NO_ESTIMATE) == 14
    assert "estimated_minutes" not in F.FEATURES_NO_ESTIMATE
    assert len([f for f in F.FEATURES if f in F.CATEGORICAL_FEATURES]) == 4
    assert len([f for f in F.FEATURES if f in F.NUMERIC_FEATURES]) == 11


# ---------------------------------------------------------------------------
# 4. preprocessing
# ---------------------------------------------------------------------------

def test_preprocessor_fits_on_train_and_transforms_other_splits(frame):
    train, validation, _ = D.split_chronologically(frame)
    pre = F.build_preprocessor(F.FEATURES)
    pre.fit(train[F.FEATURES])
    transformed = pre.transform(validation[F.FEATURES])
    assert transformed.shape[0] == len(validation)
    assert np.isfinite(transformed).all()


def test_unseen_category_does_not_raise(frame):
    """handle_unknown='ignore' must degrade gracefully, not explode."""
    train, _, _ = D.split_chronologically(frame)
    pre = F.build_preprocessor(F.FEATURES)
    pre.fit(train[F.FEATURES])
    row = train[F.FEATURES].iloc[[0]].copy()
    row["task_type"] = "UNSEEN_TASK_TYPE"
    transformed = pre.transform(row)
    assert transformed.shape[0] == 1
    assert np.isfinite(transformed).all()


def test_preprocessor_output_width_is_stable(frame):
    train, validation, test = D.split_chronologically(frame)
    pre = F.build_preprocessor(F.FEATURES)
    pre.fit(train[F.FEATURES])
    widths = {pre.transform(part[F.FEATURES]).shape[1]
              for part in (train, validation, test)}
    assert len(widths) == 1


# ---------------------------------------------------------------------------
# 5. training
# ---------------------------------------------------------------------------

def test_training_produces_all_artifacts(trained):
    out, _ = trained
    for name in (T.MODEL_FILENAME, T.METADATA_FILENAME, T.IMPORTANCE_FILENAME):
        path = os.path.join(out, name)
        assert os.path.exists(path), name
        assert os.path.getsize(path) > 0


def test_metadata_has_required_keys(trained):
    _, metadata = trained
    for key in ("seed", "target", "features", "split", "models", "final_model",
                "uncertainty", "interval_coverage", "excluded_columns",
                "leakage_guard", "environment", "source_data", "disclaimer"):
        assert key in metadata, key
    assert metadata["seed"] == 42
    assert metadata["target"] == "actual_minutes"
    assert metadata["target_units"] == "minutes"


def test_metadata_states_synthetic_only(trained):
    _, metadata = trained
    assert metadata["data_source"] == "synthetic"
    assert "SYNTHETIC" in metadata["disclaimer"].upper()
    assert "caterpillar" in metadata["disclaimer"].lower()


def test_all_models_were_evaluated(trained):
    _, metadata = trained
    for name in ("baseline_0_planner_estimate", "baseline_1_train_mean",
                 "baseline_2_linear_regression",
                 "candidate_random_forest_validation_selected",
                 "deployment_random_forest_compact",
                 "ablation_random_forest_no_estimate"):
        assert name in metadata["models"], name
        assert "test" in metadata["models"][name]


def test_shipped_model_is_the_compact_configuration(trained):
    _, metadata = trained
    assert metadata["final_model"] == "deployment_random_forest_compact"
    shipped = metadata["models"][metadata["final_model"]]
    assert shipped["shipped"] is True
    assert shipped["selected_params"]["n_estimators"] == 200
    assert shipped["selected_params"]["min_samples_leaf"] == 4


def test_validation_selected_configuration_is_still_recorded(trained):
    """The larger config must stay visible, not be quietly dropped."""
    _, metadata = trained
    recorded = metadata["models"]["candidate_random_forest_validation_selected"]
    assert recorded["shipped"] is False
    assert recorded["selection_metric"] == "validation MAE"
    for split in ("validation", "test"):
        assert np.isfinite(recorded[split]["MAE"])
    assert recorded["artifact_bytes"] > 0


def test_configuration_tradeoff_is_documented(trained):
    """
    Both configurations must be recorded with measured sizes and costs.

    Note: this does NOT assert that the deployment artifact is the smaller of
    the two. These tests narrow the grid to 60-tree forests for speed, so the
    grid winner here can be smaller than the fixed 200-tree deployment
    configuration. The real size ordering is asserted against the production
    metadata in test_production_metadata_shows_the_size_reduction.
    """
    _, metadata = trained
    choice = metadata["configuration_choice"]

    assert choice["validation_selected"]["shipped"] is False
    assert choice["deployment_selected"]["shipped"] is True
    assert choice["deployment_selected"]["params"]["n_estimators"] == 200
    assert choice["deployment_selected"]["params"]["min_samples_leaf"] == 4
    assert choice["validation_selected"]["chosen_by"] == (
        "lowest validation MAE across the grid")
    assert "human decision" in choice["deployment_selected"]["chosen_by"]

    for side in ("validation_selected", "deployment_selected"):
        assert choice[side]["artifact_bytes"] > 0, side
        assert np.isfinite(choice[side]["validation_MAE"]), side
        assert np.isfinite(choice[side]["test_MAE"]), side

    # the recorded tradeoff must be arithmetically consistent with the sizes
    expected_factor = (choice["validation_selected"]["artifact_bytes"]
                       / choice["deployment_selected"]["artifact_bytes"])
    assert choice["measured_tradeoff"]["artifact_size_reduction_factor"] == pytest.approx(
        expected_factor, rel=1e-9)

    expected_cost = (choice["deployment_selected"]["test_MAE"]
                     - choice["validation_selected"]["test_MAE"])
    assert choice["measured_tradeoff"]["test_MAE_cost_minutes"] == pytest.approx(
        expected_cost, rel=1e-9)

    assert choice["rationale"]
    assert "10x smaller" in choice["rationale"]


def test_production_metadata_shows_the_size_reduction():
    """
    Against the real artifact trained with the full grid, the compact
    deployment configuration must genuinely be the smaller one.
    """
    path = os.path.join(T.MODEL_DIR, T.METADATA_FILENAME)
    if not os.path.exists(path):
        pytest.skip("ml/models metadata not present - run the training script")
    with open(path, encoding="utf-8") as handle:
        choice = json.load(handle)["configuration_choice"]

    assert choice["validation_selected"]["params"] == {
        "n_estimators": 400, "max_depth": None, "min_samples_leaf": 1}
    assert choice["deployment_selected"]["params"] == {
        "n_estimators": 200, "max_depth": None, "min_samples_leaf": 4}
    assert (choice["deployment_selected"]["artifact_bytes"]
            < choice["validation_selected"]["artifact_bytes"])
    assert choice["measured_tradeoff"]["artifact_size_reduction_factor"] > 5.0
    assert choice["measured_tradeoff"]["test_MAE_cost_minutes"] < 1.0


def test_compact_model_accuracy_cost_is_small(trained):
    """The tradeoff was accepted on the basis of a small cost - verify it."""
    _, metadata = trained
    cost = metadata["configuration_choice"]["measured_tradeoff"]["test_MAE_cost_minutes"]
    assert cost < 2.0, cost


def test_shipped_artifact_is_compact_on_disk(trained):
    out, _ = trained
    size = os.path.getsize(os.path.join(out, T.MODEL_FILENAME))
    assert size < 20_000_000, size


def test_metrics_are_finite_and_reported_per_split(trained):
    _, metadata = trained
    for name, result in metadata["models"].items():
        for split in ("validation", "test"):
            m = result[split]
            for key in ("MAE", "RMSE", "R2", "MAPE", "n"):
                assert key in m, (name, split, key)
                assert np.isfinite(m[key]), (name, split, key)
            assert m["MAE"] >= 0 and m["RMSE"] >= 0


def test_model_beats_the_planner_baseline(trained):
    """The whole point: the trained model must improve on the incumbent."""
    _, metadata = trained
    planner = metadata["models"]["baseline_0_planner_estimate"]["test"]["MAE"]
    final = metadata["models"][metadata["final_model"]]["test"]["MAE"]
    assert final < planner


def test_model_beats_the_mean_predictor(trained):
    _, metadata = trained
    mean_r2 = metadata["models"]["baseline_1_train_mean"]["test"]["R2"]
    final_r2 = metadata["models"][metadata["final_model"]]["test"]["R2"]
    assert final_r2 > mean_r2
    assert abs(mean_r2) < 0.05          # the mean predictor sits at R2 ~ 0


def test_training_is_deterministic(tmp_path):
    """
    Same seed, same data, same metrics.

    Compared with a tight relative tolerance rather than exact float equality:
    the forest predicts with n_jobs=-1, so averaging tree outputs can differ by
    one unit in the last place depending on thread reduction order. That moves
    RMSE/MAPE in the 15th significant digit while the fitted model is
    identical, which the prediction check below pins down exactly.
    """
    import joblib

    original = T.RF_GRID
    T.RF_GRID = FAST_GRID
    try:
        first = T.train(D.DATA_DIR, str(tmp_path / "a"))
        second = T.train(D.DATA_DIR, str(tmp_path / "b"))
    finally:
        T.RF_GRID = original

    for name in first["models"]:
        for split in ("validation", "test"):
            a, b = first["models"][name][split], second["models"][name][split]
            assert a["n"] == b["n"], (name, split)
            for key in ("MAE", "RMSE", "R2", "MAPE"):
                assert a[key] == pytest.approx(b[key], rel=1e-9), (name, split, key)

    assert first["uncertainty"]["ratio_lower"] == pytest.approx(
        second["uncertainty"]["ratio_lower"], rel=1e-9)
    assert first["uncertainty"]["ratio_upper"] == pytest.approx(
        second["uncertainty"]["ratio_upper"], rel=1e-9)
    assert first["final_model"] == second["final_model"]
    assert first["models"][first["final_model"]]["selected_params"] == \
        second["models"][second["final_model"]]["selected_params"]

    # The two fitted models must agree to floating-point precision.
    frame = D.load_dataset()
    sample = frame[first["features"]].iloc[:200]
    model_a = joblib.load(str(tmp_path / "a" / T.MODEL_FILENAME))
    model_b = joblib.load(str(tmp_path / "b" / T.MODEL_FILENAME))
    np.testing.assert_allclose(model_a.predict(sample), model_b.predict(sample), rtol=1e-12)


def test_final_model_is_fitted_on_train_only(trained):
    _, metadata = trained
    assert "train only" in metadata["final_model_fitted_on"]


# ---------------------------------------------------------------------------
# 6. artifact round-trip
# ---------------------------------------------------------------------------

def test_reloaded_model_reproduces_predictions(trained, predictor, frame):
    """A reloaded artifact must predict identically, or serving will drift."""
    import joblib
    out, metadata = trained
    reloaded = joblib.load(os.path.join(out, T.MODEL_FILENAME))
    sample = frame[metadata["features"]].iloc[:50]
    np.testing.assert_allclose(
        reloaded.predict(sample), predictor.model.predict(sample))


# ---------------------------------------------------------------------------
# 7. prediction and the output contract
# ---------------------------------------------------------------------------

def test_output_has_exactly_the_contract_keys(predictor, reference):
    tasks, operators, machines = reference
    result = predictor.predict(_request(
        tasks.iloc[0]["task_id"], operators.iloc[0]["operator_id"],
        machines.iloc[0]["machine_id"]))
    assert list(result.keys()) == P.CONTRACT_OUTPUT_KEYS
    assert set(result) == {"task_id", "predicted_minutes", "lower_bound", "upper_bound"}


def test_task_id_is_echoed_unchanged(predictor, reference):
    tasks, operators, machines = reference
    task_id = tasks.iloc[5]["task_id"]
    result = predictor.predict(_request(
        task_id, operators.iloc[0]["operator_id"], machines.iloc[0]["machine_id"]))
    assert result["task_id"] == task_id


def test_contract_example_shape_is_accepted(predictor, reference):
    """The exact request shape from docs/contracts.md section 1."""
    tasks, operators, machines = reference
    request = {
        "task_id": tasks.iloc[0]["task_id"],
        "operator_id": operators.iloc[0]["operator_id"],
        "machine_id": machines.iloc[0]["machine_id"],
        "environment": {
            "temperature": 29,
            "rainfall": 0,
            "humidity": 65,
            "wind_speed": 8,
            "visibility": 9.5,
        },
    }
    result = predictor.predict(request)
    assert isinstance(result["predicted_minutes"], int)
    assert isinstance(result["lower_bound"], int)
    assert isinstance(result["upper_bound"], int)


def test_unknown_ids_are_rejected(predictor, reference):
    tasks, operators, machines = reference
    good = (tasks.iloc[0]["task_id"], operators.iloc[0]["operator_id"],
            machines.iloc[0]["machine_id"])
    with pytest.raises(P.UnknownEntityError):
        predictor.predict(_request("T999999", good[1], good[2]))
    with pytest.raises(P.UnknownEntityError):
        predictor.predict(_request(good[0], "OP999", good[2]))
    with pytest.raises(P.UnknownEntityError):
        predictor.predict(_request(good[0], good[1], "M999"))


def test_malformed_requests_are_rejected(predictor, reference):
    tasks, operators, machines = reference
    base = _request(tasks.iloc[0]["task_id"], operators.iloc[0]["operator_id"],
                    machines.iloc[0]["machine_id"])

    for missing in ("task_id", "operator_id", "machine_id", "environment"):
        broken = {k: v for k, v in base.items() if k != missing}
        with pytest.raises(P.InvalidRequestError):
            predictor.predict(broken)

    for missing in P.ENVIRONMENT_KEYS:
        broken = dict(base)
        broken["environment"] = {k: v for k, v in base["environment"].items() if k != missing}
        with pytest.raises(P.InvalidRequestError):
            predictor.predict(broken)

    broken = dict(base)
    broken["environment"] = dict(base["environment"], temperature="warm")
    with pytest.raises(P.InvalidRequestError):
        predictor.predict(broken)


# ---------------------------------------------------------------------------
# 8. sanity checks across the input space
# ---------------------------------------------------------------------------

WEATHER_CASES = {
    "CLEAR": {"rainfall": 0.0, "humidity": 45.0, "visibility": 10.0},
    "CLOUDY": {"rainfall": 0.0, "humidity": 82.0, "visibility": 9.0},
    "RAIN": {"rainfall": 6.0, "humidity": 88.0, "visibility": 8.0},
    "HEAVY_RAIN": {"rainfall": 22.0, "humidity": 96.0, "visibility": 5.0},
    "FOG": {"rainfall": 0.0, "humidity": 90.0, "visibility": 1.2},
}


def _sweep(predictor, reference):
    """One request per (skill level, task type, weather, machine type) corner."""
    tasks, operators, machines = reference
    requests = []
    for skill in ("BEGINNER", "INTERMEDIATE", "EXPERT"):
        operator = operators[operators["skill_level"] == skill].iloc[0]["operator_id"]
        for task_type in sorted(tasks["task_type"].unique()):
            task = tasks[tasks["task_type"] == task_type].iloc[0]
            machine = machines[
                machines["machine_type"] == task["required_machine_type"]
            ].iloc[0]["machine_id"]
            for env in WEATHER_CASES.values():
                requests.append(_request(task["task_id"], operator, machine, **env))
    for machine_type in sorted(machines["machine_type"].unique()):
        machine = machines[machines["machine_type"] == machine_type].iloc[0]["machine_id"]
        requests.append(_request(tasks.iloc[0]["task_id"],
                                 operators.iloc[0]["operator_id"], machine))
    return requests


def test_sweep_covers_the_documented_input_space(predictor, reference):
    requests = _sweep(predictor, reference)
    # 3 skills x 7 task types x 5 weather cases, plus 5 machine types
    assert len(requests) == 3 * 7 * 5 + 5 == 110


def test_all_predictions_are_positive_and_bounded(predictor, reference):
    for request in _sweep(predictor, reference):
        result = predictor.predict(request)
        assert result["predicted_minutes"] > 0, request
        assert result["lower_bound"] > 0, request
        assert result["lower_bound"] <= result["predicted_minutes"], request
        assert result["predicted_minutes"] <= result["upper_bound"], request
        assert result["predicted_minutes"] <= F.MAX_PREDICTED_MINUTES


def test_no_nan_or_infinite_predictions(predictor, reference):
    for request in _sweep(predictor, reference):
        result = predictor.predict(request)
        for key in ("predicted_minutes", "lower_bound", "upper_bound"):
            assert np.isfinite(result[key]), (key, request)


def test_predictions_are_plausible_durations(predictor, reference):
    """No 3-minute excavations, no 40-hour gradings."""
    for request in _sweep(predictor, reference):
        result = predictor.predict(request)
        assert 5 <= result["predicted_minutes"] <= 1500, (result, request)


def test_extreme_environment_does_not_break_prediction(predictor, reference):
    tasks, operators, machines = reference
    task, operator = tasks.iloc[0], operators.iloc[0]["operator_id"]
    machine = machines.iloc[0]["machine_id"]
    for env in (
        {"temperature": 45.0, "rainfall": 40.0, "humidity": 98.0,
         "wind_speed": 45.0, "visibility": 0.5},
        {"temperature": 5.0, "rainfall": 0.0, "humidity": 20.0,
         "wind_speed": 0.0, "visibility": 10.0},
    ):
        result = predictor.predict(_request(task["task_id"], operator, machine, **env))
        assert result["predicted_minutes"] > 0
        assert result["lower_bound"] <= result["predicted_minutes"] <= result["upper_bound"]


def test_batch_prediction_matches_single(predictor, reference):
    requests = _sweep(predictor, reference)[:20]
    batch = predictor.predict_batch(requests)
    assert batch == [predictor.predict(r) for r in requests]


# ---------------------------------------------------------------------------
# 9. uncertainty
# ---------------------------------------------------------------------------

def test_uncertainty_is_calibrated_on_validation(trained):
    _, metadata = trained
    u = metadata["uncertainty"]
    assert u["calibrated_on"] == "validation"
    assert "validation" in u["method"]
    assert u["nominal_coverage"] == pytest.approx(0.80)


def test_interval_quantiles_bracket_the_point_prediction(trained):
    _, metadata = trained
    u = metadata["uncertainty"]
    assert 0 < u["ratio_lower"] <= 1.0 <= u["ratio_upper"]


def test_measured_coverage_is_recorded_for_both_splits(trained):
    _, metadata = trained
    for split in ("validation", "test"):
        cov = metadata["interval_coverage"][split]
        assert 0.0 <= cov["measured"] <= 1.0
        assert cov["mean_width_minutes"] > 0
        assert cov["n"] > 0


def test_measured_coverage_is_near_nominal(trained):
    """Not required to be perfect - but it must be honest and in the ballpark."""
    _, metadata = trained
    measured = metadata["interval_coverage"]["test"]["measured"]
    assert 0.65 <= measured <= 0.92, measured


def test_interval_width_scales_with_prediction(predictor, reference):
    """Multiplicative bounds: a longer task gets a wider interval."""
    tasks, operators, machines = reference
    operator = operators.iloc[0]["operator_id"]
    results = []
    for _, task in tasks.nsmallest(3, "estimated_minutes").iterrows():
        machine = machines[machines["machine_type"] == task["required_machine_type"]].iloc[0]
        results.append(predictor.predict(_request(
            task["task_id"], operator, machine["machine_id"])))
    for _, task in tasks.nlargest(3, "estimated_minutes").iterrows():
        machine = machines[machines["machine_type"] == task["required_machine_type"]].iloc[0]
        results.append(predictor.predict(_request(
            task["task_id"], operator, machine["machine_id"])))
    short = results[:3]
    long = results[3:]
    short_width = np.mean([r["upper_bound"] - r["lower_bound"] for r in short])
    long_width = np.mean([r["upper_bound"] - r["lower_bound"] for r in long])
    assert long_width > short_width


def test_bounds_are_not_a_fixed_percentage(trained):
    """Guards against someone reintroducing an arbitrary +/-10%."""
    _, metadata = trained
    u = metadata["uncertainty"]
    assert not (u["ratio_lower"] == 0.9 and u["ratio_upper"] == 1.1)


# ---------------------------------------------------------------------------
# 10. explainability
# ---------------------------------------------------------------------------

def test_feature_importance_artifact_is_complete(trained):
    out, metadata = trained
    with open(os.path.join(out, T.IMPORTANCE_FILENAME), encoding="utf-8") as handle:
        importance = json.load(handle)
    assert importance["native_kind"] in (
        "random_forest_feature_importances", "linear_regression_coefficients")
    assert importance["native"]
    names = {row["feature"] for row in importance["permutation_importance"]}
    assert names == set(metadata["features"])


def test_permutation_importance_is_sorted_descending(trained):
    out, _ = trained
    with open(os.path.join(out, T.IMPORTANCE_FILENAME), encoding="utf-8") as handle:
        rows = json.load(handle)["permutation_importance"]
    values = [row["importance"] for row in rows]
    assert values == sorted(values, reverse=True)


def test_explain_returns_top_features(predictor, trained):
    out, _ = trained
    top = predictor.explain(out, top_n=3)
    assert len(top) == 3
    assert all("feature" in row and "importance" in row for row in top)


# ---------------------------------------------------------------------------
# 11. the shipped artifact in ml/models (if training has been run)
# ---------------------------------------------------------------------------

def test_shipped_artifact_loads_and_predicts(reference):
    if not os.path.exists(os.path.join(T.MODEL_DIR, T.MODEL_FILENAME)):
        pytest.skip("ml/models artifact not present - run the training script")
    shipped = P.TaskDurationPredictor.load(T.MODEL_DIR, D.DATA_DIR)
    tasks, operators, machines = reference
    result = shipped.predict(_request(
        tasks.iloc[0]["task_id"], operators.iloc[0]["operator_id"],
        machines.iloc[0]["machine_id"]))
    assert list(result.keys()) == P.CONTRACT_OUTPUT_KEYS
    assert result["lower_bound"] <= result["predicted_minutes"] <= result["upper_bound"]


def test_missing_artifact_raises_a_clear_error(tmp_path):
    with pytest.raises(P.ModelNotTrainedError):
        P.TaskDurationPredictor.load(str(tmp_path), D.DATA_DIR)

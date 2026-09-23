# Task Duration Prediction Model

Module 2 output. Owner: **Claude A**. Branch: `feature/core-ai`.

> ## SYNTHETIC DATA DISCLAIMER
>
> This model is trained entirely on the **synthetic** data produced by Module 1
> (`scripts/data_generation/`, seed 42). Every metric on this page is measured
> on synthetic data.
>
> **These numbers describe performance on synthetic data only. They do not
> represent real-world Caterpillar performance**, and no claim about real
> machines, operators or sites should be drawn from them.

Implements the **task prediction contract** (`docs/contracts.md` §1). The
contract was not modified.

---

## 1. Target

| | |
|---|---|
| Target column | `task_history.actual_minutes` |
| Units | **minutes** |
| Transform | **none** (raw minutes) |
| Task | regression |

Observed distribution across the 3000 history rows: min 51.6, max 941.3, mean
274.4, median 255.5, sd 141.3. Skew is mild (mean/median = 1.074), so a log
transform was not justified; raw minutes keep MAE and RMSE directly readable.

Predictions are clamped to `[5, 2000]` minutes — the lower bound matches the
generator's floor, the upper is a runaway guard, not a tuning knob.

---

## 2. Features — 15

Every feature is known **before** the task runs and is resolvable at inference
from the contract's three ids plus `environment`.

| Feature | Type | Resolved from | Why |
|---|---|---|---|
| `task_type` | categorical (7) | `tasks(task_id)` | sets the baseline minutes-per-unit rate |
| `difficulty` | numeric 1–5 | `tasks(task_id)` | direct duration driver |
| `quantity` | numeric | `tasks(task_id)` | primary driver |
| `terrain` | categorical (3) | `tasks(task_id)` | FLAT/SLOPED/ROUGH affects pace |
| `estimated_minutes` | numeric | `tasks(task_id)` | the planner's estimate; model learns the correction |
| `skill_level` | categorical (3) | `operators(operator_id)` | strongest operator effect |
| `experience_years` | numeric | `operators(operator_id)` | finer than the skill band |
| `machine_type` | categorical (5) | `machines(machine_id)` | class capability |
| `age_years` | numeric | `machines(machine_id)` | proxy for wear |
| `condition_rating` | numeric | `machines(machine_id)` | direct machine-condition effect |
| `temperature` | numeric | `contract.environment` | contract field |
| `rainfall` | numeric | `contract.environment` | contract field |
| `humidity` | numeric | `contract.environment` | contract field |
| `wind_speed` | numeric | `contract.environment` | contract field |
| `visibility` | numeric | `contract.environment` | contract field |

4 categorical (one-hot, `handle_unknown="ignore"`), 11 numeric
(`StandardScaler`). The feature list lives in `ml/features.py` as a single
constant so the decisions stay auditable.

---

## 3. Leakage decisions

The feature set is enforced by `assert_no_leakage()`, called before every fit.
A test proves the guard actually fires for each forbidden column, so it cannot
degrade into decoration.

### Hard leakage — excluded

| Excluded | Reason |
|---|---|
| **all 23 `telemetry.csv` columns** | `recorded_at == completed_at`; the table is post-completion. `runtime_minutes` **equals `actual_minutes` on 3000/3000 rows** — it is the target restated. |
| **`machines.engine_hours`** | Verified to be the **final accumulated reading after all history** (equals the max telemetry reading on 25/25 machines). Using it for a March task reads a September value. |
| `completed_at` | post-completion by definition |
| `safety_events.*` | derived from post-completion telemetry |

`ml/data.py` never opens `telemetry.csv` or `safety_events.csv`, so these
cannot reach the model even by accident.

### Redundant — excluded

| Excluded | Reason |
|---|---|
| `quantity_unit` | determined 1:1 by `task_type` (7 pairs for 7 task types) |
| `required_machine_type` | identical to the machine's `machine_type` on all 3000 rows |
| `weather` | a deterministic function of the five environment values **and not a field in the contract input** — using it would force the serving layer to replicate a generator rule |
| `model`, `home_zone`, `capacity_units` | no duration effect; `model` is redundant with `machine_type` |

### Non-causal — excluded

| Excluded | Reason |
|---|---|
| `priority` | the generator applies **no** duration effect. Measured mean `actual/quantity` by level: CRITICAL 3.168, HIGH 3.084, LOW 3.087, MEDIUM 3.123 — no ordering |
| `business_value` | derived from `priority` × `quantity`; a noisy proxy for `quantity`, which is already a feature |
| `certifications` | gates *whether* an operator may run a machine (Module 3's concern), not how fast |

### Dropped by coordinator decision

| Dropped | Reason |
|---|---|
| `shift` | not present on `tasks.csv` and not in the contract input. `operators.primary_shift` matches `task_history.shift` on 3000/3000 synthetic rows, but that does not make it a reliable inference-time representation of the actual shift. Dropped for v1 rather than changing the contract. |

### Identifiers and split-only

`history_id`, `task_id`, `operator_id`, `machine_id`, `name` are **join keys
only** — high-cardinality ids invite memorisation. `shift_date` and
`started_at` are used **only** to build the split.

### Deferred

`historical_efficiency` (an operator's past `actual/estimated` ratio) needs an
expanding window to avoid leaking the test period into training. Not in v1.

---

## 4. Data split

**Chronological by `shift_date`.** Earlier → train, middle → validation,
latest → test. This matches the deployment question ("predict next week from
what we have seen") and stops a random split from scattering one period across
all three sets.

Boundaries are **hardcoded constants** in `ml/data.py`, not recomputed
quantiles, so the split is reproducible.

| Split | Date range | Rows | Share |
|---|---|---:|---:|
| Train | 2026-03-27 → 2026-07-11 | 1797 | 59.9% |
| Validation | 2026-07-12 → 2026-08-16 | 598 | 19.9% |
| Test | 2026-08-17 → 2026-09-23 | 605 | 20.2% |

`TRAIN_END = "2026-07-12"`, `VAL_END = "2026-08-17"` (both exclusive upper
bounds).

Verified by test:

- **0 `task_id` shared between any two splits** — each task occurs once
- **every categorical level appears in train** — no unseen category at inference
- splits are strictly ordered in time with no overlap

Operators (40) and machines (25) do recur across splits. That is intended:
they are recurring real-world entities, and since no identifier is a feature,
recurrence cannot leak.

**The test split was scored once, at the end.** All model selection and
hyperparameter choice used validation only.

---

## 5. Models compared

| Model | Description |
|---|---|
| **Baseline 0 — planner estimate** | predict `estimated_minutes` directly; no training. The incumbent the system must beat. |
| **Baseline 1 — train mean** | predict the training mean (271.9 min). The R² = 0 reference point. |
| **Baseline 2 — Linear Regression** | OneHot + StandardScaler + `LinearRegression` |
| **Candidate — Random Forest (validation-selected)** | OneHot + StandardScaler + `RandomForestRegressor(random_state=42)`, grid winner. Scored in full, **not shipped** |
| **Deployment — Random Forest (compact)** | same pipeline, compact configuration. **This is the shipped artifact** |
| **Ablation — Random Forest, 14 features** | compact configuration without `estimated_minutes` |

**No XGBoost.** `CLAUDE.md` says "XGBoost only where useful"; Random Forest
already reaches R² 0.95 on the held-out test split, so a new dependency was
not justified.

Hyperparameter search: 18 configurations (`n_estimators` ∈ {200, 400},
`max_depth` ∈ {None, 12, 20}, `min_samples_leaf` ∈ {1, 2, 4}), scored by
**validation MAE**. All 18 landed within **0.14 MAE** of each other
(24.08–24.22) — hyperparameters barely matter on this data.

### Two configurations, both recorded

| | Validation-selected | **Deployment (shipped)** |
|---|---|---|
| `n_estimators` | 400 | **200** |
| `max_depth` | None | **None** |
| `min_samples_leaf` | 1 | **4** |
| Chosen by | lowest validation MAE | human decision on the size/accuracy tradeoff |
| Validation MAE | 24.08 | 24.17 |
| Test MAE | 22.38 | 22.57 |
| Artifact size | 65,250,234 B (65.25 MB) | **6,686,970 B (6.69 MB)** |
| Shipped | No | **Yes** |

**Measured tradeoff: +0.1863 minutes of test MAE (about 11 seconds) for a
9.76x smaller artifact.**

The compact configuration is shipped by explicit human decision. The accuracy
cost is negligible for this prototype — 11 seconds on predictions averaging
over four hours — while a 6.7 MB artifact is materially easier to deploy, demo
and distribute than a 65 MB one.

The validation-selected configuration is **not hidden**: it is trained, scored
on all three splits and written to `task_duration_metadata.json` under
`models.candidate_random_forest_validation_selected` and
`configuration_choice.validation_selected`, with its measured artifact size.
Tests assert both configurations stay recorded and that the stated tradeoff is
arithmetically consistent with the measured sizes.

---

## 6. Metrics

**Measured on synthetic data.** MAE, RMSE and R² are primary; MAPE is a
secondary readable figure (safe here — no target value below 10 minutes).

### Validation — used for model selection

| Model | MAE | RMSE | R² | MAPE | n |
|---|---:|---:|---:|---:|---:|
| Baseline 0 — planner estimate | 57.78 | 78.40 | 0.7071 | 19.42% | 598 |
| Baseline 1 — train mean | 112.67 | 144.90 | −0.0004 | 59.41% | 598 |
| Baseline 2 — Linear Regression | 24.41 | 33.92 | 0.9452 | 10.34% | 598 |
| Candidate — RF validation-selected (not shipped) | 24.08 | 35.38 | 0.9404 | 8.87% | 598 |
| **Deployment — RF compact (shipped)** | **24.17** | 35.59 | 0.9396 | 8.85% | 598 |
| Ablation — RF compact without estimate | 29.42 | 41.80 | 0.9167 | 11.25% | 598 |

### Test — held out, scored once

| Model | MAE | RMSE | R² | MAPE | n |
|---|---:|---:|---:|---:|---:|
| Baseline 0 — planner estimate | 53.49 | 71.50 | 0.7264 | 18.62% | 605 |
| Baseline 1 — train mean | 108.05 | 136.84 | −0.0020 | 56.32% | 605 |
| Baseline 2 — Linear Regression | 23.15 | 30.47 | 0.9503 | 10.08% | 605 |
| Candidate — RF validation-selected (not shipped) | 22.38 | 30.40 | 0.9505 | 8.61% | 605 |
| **Deployment — RF compact (shipped, final)** | **22.57** | **30.70** | **0.9496** | **8.66%** | 605 |
| Ablation — RF compact without estimate | 29.31 | 39.88 | 0.9149 | 11.62% | 605 |

Training-split metrics are recorded in the metadata artifact. The forest's
train MAE is far below its validation MAE, which is normal for a forest with
little pruning; for the shipped model, validation and test agree closely
(24.17 vs 22.57), so it is not overfitting in any way that harms
generalisation.

### What the numbers mean

- **The shipped model beats the planner's estimate by 58%** on test MAE (53.49 → 22.57 minutes).
- **Without `estimated_minutes` it still beats the planner by 45%** (53.49 → 29.31). The model contributes real predictive value independently of the incumbent estimate.
- Linear Regression is already strong (test MAE 23.15) because the generator is largely a product of known factors. The shipped forest wins by only 0.58 minutes.
- The compact configuration costs **0.19 minutes** of test MAE against the validation-selected one (22.57 vs 22.38).
- A floor exists: the generator applies bounded lognormal noise (σ=0.08, clipped to [0.85, 1.20]) plus 8–20 minutes of random setup. No model can predict that away.

---

## 7. Uncertainty method

**Empirical multiplicative residual quantiles, calibrated on the validation
split.**

1. Fit the final model on **train** only.
2. Predict on **validation**; compute `ratio_i = actual_i / predicted_i`.
3. `ratio_lower = P10(ratio)`, `ratio_upper = P90(ratio)` — a nominal **80%** interval.
4. Clamp so `ratio_lower ≤ 1 ≤ ratio_upper`, guaranteeing the interval contains the point prediction.
5. Persist both ratios in the metadata artifact.
6. At inference: `lower_bound = predicted × ratio_lower`, `upper_bound = predicted × ratio_upper`.

**Calibrated values (shipped compact model):** `ratio_lower = 0.8753`,
`ratio_upper = 1.1512`.

Recalibrated from scratch for the compact model — the quantiles are a property
of the model's own validation residuals, so they were not carried over from the
validation-selected configuration.

Multiplicative rather than additive because error scales with duration — a
fixed ±40 minutes is absurd for a 60-minute task and trivial for a 900-minute
one. It also guarantees `lower_bound > 0` whenever the prediction is positive.

**The final model is deliberately fitted on train only**, not train+validation,
so the validation-derived quantiles remain valid out-of-sample.

### Measured coverage — honest reporting

| Split | Nominal | **Measured** | Mean interval width |
|---|---:|---:|---:|
| Validation | 80% | 79.93% | 74.8 minutes |
| **Test** | 80% | **78.68%** | 74.7 minutes |

Test coverage of 78.68% against a nominal 80% is what the method actually
achieved on unseen data. The quantiles were **not** tuned against the test set
to improve this number.

These are not arbitrary ±10% bounds; a test asserts the ratios are not
`(0.9, 1.1)`.

---

## 8. Final model selection

**`deployment_random_forest_compact`** —
`RandomForestRegressor(n_estimators=200, max_depth=None, min_samples_leaf=4,
random_state=42)` inside a `ColumnTransformer` pipeline.

Selection happened in two steps, and both are recorded:

1. **Validation MAE** picked `n_estimators=400, min_samples_leaf=1` out of the
   18-configuration grid (24.08 MAE). That model is scored in full but not
   shipped, because its artifact is 65.25 MB.
2. **A human decision on the size/accuracy tradeoff** selected the compact
   configuration as the serving artifact: 6.69 MB for +0.1863 minutes of test
   MAE, a 9.76x size reduction for roughly 11 seconds of accuracy.

Random Forest's margin over Linear Regression is small (test MAE 22.57 vs
23.15). Linear Regression remains a legitimate alternative if an even smaller,
fully interpretable artifact matters more than 0.58 minutes.

---

## 9. Artifact structure

All under `ml/` — **nothing in `backend/app/`**. Serving integration is a later
coordinated module.

```
ml/requirements.txt                    training deps (separate from the shared
                                       backend/requirements.txt)
ml/features.py                         feature lists, leakage guards, preprocessor
ml/data.py                             loading, joining, chronological split
ml/training/train_task_duration.py     training entrypoint (CLI)
ml/predict.py                          contract-shaped predict() - pure function
ml/tests/test_task_duration.py         49 tests

ml/models/task_duration_model.joblib   fitted Pipeline (preprocessing + estimator)
ml/models/task_duration_metadata.json  split, features, all metrics, uncertainty,
                                       leakage guard, versions, source data hash
ml/models/feature_importance.json      native importances + permutation importance
```

`ml/models/*` is gitignored. The artifact is reproducible from seed 42 plus the
training script. The metadata records the **SHA-256 of `task_history.csv`**
(`1aa7c12a70cd690a…`), so a stale artifact is detectable.

The joblib file holds the **whole pipeline**, so preprocessing can never drift
from the model it was fitted with.

### Reproducing

```bash
pip install -r ml/requirements.txt
python -m scripts.data_generation.generate        # Module 1 data, seed 42
python -m ml.training.train_task_duration         # writes ml/models/
python -m pytest ml/tests -q                      # 49 tests
```

---

## 10. Explainability

Deterministic model information, no SHAP and no new dependency:

- **Permutation importance** on validation — the increase in validation MAE (minutes) when a feature is shuffled. More trustworthy than impurity importance.
- **Native importances** (`feature_importances_` for the forest, coefficients for Linear Regression) over the encoded feature names.
- **`TaskDurationPredictor.explain(top_n)`** returns the top features so Module 10's assistant can cite model facts rather than inventing reasons.

Top features by permutation importance (validation):

| Feature | MAE increase when shuffled |
|---|---:|
| `estimated_minutes` | 126.63 min |
| `terrain` | 5.08 min |
| `experience_years` | 3.86 min |
| `skill_level` | 1.63 min |
| `condition_rating` | 0.33 min |
| `humidity` | 0.16 min |
| `visibility` | 0.13 min |
| `quantity` | 0.11 min |

Measured on the shipped compact model.

`estimated_minutes` dominates because it already encodes
`quantity × rate × difficulty`. That is **collinearity, not a bug**: the
downstream features look small because their information is largely contained
in the estimate. The ablation model (without the estimate) confirms the rest of
the feature set carries real signal on its own — test MAE 29.31 vs the
planner's 53.49.

---

## 11. Sanity checks

All figures below are from the **shipped compact model**. Asserted by tests
across a 110-request sweep covering **3 skill levels × 7 task types × 5 weather
cases, plus all 5 machine types**:

- `predicted_minutes > 0`, `lower_bound > 0`
- `lower_bound ≤ predicted_minutes ≤ upper_bound`
- no NaN or infinite values
- all predictions within 5–1500 minutes
- extreme environments (45 °C / 40 mm rain / 0.5 km visibility, and the dry
  cold end) do not break prediction
- unknown `task_id` / `operator_id` / `machine_id` raise `UnknownEntityError`
- malformed requests raise `InvalidRequestError`
- a reloaded artifact reproduces predictions exactly

Observed behaviour on the shipped model — same task `T009` (EXCAVATION,
difficulty 3, 89 m³, planner estimate 234 min), same machine:

| Operator | Prediction | Interval |
|---|---:|---|
| BEGINNER (2 y) | 361 min | 316–416 |
| INTERMEDIATE (3 y) | 290 min | 254–334 |
| EXPERT (14 y) | 248 min | 217–286 |

Same task and operator, varying weather:

| Weather | Prediction | Interval |
|---|---:|---|
| CLEAR | 286 min | 250–329 |
| RAIN (6 mm) | 318 min | 278–366 |
| HEAVY_RAIN (22 mm) | 332 min | 290–382 |
| FOG (1.2 km visibility) | 316 min | 277–364 |

The orderings (beginner slowest, rain slower than clear) were **learned from
the data**, not encoded in the model. The model is not expected to reproduce
the generator exactly, and it does not.

---

## 12. Contract compliance

`docs/contracts.md` §1 was **not modified**.

**Input** — accepted exactly as specified:

```json
{
  "task_id": "T001",
  "operator_id": "OP001",
  "machine_id": "M001",
  "environment": {
    "temperature": 29, "rainfall": 0, "humidity": 65,
    "wind_speed": 8, "visibility": 9.5
  }
}
```

**Output** — exactly four keys, in contract order, whole minutes:

```json
{
  "task_id": "T001",
  "predicted_minutes": 290,
  "lower_bound": 254,
  "upper_bound": 334
}
```

`task_id` is echoed unchanged. Tests assert the output key set is exactly
`{task_id, predicted_minutes, lower_bound, upper_bound}` — no extra fields
leak into the contract surface.

The contract states that task, operator and machine attributes are resolved
from the data store by id, and `TaskDurationPredictor` does exactly that: the
caller never passes a feature vector.

---

## 13. Known limitations

1. **Synthetic data only.** Every metric here is measured on data generated by `scripts/data_generation/`. Nothing on this page describes real-world Caterpillar performance.
2. **The model partly learns the generator.** Because the synthetic duration model is a bounded-noise product of known factors, R² 0.95 is *expected* and says more about the generator than about real construction work. Real operational data would be noisier.
3. **`estimated_minutes` dominates.** The model is largely a learned correction to the planner's estimate. If real planner estimates are less well-behaved than the synthetic ones, performance will differ. The 14-feature ablation is the more conservative reading.
4. **Random Forest's margin over Linear Regression is small** — 0.58 minutes test MAE (22.57 vs 23.15). Linear Regression is a legitimate alternative if an even smaller, fully interpretable artifact matters more.
5. **The shipped model is not the most accurate one measured.** The compact configuration was chosen for deployment over the validation-MAE winner: 6.69 MB instead of 65.25 MB, at a cost of 0.1863 minutes of test MAE. Both configurations are trained, scored and recorded in the metadata, so the tradeoff is auditable rather than hidden. If accuracy ever matters more than artifact size, switch `DEPLOYMENT_PARAMS` in `ml/training/train_task_duration.py` to `{n_estimators: 400, max_depth: None, min_samples_leaf: 1}` and retrain.
6. **No `shift` feature.** Dropped by decision; a real deployment would carry the actual shift on the task record.
7. **No temporal features.** Day of week, season and crew fatigue are not modelled. The generator does not produce them.
8. **Interval is marginal, not conditional.** One pair of ratios is applied to every prediction, so the interval does not widen for genuinely harder-to-predict inputs. Quantile regression would fix this; out of scope for a prototype.
9. **Measured coverage is 78.68%, not 80%.** Reported as measured, not tuned. The quantiles were recalibrated from the compact model's own validation residuals, not carried over.
10. **Cold start.** An operator or machine absent from the reference tables raises `UnknownEntityError`. There is no fallback to a class average.
11. **Floating-point determinism.** With `n_jobs=-1`, thread reduction order can move RMSE/MAPE in the 15th significant digit. The fitted model and its predictions are identical; metrics are compared with a 1e-9 relative tolerance.

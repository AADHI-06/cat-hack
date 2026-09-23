# Synthetic Data

Module 1 output. Owner: **Claude A**.

> ## SYNTHETIC DATA DISCLAIMER
>
> Every record in `data/generated/` is **synthetic**, produced by
> `scripts/data_generation/generate.py` from a fixed seed. It describes no real
> machine, operator, site or job.
>
> **This is not real Caterpillar operational data and must never be presented
> as such.** Every row carries `data_source = "synthetic"`, and any metric
> later measured on this data describes performance on synthetic data only.

This file is the **schema source** for Claude B, as stated in
`docs/contracts.md` §6 ("column-level definitions are produced in Module 1").

---

## 1. How to generate

```bash
# from the repository root
python -m scripts.data_generation.generate              # writes data/generated/
python -m scripts.data_generation.validate              # 138 checks
python -m pytest scripts/data_generation/tests -q       # 50 tests
```

Options: `--out <dir>` and `--seed <int>` on the generator, `--data <dir>` on
the validator.

**Seed: 42** (`config.SEED`). Two runs with the same seed produce
byte-identical CSVs. `data/generated/manifest.json` records the seed, the
reference date, row/column counts and a SHA-256 per file.

Generated CSVs are **not committed** — `.gitignore` excludes
`data/generated/*`. Regenerate them instead; the seed guarantees the same
bytes.

---

## 2. Files

| File | Rows | Cols | Grain |
|------|-----:|-----:|-------|
| `operators.csv` | 40 | 7 | one row per operator |
| `machines.csv` | 25 | 10 | one row per machine |
| `tasks.csv` | 200 | 16 | one row per **pending** task (the backlog) |
| `task_history.csv` | 3000 | 25 | one row per **completed** execution — the ML training set |
| `telemetry.csv` | 3000 | 23 | one row per completed execution |
| `safety_events.csv` | 272 | 10 | one row per detected safety condition |
| `manifest.json` | - | - | seed, counts, SHA-256 per file |

Tables not generated here: `incidents` (Module 6, coordinated),
`training_modules` and `training_progress` (Claude B). Anomaly **records** are
not generated either — Module 5 *detects* them; this module injects detectable
patterns into telemetry instead (§7).

**Reference date:** `2026-09-23`. History spans the preceding 180 days
(`2026-03-27` to `2026-09-23`); pending tasks are scheduled across the next 3
days.

---

## 3. Column definitions

Units are fixed as the architecture requires: **durations in minutes**,
timestamps **ISO-8601**, ratios as floats in **0.0–1.0**.

### 3.1 `operators.csv`

| Column | Type | Domain / range | Meaning |
|---|---|---|---|
| `operator_id` | str | `OP001`–`OP040`, unique | primary key |
| `name` | str | - | synthetic name |
| `skill_level` | str | `BEGINNER` / `INTERMEDIATE` / `EXPERT` | drives the duration model |
| `experience_years` | int | 0–25 | correlated with `skill_level` |
| `certifications` | str | `\|`-separated, from the 7 known certs | machine classes the operator may run |
| `primary_shift` | str | `DAY` / `NIGHT` | shift assignment |
| `data_source` | str | `synthetic` | synthetic marker |

Certifications: `EXCAVATOR_OP`, `DOZER_OP`, `LOADER_OP`, `HAUL_TRUCK_OP`,
`GRADER_OP`, `CONFINED_SPACE`, `BLASTING_AWARE`.

### 3.2 `machines.csv`

| Column | Type | Domain / range | Meaning |
|---|---|---|---|
| `machine_id` | str | `M001`–`M025`, unique | primary key |
| `machine_type` | str | `EXCAVATOR` / `DOZER` / `LOADER` / `HAUL_TRUCK` / `GRADER` | class |
| `model` | str | e.g. `CAT 320` | illustrative synthetic designation |
| `year_manufactured` | int | 2012–2026 | `reference_year - age_years` |
| `age_years` | int | 0–14 | drives `condition_rating` |
| `engine_hours` | float | ≥ 0 | **current** hours = final telemetry reading |
| `condition_rating` | float | 0.55–1.00 | 1.0 = as-new; lower is slower and thirstier |
| `capacity_units` | float | by type | nominal capacity |
| `home_zone` | str | `ZONE_A`–`ZONE_D` | base location |
| `data_source` | str | `synthetic` | synthetic marker |

`condition_rating = clamp(1 - 0.030 × age_years + noise(σ=0.05), 0.55, 1.00)`.
Derived from age only and held constant across the history window, so there is
no circular dependency with accumulated hours.

### 3.3 `tasks.csv` — pending backlog

Consumed by the optimizer (Module 3) and the dashboards (Modules 8–9).

| Column | Type | Domain / range | Meaning |
|---|---|---|---|
| `task_id` | str | `T001`–`T200`, unique | primary key |
| `task_type` | str | 7 values (§4) | kind of work |
| `difficulty` | int | 1–5 | 1 easiest, 5 hardest |
| `quantity` | int | by task type | amount of work |
| `quantity_unit` | str | `m3` / `m` / `m2` / `loads` / `trips` | unit for `quantity` |
| `required_machine_type` | str | machine type | machine class the task needs |
| `required_certification` | str | cert name | certification the operator needs |
| `priority` | str | `LOW` / `MEDIUM` / `HIGH` / `CRITICAL` | urgency |
| `business_value` | int | ~200–2500 | value delivered; rises with priority and quantity |
| `depends_on_task_id` | str | `T###` or **empty** | prerequisite; empty = none |
| `site_zone` | str | `ZONE_A`–`ZONE_D` | location |
| `terrain` | str | `FLAT` / `SLOPED` / `ROUGH` | ground conditions |
| `estimated_minutes` | int | 58–522 | planner's pre-task estimate |
| `status` | str | `PENDING` / `IN_PROGRESS` / `COMPLETED` / `BLOCKED` | current state |
| `shift_date` | date | next 3 days | scheduled day |
| `data_source` | str | `synthetic` | synthetic marker |

`depends_on_task_id` is the only intentionally nullable column here. A
dependency always points at a **lower-numbered task in the same zone**, so the
graph is acyclic by construction. ~15% of tasks have one.

### 3.4 `task_history.csv` — ML training set

One row per completed execution. All columns except `actual_minutes` are known
**before** the task runs, so a model may use any of them as a feature.

| Column | Type | Domain / range | Meaning |
|---|---|---|---|
| `history_id` | str | `TH00001`–`TH03000`, unique | primary key |
| `task_id` | str | `T1001`–`T4000`, unique | **disjoint from `tasks.csv`** |
| `operator_id` | str | → `operators` | who ran it |
| `machine_id` | str | → `machines` | what ran it |
| `task_type` | str | 7 values | kind of work |
| `difficulty` | int | 1–5 | |
| `quantity` | int | by task type | |
| `quantity_unit` | str | 5 values | |
| `required_machine_type` | str | machine type | always matches the machine used |
| `terrain` | str | 3 values | |
| `priority` | str | 4 values | |
| `business_value` | int | ~200–2500 | |
| `shift` | str | `DAY` / `NIGHT` | |
| `shift_date` | date | 2026-03-27 … 2026-09-23 | |
| `started_at` | datetime | ISO-8601 | |
| `completed_at` | datetime | ISO-8601 | `= started_at + actual_minutes` |
| `temperature` | float | 5.0–45.0 °C | **prediction-contract field** |
| `rainfall` | float | 0.0–40.0 mm | **prediction-contract field** |
| `humidity` | float | 20.0–98.0 % | **prediction-contract field** |
| `wind_speed` | float | 0.0–45.0 kph | **prediction-contract field** |
| `visibility` | float | 0.5–10.0 km | **prediction-contract field** |
| `weather` | str | `CLEAR` / `CLOUDY` / `RAIN` / `HEAVY_RAIN` / `FOG` | label derived from the five values above |
| `estimated_minutes` | int | ≥ 5 | planner's estimate — a legitimate feature |
| `actual_minutes` | float | 51.6–941.3 (observed) | **TARGET** |
| `data_source` | str | `synthetic` | synthetic marker |

The five environment columns are the **flattened leaves** of the
`environment` object in the task prediction contract. Same names, one level up.

**No leakage.** The latent multipliers that build `actual_minutes` are never
written to the file. `estimated_minutes` is deliberately blind to operator
skill and weather (§5), which is exactly the gap a trained model can close.
Pending and historical `task_id` ranges do not overlap, so the backlog cannot
appear in a training split.

### 3.5 `telemetry.csv`

| Column | Type | Domain / range | Meaning |
|---|---|---|---|
| `telemetry_id` | str | `TM00001`–`TM03000`, unique | primary key |
| `history_id` | str | → `task_history`, 1:1 | execution this covers |
| `task_id` | str | → `task_history` | |
| `machine_id` | str | → `machines` | |
| `operator_id` | str | → `operators` | |
| `recorded_at` | datetime | ISO-8601 | `= completed_at` |
| `engine_hours_reading` | float | ≥ 0, **non-decreasing per machine** | odometer at completion |
| `runtime_minutes` | float | `= actual_minutes` | total machine-on time |
| `idle_minutes` | float | 0 … `runtime_minutes` | time on but not working |
| `idle_ratio` | float | 0.0–0.95 | `idle_minutes / runtime_minutes` |
| `fuel_used_liters` | float | > 0 (11.1–273.3 observed) | total fuel |
| `fuel_per_unit` | float | > 0 | `fuel_used_liters / quantity` — anomaly feature |
| `load_cycles` | int | ≥ 1 | cycles moved; scales with `quantity` |
| `avg_load_pct` | float | 0.0–100.0 | mean load |
| `load_variance` | float | 3–34 | load stability — anomaly feature |
| `engine_temp_c` | float | 60.0–120.0 | anomaly feature |
| `hydraulic_pressure_psi` | float | 1500–4200 | anomaly feature |
| `max_speed_kph` | float | 0–60 | peak speed; site limit is 25 |
| `seatbelt_fastened_pct` | float | 0.0–100.0 | share of runtime fastened |
| `min_proximity_m` | float | ≥ 0 | closest detected object |
| `proximity_alerts_count` | int | 0–20 | proximity alerts raised |
| `injected_anomaly_type` | str | 4 values or **empty** | **synthetic ground truth — see §7** |
| `data_source` | str | `synthetic` | synthetic marker |

`injected_anomaly_type` is the second intentionally nullable column (empty =
normal operation).

### 3.6 `safety_events.csv`

Matches the **safety event contract** (`docs/contracts.md` §3), plus
`task_id`/`history_id` for traceability.

| Column | Type | Domain / range | Meaning |
|---|---|---|---|
| `event_id` | str | `SE0001`…, unique | primary key |
| `timestamp` | datetime | ISO-8601 | when observed |
| `operator_id` | str | → `operators` | |
| `machine_id` | str | → `machines` | |
| `task_id` | str | → `task_history` | traceability |
| `history_id` | str | → `task_history` | traceability |
| `event_type` | str | `SEATBELT` / `PROXIMITY` / `EXCESSIVE_IDLING` / `OVERSPEED` / `UNCERTIFIED_OPERATION` | observed condition |
| `severity` | str | `LOW` / `MEDIUM` / `HIGH` | |
| `description` | str | one of 5 approved strings | observational wording only |
| `data_source` | str | `synthetic` | synthetic marker |

Approved descriptions, and nothing else:

```
SEATBELT               -> "Seatbelt violation detected"
PROXIMITY              -> "Potential proximity hazard detected"
EXCESSIVE_IDLING       -> "Excessive idling detected"
OVERSPEED              -> "Speed above site limit detected"
UNCERTIFIED_OPERATION  -> "Machine operated outside certified machine class"
```

Each states only the observed condition. None characterises an operator's
character, competence or attitude.

---

## 4. Task types

| Task type | Minutes per unit | Unit | Machine | Quantity range |
|---|---:|---|---|---|
| `EXCAVATION` | 1.8 | m3 | EXCAVATOR | 20–160 |
| `TRENCHING` | 2.6 | m | EXCAVATOR | 15–90 |
| `LOADING` | 1.2 | loads | LOADER | 30–180 |
| `HAULING` | 3.5 | trips | HAUL_TRUCK | 10–70 |
| `GRADING` | 0.9 | m2 | GRADER | 60–400 |
| `BACKFILL` | 1.4 | m3 | DOZER | 25–150 |
| `SITE_CLEARING` | 1.1 | m2 | DOZER | 80–350 |

---

## 5. The duration model

```
actual_minutes = quantity × rate_per_unit
                 × difficulty × skill × machine_condition
                 × terrain × weather × shift
                 × bounded_noise
               + setup_minutes
```

| Factor | Effect | Values |
|---|---|---|
| difficulty | harder is longer | `1 + 0.15 × (d-1)` → 1.00 … 1.60 |
| skill | less experience is longer | BEGINNER 1.30, INTERMEDIATE 1.10, EXPERT 0.95 |
| machine_condition | worn is slower | `1 + 0.35 × (1 - condition_rating)` → up to ~1.16 |
| terrain | rougher is slower | FLAT 1.00, SLOPED 1.08, ROUGH 1.18 |
| rainfall | wet is slower | `1 + 0.008 × min(mm, 25)` → up to 1.20 |
| visibility | poor sight is slower | < 5 km → 1.05; < 2 km → 1.12 |
| wind | high wind is slower | > 30 kph → 1.06 |
| temperature | extremes are slower | > 38 °C → 1.07; < 8 °C → 1.04 |
| shift | night is slower | NIGHT 1.06 |
| noise | bounded variation | lognormal σ=0.08, **clipped to [0.85, 1.20]** |
| setup | fixed overhead | 8–20 minutes |

Floor: `MIN_TASK_MINUTES = 5`. Nothing shorter is ever emitted.

**Relationships are not deterministic.** Bounded noise means an expert on a
hard task can still finish slower than a beginner on an easy one — the
relationship holds in aggregate, which is what makes the data learnable rather
than trivially invertible.

**The planner's estimate** deliberately sees only `quantity`, `rate_per_unit`
and `difficulty`, plus ±8% noise and a flat 12-minute setup. It is blind to
skill, machine condition, weather and shift. Measured on this data,
`actual / estimated` averages **1.515 for beginners, 1.286 for intermediates,
1.127 for experts** — a systematic gap a model can learn.

---

## 6. Environment generation

Environment values are correlated, not independent columns:

- 22% of executions see rain; rainfall is exponential (mean ≈ 6 mm), capped at 40
- humidity rises with rainfall (`+1.6 %` per mm)
- visibility falls with rainfall (`−0.22 km` per mm); 5% of dry executions get fog (0.5–2.5 km)
- temperature falls slightly with rainfall (`−0.15 °C` per mm)
- wind rises slightly with rainfall
- `weather` is then **derived**: `HEAVY_RAIN` ≥ 12 mm, `RAIN` > 0 mm, else `FOG` if visibility < 2 km, else `CLOUDY` if humidity > 70%, else `CLEAR`

Observed mix: CLEAR 1821, RAIN 615, CLOUDY 395, HEAVY_RAIN 88, FOG 81.

---

## 7. Injected machine anomalies

5% of executions (`P_INJECTED_ANOMALY`) receive an abnormal telemetry pattern,
so Module 5 has real structure to find. Observed: **136 of 3000 (4.5%)**.

| `injected_anomaly_type` | Effect | Count |
|---|---|---:|
| `EXCESSIVE_IDLING` | `idle_ratio` 0.40–0.70 (normal 0.05–0.25) | 46 |
| `FUEL_ANOMALY` | fuel × 1.5–2.2 | 35 |
| `LOAD_CYCLE_ANOMALY` | cycles × 0.35–0.60, `load_variance` 18–34 | 31 |
| `OVERHEATING` | `engine_temp_c` 105–118 (normal 78–98) | 24 |
| *(empty)* | normal operation | 2864 |

> **`injected_anomaly_type` is synthetic ground truth for documentation and
> validation only. It must NEVER be used as a model feature.** Module 5's
> detector has to work from the telemetry columns alone; the label exists so
> its output can be checked against what was actually injected.

---

## 8. Safety event derivation

Events are **derived deterministically** from observable telemetry, so every
one traces back to a measurable condition. This is data generation, not the
Module 4 safety engine.

| Event | Condition | Severity thresholds | Injection rate |
|---|---|---|---:|
| `SEATBELT` | `seatbelt_fastened_pct` < 95 | < 70 HIGH, < 85 MEDIUM, else LOW | 3.0% |
| `PROXIMITY` | `min_proximity_m` < 3.0 | < 1.5 HIGH, < 2.5 MEDIUM, else LOW | 2.5% |
| `OVERSPEED` | `max_speed_kph` > 25.0 | > 35 HIGH, > 30 MEDIUM, else LOW | 2.0% |
| `EXCESSIVE_IDLING` | `idle_ratio` > 0.35 | > 0.50 MEDIUM, else LOW | via anomalies |
| `UNCERTIFIED_OPERATION` | operator lacks the required cert | always HIGH | 1.0% |

Observed: **272 events across 267 of 3000 executions (8.9%)** — rare enough to
be meaningful, frequent enough to demonstrate. By type: SEATBELT 81,
PROXIMITY 59, OVERSPEED 58, EXCESSIVE_IDLING 46, UNCERTIFIED_OPERATION 28.
By severity: MEDIUM 121, HIGH 92, LOW 59.

---

## 9. Validation

`python -m scripts.data_generation.validate` runs **138 checks**; the pytest
suite runs **50 tests**. Both pass. Coverage:

| Category | Examples |
|---|---|
| schema | exact column set and order per file |
| row counts | per-file counts; telemetry 1:1 with executions |
| nulls | no blanks outside the two nullable columns |
| unique ids | all six primary keys; `task_history.task_id` |
| referential integrity | 9 foreign keys; dependencies resolve; no self-dependency |
| types | integer and float columns parse |
| numeric ranges | 31 bounded ranges — no negative duration, fuel or engine hours; no impossible humidity, rainfall or ratio |
| categoricals | 19 columns checked against their vocabulary |
| timestamps | ISO-8601 parse; `completed_at` > `started_at`; span equals `actual_minutes` |
| synthetic marker | `data_source = "synthetic"` on every row of every file |
| logical relationships | §10 |
| reproducibility | same seed byte-identical; different seed differs |

Under a **different seed (7)** every data check still passes; the only failure
is the validator asserting the canonical seed 42. The generator is not tuned
to one lucky seed.

---

## 10. Measured relationships

Measured on the seed-42 output, not asserted:

| Relationship | Measurement |
|---|---|
| beginners take longer than experts | `actual/estimated`: BEGINNER 1.515 > INTERMEDIATE 1.286 > EXPERT 1.127 |
| harder tasks take longer per unit of work | d1 1.379 < d2 1.563 < d3 1.750 < d4 1.936 < d5 2.112 |
| larger quantity takes longer | holds in **7 of 7** task types |
| rain extends duration | dry 1.240 (n=2299) vs wet 1.323 (n=307) |
| worn machines are slower | condition < 0.75 → 1.291 (n=847) vs ≥ 0.90 → 1.208 (n=505) |
| more load cycles burn more fuel | bottom decile 33.7 L vs top decile 85.9 L |
| business value rises with priority | LOW 288 < MEDIUM 512 < HIGH 849 < CRITICAL 1370 |
| experience rises with skill | BEGINNER 1.5 y < INTERMEDIATE 5.9 y < EXPERT 15.1 y |
| injected idling is separable | injected min 0.404 > normal max 0.250 |
| engine hours accumulate | non-decreasing per machine across all 25 machines |

---

## 11. Notes for Claude B

1. **Synthetic marker column.** Module 1 materialises the marker as
   `data_source` with the constant value `"synthetic"` on **every row of every
   table**, matching what `backend/app/main.py` already returns. Persistence
   must carry this column through, and the UI should surface synthetic status.
   This names a convention `docs/contracts.md` §7 left unnamed — it is an
   addition, not a change, so no approved contract moved.

2. **Environment fields are flattened.** `task_history.csv` stores
   `temperature`, `rainfall`, `humidity`, `wind_speed`, `visibility` as
   top-level columns. The prediction contract nests the same five names under
   `environment`. Same names, one level of nesting apart.

3. **Two nullable columns only:** `tasks.depends_on_task_id` and
   `telemetry.injected_anomaly_type`. Empty string, not `NULL`, in the CSVs.

4. **`injected_anomaly_type` is ground truth, never a feature** (§7).

5. **Some tasks exceed one shift.** 2 of 200 pending tasks estimate above 480
   minutes, and 8.5% of historical executions ran longer. This is intentional:
   the optimizer (Module 3) needs a reason to exclude work, and the supervisor
   dashboard needs to show it. It is not a data defect.

6. **`tasks.csv` and `task_history.csv` share no `task_id`.** `T001`–`T200` is
   the backlog; `T1001`–`T4000` is history.

7. **Generated CSVs are not committed.** Run the generator after cloning.
   `manifest.json` carries SHA-256 hashes to confirm a matching run.

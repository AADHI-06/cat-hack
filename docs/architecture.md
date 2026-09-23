# Architecture

Project: **CAT Smart Operator Assistant**
Status: planning document written at Module 0. Sections describing later
modules are *intended design*, not implemented behaviour.

Development model: **two Claude accounts working in parallel** - Claude A
(Core AI / Intelligence) and Claude B (Platform / Product). See section 4.

---

## 1. Project Objective

Provide a CAT machinery operator with an assistant that continuously answers
three questions:

1. **What should the operator do next?**
2. **How long will it take?**
3. **Is the current operation safe?**

The operating loop is:

**Predict -> Plan -> Assist -> Monitor -> Learn**

The system is decision support for operators and supervisors. It is a
hackathon prototype. It does not control machinery and does not replace
certified safety systems or human supervision.

---

## 2. System Architecture

A single monolithic application with clearly separated modules. No
microservices.

```
+-------------------------------------------------------------+
|  Frontend (React + Vite + Tailwind)                         |
|    Operator Dashboard        Supervisor Dashboard           |
+---------------------------+---------------------------------+
                            | HTTP / JSON
+---------------------------v---------------------------------+
|  Backend (FastAPI, Python)                                  |
|                                                             |
|  API layer        -> routers per feature                    |
|  Service layer    -> prediction, optimization, safety,      |
|                      anomaly, incidents, training, AI       |
|  Data layer       -> SQLite access + synthetic data gen     |
+---------------------------+---------------------------------+
                            |
        +-------------------+--------------------+
        |                                        |
+-------v---------+                    +---------v---------+
|  SQLite         |                    |  ml/models/       |
|  operational    |                    |  trained model    |
|  data           |                    |  artifacts        |
+-----------------+                    +-------------------+
```

The backend and its deterministic algorithms are the source of truth. Any LLM
is an optional explanation layer on top.

---

## 3. System Boundaries

The system is split into two halves with a contract boundary between them.
This boundary is what makes parallel development possible.

```
============================ INTELLIGENCE SIDE ============================
                    DATA / ML / OPTIMIZATION / SAFETY
                             Owner: CLAUDE A

  synthetic data generation      task duration prediction
  feature engineering            shift task optimization
  model training + artifacts     safety rule engine
  data semantics                 anomaly detection

  Produces: datasets, model artifacts, predictions, plans,
            safety events, anomaly records
  Knows nothing about: HTTP, routers, ORM sessions, React, charts
===========================================================================
                                  |
                                  |   docs/contracts.md
                                  |   (JSON-shaped, stable, versioned
                                  |    by human approval)
                                  v
============================== PLATFORM SIDE ==============================
                 API / DATABASE / FRONTEND / DASHBOARDS
                             Owner: CLAUDE B

  SQLite schema + access layer   HTTP API routers
  request/response models        operator dashboard
  application persistence        supervisor dashboard
  application integration        training hub UI
                                 AI assistant UI

  Consumes: the contracts above
  Knows nothing about: estimators, hyperparameters, feature encodings,
            anomaly thresholds, optimizer internals
===========================================================================
```

**Boundary rules**

1. The platform side never imports from `backend/app/ml/` internals, never
   loads a model artifact directly, and never reimplements a scoring or
   scheduling rule. It calls the intelligence side's service interface.
2. The intelligence side never opens an HTTP request, never touches an ORM
   session, and never formats anything for display.
3. The UI contains **no ML logic**. It renders what the backend returns.
4. Data crossing the boundary is plain Python types or JSON-serializable
   structures matching section 6 - not model objects, DataFrames or numpy
   arrays.
5. Units are fixed at the boundary: durations in **minutes**, timestamps in
   ISO-8601, `utilization` and `score` as floats in `0.0`-`1.0`.
6. Every operational record crossing the boundary keeps its **synthetic
   marker**.

**Why the boundary sits here:** the intelligence side is the part most likely
to be rewritten during a hackathon (retrain, swap estimator, retune
thresholds). Holding it behind a contract means the platform side and the
dashboards keep working while it churns.

---

## 4. Parallel Development Ownership

Two Claude accounts develop this project simultaneously. Every session must
begin by knowing which role it is.

```
                    HUMAN
                      |
                      v
              PROJECT COORDINATOR
                 (ChatGPT)
                      |
          +-----------+-----------+
          |                       |
          v                       v
      CLAUDE A                CLAUDE B
   Core AI / Intelligence   Platform / Product
          |                       |
          v                       v
   feature/core-ai        feature/platform-ui
          |                       |
          +-----------+-----------+
                      |
                      v
                  REVIEW
                      |
                      v
                 INTEGRATION
                      |
                      v
                    main
```

### 4.1 Roles

**Claude A - Core AI / Intelligence owner.** Owns synthetic data generation,
ML training, task duration prediction, shift task optimization, safety
intelligence logic, machine behavior anomaly detection, ML artifacts, and
core AI/business logic.

**Claude B - Platform / Product owner.** Owns database integration, the
backend API layer, application services that expose core functionality, the
frontend, the operator dashboard, the supervisor dashboard, the training hub
UI, AI assistant UI/integration, and application-level integration.

### 4.2 File Ownership

**Claude A ownership paths**

```
data/
ml/
scripts/data_generation/
backend/app/ml/
backend/app/services/optimization/
backend/app/services/safety/
backend/app/services/anomaly/
```

**Claude B ownership paths**

```
backend/app/api/
backend/app/models/
backend/app/services/database/
frontend/
```

**Rule:** neither Claude modifies the other Claude's owned implementation
files unless explicitly instructed during a coordinated integration task.

Sub-packages under `backend/app/` are created by their owner in the module
that first needs them, not pre-created at Module 0.

Tests live next to the code they cover, under the owner's responsibility.

### 4.3 Shared-File Rules

These files are shared and must **not** be modified by both Claudes
simultaneously:

```
CLAUDE.md
README.md
docs/architecture.md
docs/progress.md
docs/contracts.md
backend/requirements.txt
backend/app/main.py
database schema contracts
API contracts
```

Before modifying a shared file, the active Claude must state:

1. **Why** the file needs modification.
2. **What** will change.
3. **Whether the other Claude needs to know** about it.

If both Claude accounts need to modify a shared file, **stop and request
coordination** through the human/coordinator. Do not proceed unilaterally.

`backend/app/main.py` is the highest-risk shared file, because both sides
eventually register things on the app. Router registration is a coordinated
edit, not an incidental one.

### 4.4 Module Ownership

| # | Module | Owner | Coordination notes |
|----|--------|-------|--------------------|
| 0 | Foundation | A | repo, architecture, docs, base backend, rules, branch strategy |
| 1 | Synthetic Data | A | B waits for the data contract; B must not modify A's generator |
| 2 | Task Time Prediction | A | B prepares API integration only after the prediction contract is approved |
| 3 | Shift Task Optimization | A | greedy/knapsack, not an industrial solver |
| 4 | Safety Intelligence | A | B integrates through API/UI |
| 5 | Machine Behavior Anomaly Detection | A | B displays results |
| 6 | Incident Management | A + B | **coordinated** - A: event/incident logic and contract. B: persistence, API, UI |
| 7 | Operator Training Hub | B | A provides recommendation logic only if required |
| 8 | Operator Dashboard | B | UI contains no ML logic |
| 9 | Supervisor Dashboard | B | |
| 10 | AI Assistant | A + B | **coordinated** - A: context logic and structured response data. B: UI and API |
| 11 | End-to-End Integration | Joint | separate approved task |
| 12 | Final QA / Demo / Documentation | Joint | |

Modules 6, 10, 11 and 12 require the coordinator to sequence work so that both
Claudes never edit the same files at once.

Neither Claude independently decides to start another major module. The
coordinator determines next task, dependency ordering, interface changes,
integration timing, and which files each Claude may modify.

### 4.5 Branch Strategy

```
main                   reviewed and integrated work only
feature/core-ai        Claude A development
feature/platform-ui    Claude B development
```

- Default branch is `main`. **No direct development pushes to `main`.**
- Each Claude pushes only its own feature branch.
- Before starting a task: `git fetch origin`, then ensure the local branch is
  based on the latest appropriate state.
- Do **not** blindly rebase or reset the other developer's work.
- `git push --force`, `git reset --hard` and `git clean -fd` require explicit
  human authorization.

Remote: https://github.com/AADHI-06/cat-hack

### 4.6 Interface Contracts

Contracts are the mechanism that makes the ownership split work. Claude A
exposes stable conceptual contracts; Claude B builds against them rather than
depending on internal ML implementation.

Canonical location: **`docs/contracts.md`** (that file also tracks per-contract
approval status). Section 6 below restates them for architectural context; if
the two ever disagree, `docs/contracts.md` wins.

A contract becomes binding when the human approves the module that implements
it. Changing an approved contract is a coordinated task:

1. document the change
2. notify the other Claude through the coordinator
3. update `docs/contracts.md` and any affected contract
4. test compatibility on both sides

Contracts are contracts, not necessarily final API schemas. Claude B may wrap,
rename or nest them when exposing HTTP endpoints. **Do not over-engineer
them.**

### 4.7 Integration Process

Integration is a **separate approved task**, never a side effect of finishing
a module.

Before integration, Claude A provides approved data contracts, ML artifacts,
the optimizer, the safety engine, the anomaly engine, and tests. Claude B
provides the API, database, frontend, dashboards, and training hub.

**Never merge branches simply because both branches compile.** Verify:

1. contracts match
2. imports work
3. APIs work
4. ML artifacts load
5. database schema matches
6. frontend builds
7. end-to-end workflow works

Only then does work reach `main`.

### 4.8 Human Approval Process

Every module follows seven steps:

| Step | Action |
|------|--------|
| 1 - PLAN | objective, files involved, dependencies, interfaces, tests, risks |
| 2 - IMPLEMENT | only the approved scope |
| 3 - VERIFY | unit tests, integration tests where applicable, lint/type checks where applicable, build checks, relevant ML validation |
| 4 - HUMAN REVIEW | **STOP.** Report implementation summary, files changed, tests, known issues, manual verification instructions. **WAIT for explicit human approval.** |
| 5 - COMMIT | after approval only: inspect `git status`, inspect `git diff`, commit the approved scope |
| 6 - PUSH | push ONLY the appropriate feature branch |
| 7 - STOP | do not automatically begin another module |

The human approval step is never skipped. Nothing unapproved is committed or
pushed. `docs/progress.md` records owner, status, tests, approval, commit and
integration state per module.

---

## 5. Main Modules

| # | Module | Owner | Responsibility |
|----|--------|-------|----------------|
| 0 | Foundation | A | Repository, architecture, documentation, base backend, project rules, branch strategy. |
| 1 | Synthetic Data | A | Produce reproducible, clearly labeled synthetic operators, machines, tasks, task history and telemetry. |
| 2 | Task Time Prediction | A | Predict task duration from task, operator, machine and condition features. |
| 3 | Shift Task Optimization | A | Select and order tasks to maximize useful operational value within shift capacity. |
| 4 | Safety Intelligence | A | Raise safety alerts from observable conditions (seatbelt, proximity, idling, speed). |
| 5 | Machine Behavior Anomaly Detection | A | Flag unusual machine behaviour from telemetry. |
| 6 | Incident Management | A + B | A: event/incident logic and contract. B: persistence, API, UI. |
| 7 | Operator Training Hub | B | Training content, completion status, recommendation UI. |
| 8 | Operator Dashboard | B | Today's plan, next task, predicted time, live safety status. |
| 9 | Supervisor Dashboard | B | Fleet and crew overview, utilization, incidents, plan quality. |
| 10 | AI Assistant | A + B | A: context logic and structured response data. B: UI and API integration. |
| 11 | End-to-End Integration | Joint | Wire modules together, end-to-end tests, demo path. |
| 12 | Final QA / Demo / Documentation | Joint | Verify every demo path and finalize documentation. |

---

## 6. Integration Contracts

Restated here for architectural context. Canonical version with approval
status: `docs/contracts.md`.

All four are owned and implemented by **Claude A**, and consumed by
**Claude B**. Durations are in minutes.

### 6.1 Task Prediction Contract

Implemented in Module 2.

**Input**

```json
{
  "task_id": "T001",
  "operator_id": "OP001",
  "machine_id": "M001",
  "environment": {
    "temperature": 29,
    "rainfall": 0,
    "humidity": 65,
    "wind_speed": 8,
    "visibility": 9.5
  }
}
```

**Output**

```json
{
  "task_id": "T001",
  "predicted_minutes": 72,
  "lower_bound": 65,
  "upper_bound": 82
}
```

`predicted_minutes` is the point prediction; the bounds express uncertainty,
not a guarantee. Task, operator and machine attributes are resolved from the
data store by id - the caller does not pass feature vectors.

### 6.2 Optimization Contract

Implemented in Module 3.

**Input (conceptual):** pending tasks, predicted durations, task priorities,
business values, task dependencies, operator suitability, machine
compatibility, shift capacity.

**Output**

```json
{
  "shift_minutes": 480,
  "selected_tasks": [
    {
      "task_id": "T001",
      "order": 1,
      "predicted_minutes": 72
    }
  ],
  "total_predicted_minutes": 420,
  "utilization": 0.875
}
```

`selected_tasks` is in execution order, `order` is 1-based, and
`utilization` = `total_predicted_minutes` / `shift_minutes`. Tasks left out
should be reportable with a reason so the supervisor dashboard can explain
omissions; the exact shape is agreed in Module 3.

### 6.3 Safety Event Contract

Implemented in Module 4.

```json
{
  "event_id": "SE001",
  "timestamp": "2026-09-23T08:14:00",
  "operator_id": "OP001",
  "machine_id": "M001",
  "event_type": "SEATBELT",
  "severity": "HIGH",
  "description": "Seatbelt unfastened"
}
```

Events derive from **observable conditions only**. `description` states the
observed condition and must not characterize an operator's competence,
character or safety attitude.

### 6.4 Anomaly Contract

Implemented in Module 5.

```json
{
  "anomaly_id": "AN001",
  "machine_id": "M001",
  "operator_id": "OP001",
  "anomaly_type": "EXCESSIVE_IDLING",
  "score": 0.91,
  "description": "Idle time is significantly above normal"
}
```

`score` is a normalized anomaly score; higher means more unusual. Wording
stays observational.

### 6.5 Incident Contract

Implemented in Module 6, coordinated between A and B. A safety event or
anomaly is the expected source of an incident. Shape agreed jointly in that
module.

---

## 7. Data Flow

```
Synthetic generator (fixed seed = 42)            [Claude A]
        |
        v
data/generated/*.csv  ->  SQLite (operational store)   [A -> B boundary]
        |                        |
        |                        +--> API reads for dashboards   [Claude B]
        v
data/processed/  (feature tables for ML)         [Claude A]
        |
        v
ml/training/  ->  ml/models/  (trained artifacts) [Claude A]
        |
        v
Backend service layer loads model at startup     [Claude A]
        |
        v
Predictions + plans + alerts  ->  API  ->  Frontend   [A -> B boundary]
        |
        v
Completed tasks and confirmed incidents written back to SQLite  [Claude B]
        |
        +--> feed the next retraining cycle (the "Learn" step)  [Claude A]
```

All synthetic records carry an explicit synthetic marker so no output can be
mistaken for real Caterpillar operational data.

---

## 8. ML Flow

Owner: Claude A. Two models, both trained offline under `ml/training/` and
loaded read-only by the backend.

**Task duration (regression)**

```
features: task type, difficulty, quantity, machine type, operator skill,
          weather, shift, terrain
   |
   v
split into train / validation / test
   (no leakage: no post-task fields, no same-task records across splits)
   |
   v
baseline (mean / linear) -> Random Forest -> XGBoost only if it earns its place
   |
   v
report MAE, RMSE, R2 on the held-out test set - measured values only
```

**Machine anomaly (unsupervised)**

```
telemetry features: idle ratio, fuel per unit output, load variance,
                    engine temperature, hydraulic pressure
   |
   v
Isolation Forest -> anomaly score -> threshold
   |
   v
"Unusual machine behavior detected"
```

Rules that hold throughout: never fabricate metrics, report only what the
model actually produced, and state clearly that performance on synthetic data
does not represent real-world Caterpillar performance.

---

## 9. Optimization Flow

Owner: Claude A.

```
inputs: pending tasks, predicted durations, priorities, business values,
        operator suitability and certifications, machine compatibility,
        task dependencies, remaining shift capacity
   |
   v
filter  : drop tasks whose machine, operator or certification
          requirements cannot be met
   |
   v
order   : respect dependencies (a task cannot precede its prerequisite)
   |
   v
select  : greedy / knapsack-style on value density
          score = f(business value, priority) / predicted duration
   |
   v
output  : ordered shift plan + total predicted time + utilization
          + unscheduled tasks with the reason each was left out
```

The objective is to **maximize useful operational value within available shift
capacity**, not to maximize the count of tasks. The algorithm stays a simple
greedy or knapsack approach, not an industrial scheduling engine.

---

## 10. Safety Flow

Owner: Claude A (logic). Claude B integrates through API and UI.

```
telemetry + task context
   |
   v
deterministic rule checks (observable conditions only):
   - seatbelt engaged while machine in motion
   - proximity distance below threshold
   - idle duration above threshold
   - speed above site limit for the zone
   - operating outside certified machine class
   |
   v
severity (LOW / MEDIUM / HIGH)
   |
   v
safety event record  ->  operator alert  +  incident  +  supervisor dashboard
```

Alert wording is restricted to observable facts, for example "Seatbelt
violation detected", "Potential proximity hazard", "Excessive idling
detected", "Unusual machine behavior detected". The system makes no claims
about an operator's character or competence, and it does not replace certified
safety systems or human supervision.

---

## 11. Operator Dashboard

Owner: Claude B. Purpose: tell one operator what to do next, how long it
should take, and whether the current operation is safe.

Displays: operator, machine, shift, today's tasks, current task, predicted
duration, task priority, task status, weather, safety status, alerts, shift
progress.

- **Next task card** - task, machine, location, predicted duration with the
  main factors behind that prediction
- **Today's plan** - ordered task list with progress and running time vs plan
- **Safety status** - current alerts with severity, plus an acknowledge action
- **Machine status** - assigned machine, key telemetry, anomaly flag
- **Training prompts** - short suggestions tied to the operator's skill gaps

Clean, industrial, readable, responsive. No decorative animation or 3D. The UI
contains no ML logic; it consumes backend contracts.

---

## 12. Supervisor Dashboard

Owner: Claude B. Purpose: give a supervisor the state of the crew and fleet
for the shift.

Displays: active machines, operators, task progress, shift utilization, safety
events, incidents, anomalies, machine utilization, operator performance.

- **Shift overview** - planned vs predicted vs actual completion
- **Crew view** - operators, assigned machines, current task, on or off plan
- **Fleet utilization** - machine hours, idle share, anomaly flags
- **Incident feed** - open safety and anomaly incidents, severity, status
- **Plan quality** - value scheduled vs shift capacity, tasks left out and why

---

## 13. Planned Technology Stack

**Backend**

- Python 3.13
- FastAPI (API), Uvicorn (server)
- SQLite (operational store)
- Pandas, NumPy (data handling)
- scikit-learn (Random Forest, Isolation Forest)
- XGBoost only where it demonstrably helps
- pytest, httpx (tests)

**Frontend**

- React + Vite
- Tailwind CSS
- Recharts or equivalent for charts

**Repository layout** (owner in brackets)

```
backend/
  app/
    main.py                     [shared]  app entrypoint
    ml/                         [A]       models, training glue, inference
    services/
      optimization/             [A]       shift optimizer
      safety/                   [A]       safety rule engine
      anomaly/                  [A]       anomaly detection
      database/                 [B]       persistence and access layer
    api/                        [B]       HTTP routers
    models/                     [B]       request/response and ORM models
  tests/                        [both]    tests alongside owned code
  requirements.txt              [shared]
data/         [A]  raw / processed / generated  (generated data not committed)
ml/           [A]  training scripts, model artifacts, notebooks
scripts/      [A]  data_generation/ and developer utilities
docs/         [shared]  architecture, progress, contracts
frontend/     [B]  React application (added in a later module)
```

Sub-packages under `backend/app/` are created by their owner in the module
that first needs them, not pre-created at Module 0.

Dependencies are added in the module that first needs them, not up front. As
of Module 0 only FastAPI, Uvicorn, pytest and httpx are installed.

---

## 14. Non-Goals

- Not a production industrial control system
- Not a replacement for certified safety systems or human supervision
- No microservices, Kubernetes, Redis, Kafka, or distributed infrastructure
  without explicit approval
- No machine actuation or emergency-system control from the AI layer
- No complicated industrial scheduling solver
- No unnecessary authentication or external APIs
- No hard dependency on an external LLM: the application must work fully
  without one

Priorities: **WORKING > COMPLEX**, **DEMONSTRABLE > ENTERPRISE**,
**UNDERSTANDABLE > ABSTRACT**.

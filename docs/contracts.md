# Interface Contracts

**Purpose:** allow Claude A (Core/AI) and Claude B (Platform/UI) to build in
parallel without reading each other's implementation.

**The rule:** Claude B builds against the contracts on this page, never against
Claude A's internal ML or algorithm code. Claude A may change internals freely
as long as the contract holds.

These are **conceptual contracts, not final API schemas**. Claude B may wrap,
rename or nest them when exposing HTTP endpoints. They are deliberately small.
Do not over-engineer them.

**Status:** drafted at Module 0. Each contract becomes binding only when the
human approves the module that implements it. Until then it is a target, and
`Approved` in the table below stays `No`.

| Contract | Implemented by | Becomes binding after | Approved |
|---------------------|----------------|-----------------------|----------|
| Task Prediction | Claude A | Module 2 | No |
| Optimization | Claude A | Module 3 | No |
| Safety Event | Claude A | Module 4 | No |
| Anomaly | Claude A | Module 5 | No |
| Incident | A + B (coordinated) | Module 6 | No |

Changing an approved contract is a coordinated task: document the change,
notify the other Claude through the coordinator, update this file, then test
compatibility on both sides.

---

## 1. Task Prediction Contract

Owner: Claude A. Implemented in Module 2.

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

Notes:

- `predicted_minutes` is the point prediction. `lower_bound` / `upper_bound`
  express prediction uncertainty, not a guarantee.
- Units are minutes throughout the project. No mixed units.
- The model resolves task, operator and machine attributes from the data store
  by id; the caller does not pass feature vectors.

---

## 2. Optimization Contract

Owner: Claude A. Implemented in Module 3.

**Input (conceptual)**

- pending tasks
- predicted durations
- task priorities
- business values
- task dependencies
- operator suitability
- machine compatibility
- shift capacity

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

Notes:

- `selected_tasks` is returned in execution order; `order` is 1-based.
- `utilization` = `total_predicted_minutes` / `shift_minutes`.
- The objective is maximum useful operational value within shift capacity, not
  maximum task count. A greedy or knapsack-style approach is acceptable.
- Tasks left out should be reportable with a reason, so the supervisor
  dashboard can explain omissions. Exact shape agreed in Module 3.

---

## 3. Safety Event Contract

Owner: Claude A. Implemented in Module 4.

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

Notes:

- Events are derived from **observable conditions only**.
- `description` states the observed condition. It must not characterize an
  operator's competence, character or safety attitude.
- This is decision support. It does not replace certified safety systems or
  human supervision.

---

## 4. Anomaly Contract

Owner: Claude A. Implemented in Module 5.

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

Notes:

- `score` is a normalized anomaly score. Higher means more unusual.
- Wording stays observational: "Unusual machine behavior detected",
  "Excessive idling detected".

---

## 5. Incident Contract

Coordinated: Claude A owns event/incident logic, Claude B owns persistence,
API and UI. Implemented in Module 6. Shape agreed jointly in that module; a
safety event or anomaly is the expected source of an incident.

---

## 6. Database Tables

SQLite is the prototype database.

**Claude A owns data semantics** (what the columns mean, what values are
valid, what relationships hold). **Claude B owns application persistence and
database integration** (schema definition in code, migrations, access layer).

Logical tables:

| Table | Semantics owner | Notes |
|--------------------|-----------------|-------------------------------|
| `operators` | Claude A | skill level, certifications |
| `machines` | Claude A | type, model, hours, condition |
| `tasks` | Claude A | difficulty, quantity, priority, business value, dependencies |
| `task_history` | Claude A | completed tasks with actual duration - the ML training set |
| `telemetry` | Claude A | idle, fuel, load, seatbelt, proximity |
| `safety_events` | Claude A | see contract 3 |
| `incidents` | A + B | see contract 5 |
| `training_modules` | Claude B | training content |
| `training_progress` | Claude B | per-operator completion |

Column-level definitions are produced in Module 1 (Claude A) and recorded
alongside the synthetic data documentation. Claude B should treat Module 1's
approved output as the schema source.

If a schema change is required:

1. document the change
2. notify the other Claude through the coordinator
3. update this file and the affected contracts
4. test compatibility on both sides

---

## 7. Synthetic Data Marker

Every generated operational record carries an explicit synthetic marker. No
output of this system may be presented as real Caterpillar data. Claude B must
preserve that marker through persistence and surface the synthetic status in
the UI.

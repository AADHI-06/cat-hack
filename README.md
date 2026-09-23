# CAT Smart Operator Assistant

An AI-powered operator companion for CAT machinery. Hackathon prototype.

> **Status:** Module 0 (project foundation) only. See
> [docs/progress.md](docs/progress.md) for what is built and what is not.

---

## Problem Statement (Summary)

Heavy-machinery operators plan and run their shifts with limited support. Task
durations are estimated from experience, shift plans are assembled by hand, and
safety-relevant conditions are noticed only when someone happens to be
watching. The result is uneven productivity, idle machine time, plans that
drift from reality, and safety issues that are recorded after the fact rather
than surfaced as they happen.

Supervisors face the same gap at crew scale: they lack a single view of what
each operator is doing, how the shift is tracking against plan, and which
machines are behaving unusually.

---

## Proposed Solution

An assistant that sits alongside the operator and continuously answers three
questions:

1. **What should the operator do next?**
2. **How long will it take?**
3. **Is the current operation safe?**

It does this with a loop of **Predict -> Plan -> Assist -> Monitor -> Learn**:
predict task durations from historical patterns, build a shift plan that
maximizes useful operational value within shift capacity, assist the operator
through a focused dashboard, monitor telemetry for safety and anomalies, and
feed completed work back into the next prediction cycle.

The system is **decision support**. It does not control machinery and does not
replace certified safety systems or human supervision.

---

## Main Features

| Feature | Description |
|---------|-------------|
| Daily task planning | An ordered plan for the shift, respecting dependencies and capacity |
| Task time prediction | ML-predicted duration per task, with the main contributing factors |
| Shift optimization | Greedy/knapsack selection maximizing operational value, not task count |
| Safety monitoring | Deterministic alerts from observable conditions (seatbelt, proximity, idling, speed) |
| Anomaly detection | Unusual machine behaviour flagged from telemetry |
| Incident logging | Safety and anomaly events recorded, tracked and resolved |
| Operator training hub | Short training suggestions mapped to observed skill gaps |
| Operator dashboard | Next task, predicted time, live safety status, machine state |
| Supervisor dashboard | Crew and fleet overview, utilization, incident feed, plan quality |
| AI explanations | Plain-language explanation of what the system decided and why (optional) |

The AI explanation layer is optional by design: if no external LLM is
available, every other feature still works.

---

## Technology Stack

**Backend**

- Python 3.13, FastAPI, Uvicorn
- SQLite
- Pandas, NumPy
- scikit-learn (Random Forest, Isolation Forest), XGBoost where it helps
- pytest, httpx

**Frontend**

- React, Vite, Tailwind CSS, Recharts or equivalent

Architecture is a simple monolith with clear module boundaries. Full design:
[docs/architecture.md](docs/architecture.md).

---

## Development Model

This project is built by **two Claude accounts working in parallel**, split at
a contract boundary:

| | Claude A - Core AI / Intelligence | Claude B - Platform / Product |
|---|---|---|
| **Owns** | data generation, ML, prediction, optimization, safety logic, anomaly detection | database, API layer, frontend, dashboards, training hub, assistant UI |
| **Paths** | `data/`, `ml/`, `scripts/data_generation/`, `backend/app/ml/`, `backend/app/services/{optimization,safety,anomaly}/` | `backend/app/api/`, `backend/app/models/`, `backend/app/services/database/`, `frontend/` |
| **Branch** | `feature/core-ai` | `feature/platform-ui` |

Claude B builds against the interfaces in
[docs/contracts.md](docs/contracts.md), never against Claude A's internal ML
code. Neither modifies the other's implementation files outside a coordinated
integration task. `main` holds only reviewed and integrated work.

Full rules: [CLAUDE.md](CLAUDE.md). Boundaries and ownership:
[docs/architecture.md](docs/architecture.md).

---

## Planned Development Modules

Built strictly one module at a time, each gated on human review.

| # | Module | Owner |
|----|-----------------------------------|-------|
| 0 | Foundation | Claude A |
| 1 | Synthetic Data | Claude A |
| 2 | Task Prediction | Claude A |
| 3 | Optimization | Claude A |
| 4 | Safety | Claude A |
| 5 | Anomaly Detection | Claude A |
| 6 | Incident Management | A + B |
| 7 | Training Hub | Claude B |
| 8 | Operator Dashboard | Claude B |
| 9 | Supervisor Dashboard | Claude B |
| 10 | AI Assistant | A + B |
| 11 | Integration | A + B |
| 12 | Final QA / Demo | A + B |

Live status: [docs/progress.md](docs/progress.md).

---

## Repository Layout

```
cat-hack/
  backend/          FastAPI application and backend tests
    app/            application package
    tests/          backend tests
    requirements.txt
  data/
    raw/            source inputs
    processed/      feature tables for ML
    generated/      synthetic datasets (not committed)
  ml/
    training/       training scripts
    models/         trained artifacts (not committed)
    notebooks/      exploration
  docs/
    architecture.md   system design, boundaries, ownership
    contracts.md      interfaces between Claude A and Claude B
    progress.md       module status
  scripts/          developer utilities
  frontend/         React application (added in a later module)
```

Sub-packages under `backend/app/` (`ml/`, `api/`, `models/`, `services/*`) are
created by their owner in the module that first needs them.

---

## Getting Started

Requires Python 3.13.

```bash
# from the repository root
python -m venv .venv
source .venv/Scripts/activate      # Windows (Git Bash)
# .venv\Scripts\activate           # Windows (PowerShell)

pip install -r backend/requirements.txt
```

Run the backend:

```bash
uvicorn app.main:app --reload --app-dir backend
```

Then check `http://127.0.0.1:8000/health` and the interactive docs at
`http://127.0.0.1:8000/docs`.

Run the backend tests:

```bash
cd backend
python -m pytest -v
```

---

## Synthetic Data Disclaimer

**This project uses synthetic data only.**

The hackathon does not provide sufficient real operational data, so all
operators, machines, tasks, task histories and telemetry in this project are
**generated synthetically** from a fixed random seed. They are constructed to
contain sensible, documented relationships (harder tasks generally take
longer, beginners generally take longer, adverse weather can extend duration,
excessive idle time indicates abnormal machine behaviour) rather than
meaningless random values.

This data is **not real Caterpillar data** and is not presented as such. Every
generated record is explicitly labeled as synthetic.

Consequently, **any model metrics reported in this project describe performance
on synthetic data and do not represent real-world Caterpillar performance.**
Only metrics actually produced by a trained model are reported; none are
estimated or fabricated.

---

## Scope and Limitations

- Hackathon prototype, not a production industrial control system
- Decision support only: it does not actuate machinery or control safety or
  emergency systems
- Does not replace certified safety systems or human supervision
- The AI assistant explains decisions; deterministic backend algorithms remain
  the source of truth

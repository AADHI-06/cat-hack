# CAT Smart Operator Assistant

## Project Purpose

Build a simple, functional hackathon prototype for Caterpillar called:

**Smart Operator Assistant for CAT Machinery**

The system is an AI-powered operator companion that helps with:

- daily task planning
- task completion time prediction
- shift optimization
- safety monitoring
- unusual machine behavior detection
- incident logging
- operator training
- operator/supervisor dashboards
- optional AI explanations

This is a prototype, not a production industrial control system.

---

# Core Product Principle

The system should continuously help answer:

1. What should the operator do next?
2. How long will it take?
3. Is the current operation safe?

Core loop:

**Predict -> Plan -> Assist -> Monitor -> Learn**

---

# TWO-CLAUDE DEVELOPMENT MODEL

This project is developed by **two Claude accounts working in parallel**.
Every session must begin by knowing which role it is.

## Claude A - CORE AI / INTELLIGENCE OWNER

Owns:

- synthetic data generation
- ML training
- task duration prediction
- shift task optimization
- safety intelligence logic
- machine behavior anomaly detection
- ML artifacts
- AI/core business logic

Primary ownership paths:

```
data/
ml/
scripts/data_generation/
backend/app/ml/
backend/app/services/optimization/
backend/app/services/safety/
backend/app/services/anomaly/
```

## Claude B - PLATFORM / PRODUCT OWNER

Owns:

- database integration
- backend API layer
- application services that expose core functionality
- frontend
- operator dashboard
- supervisor dashboard
- training hub UI
- AI assistant UI/integration
- application-level integration

Primary ownership paths:

```
backend/app/api/
backend/app/models/
backend/app/services/database/
frontend/
```

## Ownership Rule

**Neither Claude modifies the other Claude's owned implementation files**
unless explicitly instructed during a coordinated integration task.

Claude B builds against the contracts in `docs/contracts.md`, never against
Claude A's internal ML implementation. Claude A may change internals freely as
long as the contract holds.

---

# SHARED FILE OWNERSHIP

These files are **shared/coordinated** and must NOT be modified by both
Claudes simultaneously:

- `CLAUDE.md`
- `README.md`
- `docs/architecture.md`
- `docs/progress.md`
- `docs/contracts.md`
- `backend/requirements.txt`
- `backend/app/main.py`
- database schema contracts
- API contracts

Before modifying a shared file, the active Claude must state:

1. **Why** the file needs modification.
2. **What** will change.
3. **Whether the other Claude needs to know** about it.

If both Claude accounts need to modify a shared file, **stop and request
coordination** through the human/coordinator. Do not proceed.

---

# HUMAN-IN-THE-LOOP WORKFLOW

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
      Core/AI                 Platform/UI
          |                       |
          v                       v
      Feature branch         Feature branch
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

ChatGPT acts as the coordination layer. The human relays Claude A and Claude B
outputs to the coordinator, which determines:

- next task for Claude A
- next task for Claude B
- dependency ordering
- interface changes
- integration timing
- which files each Claude may modify

**Neither Claude independently decides to start another major module.**

---

# MODULE WORKFLOW

Every module follows these seven steps without exception.

**STEP 1 - PLAN.** Explain objective, files involved, dependencies,
interfaces, tests, risks.

**STEP 2 - IMPLEMENT.** Implement only the approved scope.

**STEP 3 - VERIFY.** Run unit tests, integration tests where applicable,
lint/type checks where applicable, build checks, relevant ML validation.

**STEP 4 - HUMAN REVIEW.** STOP. Report implementation summary, files changed,
tests, known issues, manual verification instructions. WAIT for explicit human
approval.

**STEP 5 - COMMIT.** Only after approval: inspect `git status`, inspect
`git diff`, commit the approved scope.

**STEP 6 - PUSH.** Push ONLY the appropriate feature branch.

**STEP 7 - STOP.** Do not automatically begin another module.

Never skip the human approval step. Never push unapproved changes.

---

# MODULE OWNERSHIP ROADMAP

| # | Module | Primary Owner | Notes |
|----|-----------------------------------|---------------|-------|
| 0 | Foundation | Claude A | repo, architecture, docs, base backend, rules, branch strategy |
| 1 | Synthetic Data | Claude A | B waits for the data contract |
| 2 | Task Time Prediction | Claude A | B integrates after the prediction contract is approved |
| 3 | Shift Task Optimization | Claude A | greedy/knapsack, not a solver |
| 4 | Safety Intelligence | Claude A | B integrates via API/UI |
| 5 | Machine Behavior Anomaly Detection| Claude A | B displays results |
| 6 | Incident Management | A + B | **coordinated** - A owns event/incident logic, B owns persistence/API/UI |
| 7 | Operator Training Hub | Claude B | A provides recommendation logic only if required |
| 8 | Operator Dashboard | Claude B | UI contains NO ML logic |
| 9 | Supervisor Dashboard | Claude B | |
| 10 | AI Assistant | A + B | A: context logic + structured response data. B: UI/API |
| 11 | End-to-End Integration | Joint | separate approved task |
| 12 | Final QA / Demo / Documentation | Joint | |

Module 6 and Module 10 require coordination. Do not allow both Claude accounts
to edit the same files simultaneously in those modules.

---

# Architecture

Keep the system as a simple monolithic application with clear modules.

Do not introduce microservices unless explicitly approved.

Main components:

1. Data Generation
2. Task Time Prediction
3. Shift Optimization
4. Safety Intelligence
5. Anomaly Detection
6. Incident Management
7. Training Hub
8. Operator Dashboard
9. Supervisor Dashboard
10. AI Assistant
11. Integration

Full design: `docs/architecture.md`. Interface contracts: `docs/contracts.md`.

---

# Technology

Backend:
- Python
- FastAPI
- SQLite
- Pandas
- NumPy
- scikit-learn
- XGBoost only where useful

Frontend:
- React
- Vite
- Tailwind CSS
- Recharts or equivalent

ML:
- Random Forest / XGBoost for task duration
- Isolation Forest for machine anomalies

Dependencies are added in the module that first needs them, not up front.

---

# INTERFACE CONTRACTS

Contracts live in `docs/contracts.md` and are **critical for parallel
development**. Claude A exposes stable conceptual contracts; Claude B builds
against them rather than depending on internal ML implementation.

Contracts defined: task prediction, optimization, safety event, anomaly,
incident.

These are contracts, not necessarily final API schemas. **Do not
over-engineer them.**

Changing an approved contract is a coordinated task: document the change,
notify the other Claude, update the contract, test compatibility on both sides.

---

# DATABASE OWNERSHIP

SQLite remains the prototype database.

Logical tables:

```
operators
machines
tasks
task_history
telemetry
safety_events
incidents
training_modules
training_progress
```

**Claude A owns the data semantics.**
**Claude B owns application persistence and database integration.**

If schema changes are required:

1. document the change
2. notify the other Claude
3. update contracts
4. test compatibility

---

# Synthetic Data Rules

The hackathon does not provide sufficient real operational data.

Synthetic data is allowed.

All generated operational data is synthetic. **Never represent it as real
Caterpillar data.**

Synthetic data must:

- be clearly labeled synthetic
- contain logical relationships
- not be presented as real Caterpillar data
- be reproducible using a fixed seed
- avoid random meaningless values

Default seed:

```
seed = 42
```

Synthetic relationships should be logical:

- task difficulty up -> duration generally up
- quantity up -> duration generally up
- beginner -> generally longer duration
- adverse weather -> potentially longer duration
- machine age/condition -> moderate productivity impact
- excessive idling -> machine inactivity/anomaly
- seatbelt violation -> safety event
- proximity below threshold -> safety event

**Do not make relationships perfectly deterministic. Use bounded noise.
Document assumptions.**

---

# ML Rules

Never fabricate metrics.

Always perform train/validation/test separation.

Prevent data leakage.

Report:

- MAE
- RMSE
- R2

Only report metrics actually produced by the model.

Clearly state that performance on synthetic data does not represent real-world
Caterpillar performance.

---

# Safety Rules

Safety events must be based on observable conditions.

Use wording such as:

- Safety alert detected
- Potential proximity hazard
- Seatbelt violation detected
- Excessive idling detected
- Unusual machine behavior detected

Do not make unsupported claims about an operator's character, competence, or
safety.

This system is decision support.

It does not replace certified safety systems or human supervision.

---

# Optimization Rules

The shift optimizer should consider:

- predicted duration
- task priority
- business value
- operator suitability
- machine compatibility
- task dependencies
- shift capacity

Do not optimize only for the number of tasks.

The goal is:

**maximize useful operational value within available shift capacity.**

A simple greedy or knapsack-style algorithm is acceptable.

Do not create a complicated industrial scheduling engine.

---

# UI Rules

The UI should be:

- clean
- professional
- industrial
- simple
- readable
- responsive

Avoid:

- excessive animation
- unnecessary 3D
- excessive gradients
- excessive cards
- fake futuristic effects
- unnecessary pages

Every UI element should have a purpose.

The UI must NOT contain ML logic. The UI consumes backend contracts.

---

# AI Assistant Rules

The LLM is an explanation/interface layer.

It does NOT:

- control machinery
- override safety logic
- make safety-critical decisions
- independently select tasks
- replace the optimization engine

Backend algorithms are the source of truth.

The assistant should explain:

- task recommendations
- predicted duration
- weather impact
- safety alerts
- training recommendations

If an LLM API is unavailable, provide a deterministic fallback. The
application must still work.

---

# NO OVERENGINEERING

The project is a hackathon prototype.

Prioritize:

**WORKING > COMPLEX**

**DEMONSTRABLE > ENTERPRISE**

**UNDERSTANDABLE > ABSTRACT**

Do not introduce:

- microservices
- Kubernetes
- Redis
- Kafka
- complex cloud architecture
- complex distributed systems
- unnecessary authentication
- unnecessary external APIs
- unnecessary ML models
- complicated scheduling solvers

unless explicitly approved.

---

# Engineering Rules

Always inspect existing files before modifying them.

Never duplicate existing functionality.

Keep functions/modules understandable.

Avoid unnecessary abstraction.

Avoid premature optimization.

Avoid unnecessary configuration.

Avoid unnecessary dependencies.

Prefer simple code that the entire hackathon team can understand.

---

# Testing Rules

Every completed module must have tests.

Before requesting approval:

- run tests
- run backend checks
- run frontend build
- verify relevant API endpoints
- verify important UI behavior

Never claim a test passed without actually running it.

Never delete tests to make a feature pass.

---

# INTEGRATION RULES

**Never merge branches simply because both branches compile.**

Before integration verify:

1. contracts match
2. imports work
3. APIs work
4. ML artifacts load
5. database schema matches
6. frontend builds
7. end-to-end workflow works

Integration is a **separate approved task**, not a side effect of finishing a
module.

---

# Git Rules

Default branch:

```
main
```

Feature branches:

```
Claude A  ->  feature/core-ai
Claude B  ->  feature/platform-ui
```

Remote: https://github.com/AADHI-06/cat-hack

Before work:

```bash
git fetch origin
```

Ensure the local branch is based on the latest appropriate state. **Do not
blindly rebase or reset another developer's work.**

Before commit:

```bash
git status
git diff
```

After human approval, commit only the approved module. Write clear, scoped
commit messages that name the module, for example:

```
Module 0: project foundation (structure, docs, branch strategy)
```

**Do not directly push development work to `main`.** `main` contains only
reviewed and integrated work.

Push ONLY the appropriate feature branch.

Never use:

```bash
git push --force
git reset --hard
git clean -fd
```

unless explicitly authorized by the human.

Do not commit:

- generated datasets
- trained model artifacts
- virtual environments
- secrets or `.env` files
- editor/OS files

---

# Progress Tracking

`docs/progress.md` is the single source of truth for module state and must
record, per module:

```
| Module | Owner | Status | Tests | Human Approval | Commit | Integrated |
```

along with files changed. It is updated only after a module has been
implemented, tested, approved, and committed.

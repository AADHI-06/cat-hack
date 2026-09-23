"""
Response models for dashboards and system status.

These only aggregate stored data (lists and counts). Fields for predictions,
shift plans, live safety status and anomalies are added when Claude A's
contracts for them are approved; until then `services` reports them as
unavailable so the UI can show an honest empty state.
"""

from pydantic import BaseModel

from app.models.operational import DataSource, Machine, Operator, SafetyEvent, TaskHistory


class ServiceStatus(BaseModel):
    """Availability of one intelligence capability owned by Claude A (or a later module)."""

    key: str
    name: str
    module: int
    available: bool
    message: str


class SafetySummary(BaseModel):
    """Counts of recorded safety events. Severity comes from the stored events, not the UI."""

    total: int
    by_severity: dict[str, int]
    by_event_type: dict[str, int]


class TaskSummary(BaseModel):
    total: int
    by_status: dict[str, int]
    by_priority: dict[str, int]


class SystemStatus(BaseModel):
    database_loaded: bool
    table_counts: dict[str, int]
    services: list[ServiceStatus]
    data_source: DataSource = "synthetic"
    disclaimer: str


class OperatorDashboard(BaseModel):
    operator: Operator
    safety_summary: SafetySummary
    recent_safety_events: list[SafetyEvent]
    recent_executions: list[TaskHistory]
    services: list[ServiceStatus]
    data_source: DataSource = "synthetic"


class SupervisorDashboard(BaseModel):
    operators: list[Operator]
    machines: list[Machine]
    task_summary: TaskSummary
    safety_summary: SafetySummary
    recent_safety_events: list[SafetyEvent]
    services: list[ServiceStatus]
    data_source: DataSource = "synthetic"

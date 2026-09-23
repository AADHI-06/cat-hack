import sqlite3

from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies import get_db
from app.api.intelligence import service_statuses
from app.api.routes.safety import safety_summary
from app.models.dashboard import OperatorDashboard, SupervisorDashboard, TaskSummary
from app.services.database import repository

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

RECENT_LIMIT = 10


@router.get("/operator/{operator_id}", response_model=OperatorDashboard)
def operator_dashboard(operator_id: str, conn: sqlite3.Connection = Depends(get_db)):
    """
    Everything currently known about one operator.

    No machine assignment or shift plan yet: those come from the optimizer
    (Module 3), reported via `services`.
    """
    operator = repository.get_operator(conn, operator_id)
    if operator is None:
        raise HTTPException(status_code=404, detail=f"Operator {operator_id} not found")
    return OperatorDashboard(
        operator=operator,
        safety_summary=safety_summary(conn, operator_id=operator_id),
        recent_safety_events=repository.list_safety_events(conn, operator_id=operator_id, limit=RECENT_LIMIT),
        recent_executions=repository.list_task_history(conn, operator_id=operator_id, limit=RECENT_LIMIT),
        services=service_statuses(),
    )


@router.get("/supervisor", response_model=SupervisorDashboard)
def supervisor_dashboard(conn: sqlite3.Connection = Depends(get_db)):
    """Crew and fleet overview across all operators and machines."""
    by_status = repository.count_by(conn, "tasks", "status")
    return SupervisorDashboard(
        operators=repository.list_operators(conn),
        machines=repository.list_machines(conn),
        task_summary=TaskSummary(
            total=sum(by_status.values()),
            by_status=by_status,
            by_priority=repository.count_by(conn, "tasks", "priority"),
        ),
        safety_summary=safety_summary(conn),
        recent_safety_events=repository.list_safety_events(conn, limit=RECENT_LIMIT),
        services=service_statuses(),
    )

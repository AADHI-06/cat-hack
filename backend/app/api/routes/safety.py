import sqlite3

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import get_db
from app.models.dashboard import SafetySummary
from app.models.operational import SafetyEvent, SafetyEventType, Severity
from app.services.database import repository

router = APIRouter(prefix="/safety", tags=["safety"])


def safety_summary(conn: sqlite3.Connection, operator_id=None, machine_id=None) -> SafetySummary:
    filters = {"operator_id": operator_id, "machine_id": machine_id}
    by_severity = repository.count_by(conn, "safety_events", "severity", filters)
    return SafetySummary(
        total=sum(by_severity.values()),
        by_severity=by_severity,
        by_event_type=repository.count_by(conn, "safety_events", "event_type", filters),
    )


@router.get("/events", response_model=list[SafetyEvent])
def list_safety_events(
    operator_id: str | None = None,
    machine_id: str | None = None,
    severity: Severity | None = None,
    event_type: SafetyEventType | None = None,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    conn: sqlite3.Connection = Depends(get_db),
):
    """Recorded safety events, newest first. Severity is as stored - never recomputed here."""
    return repository.list_safety_events(conn, operator_id, machine_id, severity, event_type, limit, offset)


@router.get("/summary", response_model=SafetySummary)
def get_safety_summary(
    operator_id: str | None = None,
    machine_id: str | None = None,
    conn: sqlite3.Connection = Depends(get_db),
):
    return safety_summary(conn, operator_id, machine_id)

import sqlite3
from datetime import date

from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies import get_db
from app.models.operational import MachineType, Priority, Task, TaskStatus, Zone
from app.services.database import repository

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("", response_model=list[Task])
def list_tasks(
    status: TaskStatus | None = None,
    priority: Priority | None = None,
    site_zone: Zone | None = None,
    required_machine_type: MachineType | None = None,
    shift_date: date | None = None,
    conn: sqlite3.Connection = Depends(get_db),
):
    """The pending task backlog, ordered by shift date."""
    return repository.list_tasks(
        conn, status, priority, site_zone, required_machine_type,
        shift_date.isoformat() if shift_date else None,
    )


@router.get("/{task_id}", response_model=Task)
def get_task(task_id: str, conn: sqlite3.Connection = Depends(get_db)):
    task = repository.get_task(conn, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    return task

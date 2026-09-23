import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.dependencies import get_db
from app.models.operational import Machine, MachineType, Telemetry, Zone
from app.services.database import repository

router = APIRouter(prefix="/machines", tags=["machines"])


@router.get("", response_model=list[Machine])
def list_machines(
    machine_type: MachineType | None = None,
    home_zone: Zone | None = None,
    conn: sqlite3.Connection = Depends(get_db),
):
    return repository.list_machines(conn, machine_type, home_zone)


@router.get("/{machine_id}", response_model=Machine)
def get_machine(machine_id: str, conn: sqlite3.Connection = Depends(get_db)):
    machine = repository.get_machine(conn, machine_id)
    if machine is None:
        raise HTTPException(status_code=404, detail=f"Machine {machine_id} not found")
    return machine


@router.get("/{machine_id}/telemetry", response_model=list[Telemetry])
def machine_telemetry(
    machine_id: str,
    limit: int = Query(20, ge=1, le=500),
    offset: int = Query(0, ge=0),
    conn: sqlite3.Connection = Depends(get_db),
):
    """Most recent telemetry readings for one machine, newest first."""
    if repository.get_machine(conn, machine_id) is None:
        raise HTTPException(status_code=404, detail=f"Machine {machine_id} not found")
    return repository.list_telemetry(conn, machine_id=machine_id, limit=limit, offset=offset)

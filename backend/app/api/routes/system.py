import sqlite3

from fastapi import APIRouter, Depends

from app.api.dependencies import get_db
from app.api.intelligence import service_statuses
from app.models.dashboard import SystemStatus
from app.services.database import repository
from app.services.database.schema import TABLE_ORDER

router = APIRouter(prefix="/system", tags=["system"])

DISCLAIMER = (
    "All operational data is synthetic, generated for a hackathon prototype. "
    "It is not real Caterpillar data."
)


@router.get("/status", response_model=SystemStatus)
def system_status(conn: sqlite3.Connection = Depends(get_db)):
    """Whether the database has been loaded, and which intelligence services are available."""
    counts = repository.table_counts(conn, TABLE_ORDER)
    return SystemStatus(
        database_loaded=all(counts.values()),
        table_counts=counts,
        services=service_statuses(),
        disclaimer=DISCLAIMER,
    )

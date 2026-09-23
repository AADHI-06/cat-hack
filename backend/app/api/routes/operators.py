import sqlite3

from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies import get_db
from app.models.operational import Operator, Shift, SkillLevel
from app.services.database import repository

router = APIRouter(prefix="/operators", tags=["operators"])


@router.get("", response_model=list[Operator])
def list_operators(
    skill_level: SkillLevel | None = None,
    primary_shift: Shift | None = None,
    conn: sqlite3.Connection = Depends(get_db),
):
    return repository.list_operators(conn, skill_level, primary_shift)


@router.get("/{operator_id}", response_model=Operator)
def get_operator(operator_id: str, conn: sqlite3.Connection = Depends(get_db)):
    operator = repository.get_operator(conn, operator_id)
    if operator is None:
        raise HTTPException(status_code=404, detail=f"Operator {operator_id} not found")
    return operator

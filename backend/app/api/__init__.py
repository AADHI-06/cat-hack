"""
HTTP API (Claude B). All routes live under /api.

Registered on the app in backend/app/main.py.
"""

from fastapi import APIRouter

from app.api.routes import dashboard, machines, operators, safety, system, tasks

api_router = APIRouter(prefix="/api")
api_router.include_router(system.router)
api_router.include_router(operators.router)
api_router.include_router(machines.router)
api_router.include_router(tasks.router)
api_router.include_router(safety.router)
api_router.include_router(dashboard.router)

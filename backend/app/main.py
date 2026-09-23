"""
CAT Smart Operator Assistant - FastAPI application entrypoint.

Module 0 scope: foundation only. This file intentionally contains no feature
endpoints. Feature routers are added in later modules.

Run locally:
    uvicorn app.main:app --reload --app-dir backend
"""

from fastapi import FastAPI

from app import __version__
from app.api import api_router

app = FastAPI(
    title="CAT Smart Operator Assistant",
    description=(
        "AI-powered operator companion for CAT machinery. "
        "Prototype built on clearly labeled synthetic data."
    ),
    version=__version__,
)


@app.get("/")
def root():
    """Basic service identity. Used to confirm the app is serving."""
    return {
        "service": "CAT Smart Operator Assistant",
        "version": __version__,
        "status": "ok",
        "data_source": "synthetic",
    }


@app.get("/health")
def health():
    """Liveness probe for local development and tests."""
    return {"status": "healthy"}


# Platform API routes (Claude B): /api/...
app.include_router(api_router)

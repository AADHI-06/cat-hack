"""
Module 0 foundation tests.

These prove only that the backend foundation is importable and serves.
No feature behaviour is asserted here.
"""

from fastapi.testclient import TestClient

from app import __version__
from app.main import app

client = TestClient(app)


def test_app_imports():
    """The FastAPI application object is constructed on import."""
    assert app is not None
    assert app.title == "CAT Smart Operator Assistant"
    assert app.version == __version__


def test_app_starts_and_serves_root():
    """The app starts under the test client and the root route responds."""
    response = client.get("/")
    assert response.status_code == 200

    body = response.json()
    assert body["service"] == "CAT Smart Operator Assistant"
    assert body["status"] == "ok"
    assert body["data_source"] == "synthetic"


def test_health_endpoint():
    """Liveness probe responds."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}

"""Tests for the health check endpoint"""

from fastapi.testclient import TestClient

from src.app import app
from src.core.project import PROJECT_NAME, PROJECT_VERSION

client = TestClient(app)


def test_health_check() -> None:
    """Test the health check endpoint"""
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "OK",
        "name": PROJECT_NAME,
        "version": PROJECT_VERSION,
    }

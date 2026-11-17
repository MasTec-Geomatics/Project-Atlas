"""Tests for the reference load endpoint, ``POST /api/v1/reference/loads/{layer}``."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from src.app import app
from src.reference.api import get_reference_engine
from src.reference.load import LoadError
from src.reference.loaders import LOADERS

client = TestClient(app)


@pytest.fixture
def test_engine(reference_engine: Engine) -> Iterator[Engine]:
    """Point the endpoint at the reference test database instead of the real one."""
    app.dependency_overrides[get_reference_engine] = lambda: reference_engine
    yield reference_engine
    app.dependency_overrides.clear()


def test_start_load_runs_the_layer_loader(
    test_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The endpoint answers 202 and runs that layer's loader with the reference engine."""
    calls: list[Engine] = []
    monkeypatch.setitem(LOADERS, "wetlands", calls.append)

    response = client.post("/api/v1/reference/loads/wetlands")

    assert response.status_code == 202
    assert response.json() == {"layer": "wetlands"}
    assert calls == [test_engine]


@pytest.mark.usefixtures("test_engine")
def test_start_load_rejects_unknown_layer() -> None:
    """A layer with no loader answers 404 and starts nothing."""
    response = client.post("/api/v1/reference/loads/not_a_layer")

    assert response.status_code == 404
    assert response.json() == {"detail": "No loader for layer 'not_a_layer'"}


@pytest.mark.usefixtures("test_engine")
def test_failed_load_does_not_break_the_response(monkeypatch: pytest.MonkeyPatch) -> None:
    """A loader that fails in the background still leaves the 202 response intact."""

    def failing_loader(_engine: Engine) -> None:
        raise LoadError("source is down")

    monkeypatch.setitem(LOADERS, "wetlands", failing_loader)

    response = client.post("/api/v1/reference/loads/wetlands")

    assert response.status_code == 202

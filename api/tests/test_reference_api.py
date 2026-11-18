"""Tests for the reference load endpoints.

- ``POST /api/v1/reference/loads/{layer}`` loads every enabled state.
- ``POST /api/v1/reference/loads/{layer}/{state}`` loads one state.
"""

from collections.abc import Sequence

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, insert

from src.app import app
from src.reference import api
from src.reference.load import LayerSource, LoadError
from src.reference.models.public import Source

client = TestClient(app)


def add_source(engine: Engine, state: str, *, is_enabled: bool = True) -> None:
    """Insert one ``hydro.wetlands`` row into ``public.sources``."""
    with engine.begin() as connection:
        connection.execute(
            insert(Source).values(
                layer="hydro.wetlands",
                state=state,
                download_url=f"https://example.com/{state}_geopackage_wetlands.zip",
                format="gpkg",
                is_enabled=is_enabled,
            )
        )


@pytest.fixture
def started(monkeypatch: pytest.MonkeyPatch) -> list[tuple[Engine, list[LayerSource]]]:
    """Record the loads the endpoints start, instead of running them.

    Returns:
        One ``(engine, sources)`` entry per started load.
    """
    calls: list[tuple[Engine, list[LayerSource]]] = []

    def record(engine: Engine, sources: Sequence[LayerSource]) -> None:
        calls.append((engine, list(sources)))

    monkeypatch.setitem(vars(api), "run_loads", record)
    return calls


def test_load_all_enabled_states(
    api_engine: Engine, started: list[tuple[Engine, list[LayerSource]]]
) -> None:
    """Loading a layer loads every enabled state, in state order, and skips disabled ones."""
    add_source(api_engine, "TX")
    add_source(api_engine, "LA")
    add_source(api_engine, "OK", is_enabled=False)

    response = client.post("/api/v1/reference/loads/wetlands")

    assert response.status_code == 202
    assert response.json() == {"layer": "wetlands", "states": ["LA", "TX"]}
    [(engine, sources)] = started
    assert engine is api_engine
    assert [(s.state, s.url, s.source_layer, s.file_suffix) for s in sources] == [
        ("LA", "https://example.com/LA_geopackage_wetlands.zip", "LA_Wetlands", ".gpkg"),
        ("TX", "https://example.com/TX_geopackage_wetlands.zip", "TX_Wetlands", ".gpkg"),
    ]


def test_load_one_state(
    api_engine: Engine, started: list[tuple[Engine, list[LayerSource]]]
) -> None:
    """Loading a layer for one state loads only that state."""
    add_source(api_engine, "TX")
    add_source(api_engine, "LA")

    response = client.post("/api/v1/reference/loads/wetlands/LA")

    assert response.status_code == 202
    assert response.json() == {"layer": "wetlands", "states": ["LA"]}
    [(_, sources)] = started
    assert [s.state for s in sources] == ["LA"]


@pytest.mark.usefixtures("api_engine")
@pytest.mark.parametrize(
    "path", ["/api/v1/reference/loads/not_a_layer", "/api/v1/reference/loads/not_a_layer/TX"]
)
def test_unknown_layer(path: str, started: list[tuple[Engine, list[LayerSource]]]) -> None:
    """A layer with no loader answers 404 and starts nothing."""
    response = client.post(path)

    assert response.status_code == 404
    assert response.json() == {"detail": "No loader for layer 'not_a_layer'"}
    assert started == []


def test_no_enabled_sources(
    api_engine: Engine, started: list[tuple[Engine, list[LayerSource]]]
) -> None:
    """A layer with no enabled sources answers 404 and starts nothing."""
    add_source(api_engine, "TX", is_enabled=False)

    response = client.post("/api/v1/reference/loads/wetlands")

    assert response.status_code == 404
    assert response.json() == {"detail": "No enabled sources for hydro.wetlands"}
    assert started == []


def test_state_without_enabled_source(
    api_engine: Engine, started: list[tuple[Engine, list[LayerSource]]]
) -> None:
    """A state with no enabled source answers 404 and starts nothing."""
    add_source(api_engine, "TX")

    response = client.post("/api/v1/reference/loads/wetlands/LA")

    assert response.status_code == 404
    assert response.json() == {"detail": "No enabled source for hydro.wetlands in LA"}
    assert started == []


@pytest.mark.usefixtures("api_engine")
def test_bad_state_code(started: list[tuple[Engine, list[LayerSource]]]) -> None:
    """The state in the path must be a two-letter uppercase code."""
    response = client.post("/api/v1/reference/loads/wetlands/tx")

    assert response.status_code == 422
    assert started == []


def test_failed_load_does_not_break_the_response(
    api_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A load that fails in the background still leaves the 202 response intact."""
    add_source(api_engine, "TX")

    def failing_loads(_engine: Engine, _sources: Sequence[LayerSource]) -> None:
        raise LoadError("source is down")

    monkeypatch.setitem(vars(api), "run_loads", failing_loads)

    response = client.post("/api/v1/reference/loads/wetlands")

    assert response.status_code == 202

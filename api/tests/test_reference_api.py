"""Tests for the reference load endpoint, ``POST /api/v1/reference/loads``.

The request is a list of layer and state pairs, one per checked box on the admin page.
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


def add_source(engine: Engine, layer: str, state: str, *, is_enabled: bool = True) -> None:
    """Insert one ``public.sources`` row."""
    with engine.begin() as connection:
        connection.execute(
            insert(Source).values(
                layer=layer,
                state=state,
                download_url=f"https://example.com/{layer}/{state}.zip",
                format="gpkg",
                is_enabled=is_enabled,
            )
        )


@pytest.fixture
def started(monkeypatch: pytest.MonkeyPatch) -> list[tuple[Engine, list[LayerSource]]]:
    """Record the loads the endpoint starts, instead of running them.

    Returns:
        One ``(engine, sources)`` entry per started request.
    """
    calls: list[tuple[Engine, list[LayerSource]]] = []

    def record(engine: Engine, sources: Sequence[LayerSource]) -> None:
        calls.append((engine, list(sources)))

    monkeypatch.setitem(vars(api), "run_loads", record)
    return calls


def test_load_pairs(api_engine: Engine, started: list[tuple[Engine, list[LayerSource]]]) -> None:
    """Each layer and state pair is loaded, in one background run."""
    add_source(api_engine, "hydro.wetlands", "TX")
    add_source(api_engine, "boundaries.counties", "TX")
    add_source(api_engine, "boundaries.counties", "LA")

    response = client.post(
        "/api/v1/reference/loads",
        json=[
            {"layer": "wetlands", "state": "TX"},
            {"layer": "counties", "state": "TX"},
            {"layer": "counties", "state": "LA"},
        ],
    )

    assert response.status_code == 202
    assert response.json() == {
        "loads": [
            {"layer": "wetlands", "state": "TX"},
            {"layer": "counties", "state": "TX"},
            {"layer": "counties", "state": "LA"},
        ]
    }
    [(engine, sources)] = started
    assert engine is api_engine
    assert [(s.model.__tablename__, s.state) for s in sources] == [
        ("wetlands", "TX"),
        ("counties", "TX"),
        ("counties", "LA"),
    ]


def test_duplicate_pairs_load_once(
    api_engine: Engine, started: list[tuple[Engine, list[LayerSource]]]
) -> None:
    """The same layer and state sent twice is loaded once."""
    add_source(api_engine, "hydro.wetlands", "TX")

    response = client.post(
        "/api/v1/reference/loads",
        json=[{"layer": "wetlands", "state": "TX"}, {"layer": "wetlands", "state": "TX"}],
    )

    assert response.status_code == 202
    assert response.json() == {"loads": [{"layer": "wetlands", "state": "TX"}]}
    [(_, sources)] = started
    assert len(sources) == 1


def test_problems_start_nothing(
    api_engine: Engine, started: list[tuple[Engine, list[LayerSource]]]
) -> None:
    """An unknown layer or a state with no enabled source answers 422 and starts nothing."""
    add_source(api_engine, "hydro.wetlands", "TX")
    add_source(api_engine, "hydro.wetlands", "LA", is_enabled=False)

    response = client.post(
        "/api/v1/reference/loads",
        json=[
            {"layer": "wetlands", "state": "TX"},
            {"layer": "not_a_layer", "state": "TX"},
            {"layer": "wetlands", "state": "LA"},
        ],
    )

    assert response.status_code == 422
    assert response.json() == {
        "detail": [
            "No loader for layer 'not_a_layer'",
            "No enabled source for hydro.wetlands in LA",
        ]
    }
    assert started == []


@pytest.mark.usefixtures("api_engine")
def test_empty_request(started: list[tuple[Engine, list[LayerSource]]]) -> None:
    """A request with no pairs answers 422 and starts nothing."""
    response = client.post("/api/v1/reference/loads", json=[])

    assert response.status_code == 422
    assert started == []


@pytest.mark.usefixtures("api_engine")
def test_bad_state_code(started: list[tuple[Engine, list[LayerSource]]]) -> None:
    """The state must be a two-letter uppercase code."""
    response = client.post("/api/v1/reference/loads", json=[{"layer": "wetlands", "state": "tx"}])

    assert response.status_code == 422
    assert started == []


def test_failed_load_does_not_break_the_response(
    api_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A load that fails in the background still leaves the 202 response intact."""
    add_source(api_engine, "hydro.wetlands", "TX")

    def failing_loads(_engine: Engine, _sources: Sequence[LayerSource]) -> None:
        raise LoadError("source is down")

    monkeypatch.setitem(vars(api), "run_loads", failing_loads)

    response = client.post("/api/v1/reference/loads", json=[{"layer": "wetlands", "state": "TX"}])

    assert response.status_code == 202

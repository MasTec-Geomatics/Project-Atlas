"""Tests for the load endpoint, ``POST /api/v1/reference/loads``.

The request is a list of layer and state pairs, one per checked box on the admin page.
"""

from collections.abc import Sequence

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, insert

from src.app import app
from src.reference import api
from src.reference.load import Load, LoadError
from src.reference.models.public import Source

client = TestClient(app)

URL = "/api/v1/reference/loads"


def add_source(engine: Engine, layer: str, state: str | None = None) -> None:
    """Insert one ``public.sources`` row."""
    with engine.begin() as connection:
        connection.execute(
            insert(Source).values(
                layer=layer,
                state=state,
                download_url=f"https://example.com/{layer}/{state or '{state}'}.zip",
                access_type="file",
                format="GPKG",
                field_mapping={"name": "NAME"},
            )
        )


@pytest.fixture
def started(monkeypatch: pytest.MonkeyPatch) -> list[list[Load]]:
    """Record the loads the endpoint starts, instead of running them.

    Returns:
        The loads of each started request.
    """
    calls: list[list[Load]] = []

    def record(_engine: Engine, loads: Sequence[Load]) -> None:
        calls.append(list(loads))

    monkeypatch.setitem(vars(api), "run_loads", record)
    return calls


def test_load_pairs(api_engine: Engine, started: list[list[Load]]) -> None:
    """Each layer and state pair is loaded, in one background run."""
    add_source(api_engine, "boundaries.counties")

    response = client.post(
        URL,
        json=[
            {"layer": "boundaries.counties", "state": "TX"},
            {"layer": "boundaries.counties", "state": "LA"},
        ],
    )

    assert response.status_code == 202
    assert response.json() == {
        "loads": [
            {"layer": "boundaries.counties", "state": "TX"},
            {"layer": "boundaries.counties", "state": "LA"},
        ]
    }
    [loads] = started
    assert [(load.layer, load.state, load.url) for load in loads] == [
        ("boundaries.counties", "TX", "https://example.com/boundaries.counties/TX.zip"),
        ("boundaries.counties", "LA", "https://example.com/boundaries.counties/LA.zip"),
    ]


def test_state_source_is_used(api_engine: Engine, started: list[list[Load]]) -> None:
    """A state source is used for its state; other states use the federal source."""
    add_source(api_engine, "hydro.wetlands")
    add_source(api_engine, "hydro.wetlands", "TX")

    client.post(
        URL,
        json=[
            {"layer": "hydro.wetlands", "state": "TX"},
            {"layer": "hydro.wetlands", "state": "LA"},
        ],
    )

    [loads] = started
    assert [load.url for load in loads] == [
        "https://example.com/hydro.wetlands/TX.zip",
        "https://example.com/hydro.wetlands/LA.zip",
    ]


def test_duplicate_pairs_load_once(api_engine: Engine, started: list[list[Load]]) -> None:
    """The same layer and state sent twice is loaded once."""
    add_source(api_engine, "hydro.wetlands")

    response = client.post(
        URL,
        json=[
            {"layer": "hydro.wetlands", "state": "TX"},
            {"layer": "hydro.wetlands", "state": "TX"},
        ],
    )

    assert response.json() == {"loads": [{"layer": "hydro.wetlands", "state": "TX"}]}
    [loads] = started
    assert len(loads) == 1


def test_problems_start_nothing(api_engine: Engine, started: list[list[Load]]) -> None:
    """An unknown layer or a missing source answers 422, listing each, and starts nothing."""
    add_source(api_engine, "hydro.wetlands")

    response = client.post(
        URL,
        json=[
            {"layer": "hydro.wetlands", "state": "TX"},
            {"layer": "not.a_layer", "state": "TX"},
            {"layer": "boundaries.places", "state": "LA"},
        ],
    )

    assert response.status_code == 422
    assert response.json() == {
        "detail": [
            "No layer named 'not.a_layer'",
            "No enabled source for boundaries.places in LA",
        ]
    }
    assert started == []


@pytest.mark.usefixtures("api_engine")
def test_empty_request(started: list[list[Load]]) -> None:
    """A request with no pairs answers 422 and starts nothing."""
    response = client.post(URL, json=[])

    assert response.status_code == 422
    assert started == []


@pytest.mark.usefixtures("api_engine")
def test_bad_state_code(started: list[list[Load]]) -> None:
    """The state must be a two-letter uppercase code."""
    response = client.post(URL, json=[{"layer": "hydro.wetlands", "state": "tx"}])

    assert response.status_code == 422
    assert started == []


def test_failed_load_does_not_break_the_response(
    api_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A load that fails in the background still leaves the 202 response intact."""
    add_source(api_engine, "hydro.wetlands")

    def failing_loads(_engine: Engine, _loads: Sequence[Load]) -> None:
        raise LoadError("source is down")

    monkeypatch.setitem(vars(api), "run_loads", failing_loads)

    response = client.post(URL, json=[{"layer": "hydro.wetlands", "state": "TX"}])

    assert response.status_code == 202

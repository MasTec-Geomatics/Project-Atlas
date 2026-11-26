"""Tests for the admin page's load endpoints.

- ``GET /api/v1/reference/states``: the states for the **Add a state** box.
- ``GET /api/v1/reference/layers``: the layers, one column each.
- ``POST /api/v1/reference/loads``: the **Load** button. The request is a list of layer
  and state pairs, one per checked box.
- ``GET /api/v1/reference/loads``: the last load of each layer and state, for the
  progress bar and the result in each box.
"""

from collections.abc import Sequence
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, insert

from src.app import app
from src.reference import api
from src.reference.load import Load, LoadError
from src.reference.models.public import LoadRun, Source

client = TestClient(app)

URL = "/api/v1/reference/loads"
STATES_URL = "/api/v1/reference/states"
LAYERS_URL = "/api/v1/reference/layers"


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


def add_run(engine: Engine, layer: str, state: str, status: str, started: datetime) -> None:
    """Insert one ``public.load_runs`` row."""
    finished = None if status == "running" else started
    with engine.begin() as connection:
        connection.execute(
            insert(LoadRun).values(
                layer=layer,
                state=state,
                status=status,
                rows_loaded=10 if status == "succeeded" else None,
                error="source is down" if status == "failed" else None,
                started_at=started,
                finished_at=finished,
            )
        )


def test_states_have_code_and_name() -> None:
    """Every state comes back with its code and full name, so either can be searched."""
    response = client.get(STATES_URL)

    assert response.status_code == 200
    states = response.json()
    assert len(states) == 51
    assert {"code": "NC", "name": "North Carolina"} in states
    assert {"code": "DC", "name": "District of Columbia"} in states


def test_states_are_in_name_order() -> None:
    """States come back alphabetized by full name."""
    names = [state["name"] for state in client.get(STATES_URL).json()]

    assert names == sorted(names)


def test_layers() -> None:
    """Every layer table comes back by name; tables that aren't layers don't."""
    response = client.get(LAYERS_URL)

    assert response.status_code == 200
    names = [layer["name"] for layer in response.json()]
    assert "boundaries.states" in names
    assert "hydro.wetlands" in names
    assert "public.sources" not in names
    assert "public.load_runs" not in names
    assert names == sorted(names)


def test_layers_have_readable_names() -> None:
    """Each layer comes with a readable name and the readable name of its group."""
    layers = client.get(LAYERS_URL).json()

    assert {"name": "hydro.wetlands", "title": "Wetlands", "group": "Water"} in layers


def test_every_layer_has_a_title_and_group() -> None:
    """No layer is missing its readable name or group."""
    layers = client.get(LAYERS_URL).json()

    assert [layer["name"] for layer in layers if not layer["title"] or not layer["group"]] == []


def test_last_load_of_each_layer_and_state(api_engine: Engine) -> None:
    """Only the newest load of each layer and state comes back."""
    add_run(api_engine, "hydro.wetlands", "TX", "failed", datetime(2026, 11, 1, tzinfo=UTC))
    add_run(api_engine, "hydro.wetlands", "TX", "succeeded", datetime(2026, 11, 2, tzinfo=UTC))
    add_run(api_engine, "boundaries.counties", "LA", "running", datetime(2026, 11, 3, tzinfo=UTC))

    response = client.get(URL)

    assert response.status_code == 200
    loads = {(item["layer"], item["state"]): item for item in response.json()}
    assert set(loads) == {("hydro.wetlands", "TX"), ("boundaries.counties", "LA")}
    assert loads["hydro.wetlands", "TX"]["status"] == "succeeded"
    assert loads["hydro.wetlands", "TX"]["rows_loaded"] == 10
    assert loads["boundaries.counties", "LA"]["status"] == "running"
    assert loads["boundaries.counties", "LA"]["finished_at"] is None


def test_failed_load_has_its_error(api_engine: Engine) -> None:
    """A failed load comes back with its error, so the page can show why."""
    add_run(api_engine, "hydro.wetlands", "TX", "failed", datetime(2026, 11, 1, tzinfo=UTC))

    [load] = client.get(URL).json()

    assert load["status"] == "failed"
    assert load["error"] == "source is down"


def test_no_loads_yet(api_engine: Engine) -> None:
    """With nothing loaded, the list is empty."""
    assert client.get(URL).json() == []


def test_running_load_shows_its_stage(api_engine: Engine) -> None:
    """A running load comes back with its stage and how much has downloaded."""
    with api_engine.begin() as connection:
        connection.execute(
            insert(LoadRun).values(
                layer="hydro.wetlands",
                state="TX",
                status="running",
                stage="downloading",
                bytes_downloaded=340,
                bytes_total=1200,
            )
        )

    [load] = client.get(URL).json()

    assert (load["stage"], load["bytes_downloaded"], load["bytes_total"]) == (
        "downloading",
        340,
        1200,
    )


def test_startup_fails_interrupted_loads(api_engine: Engine) -> None:
    """When the API starts, loads it left running are recorded as failed."""
    add_run(api_engine, "hydro.wetlands", "TX", "running", datetime(2026, 11, 1, tzinfo=UTC))

    with TestClient(app):
        [load] = client.get(URL).json()

    assert (load["status"], load["error"]) == ("failed", "The API restarted during this load.")

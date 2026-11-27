"""Tests for the sources endpoints, used by the admin page's source forms."""

import json
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, insert
from sqlalchemy.exc import SQLAlchemyError

from src.app import app
from src.reference import api
from src.reference.load import CheckedLink, SourceLayer
from src.reference.models.public import LoadRun, SourceCheck

client = TestClient(app)

URL = "/api/v1/reference/sources"

PLACES_SOURCE: dict[str, Any] = {
    "layer": "boundaries.places",
    "download_url": "https://example.com/tl_2026_{fips}_place.zip",
    "access_type": "file",
    "format": "ESRI Shapefile",
    "field_mapping": {"geoid": "GEOID", "name": "NAME"},
}


def test_add_federal_and_state_sources(api_engine: Engine) -> None:
    """A layer can have one federal source and one source per state."""
    federal = client.post(URL, json=PLACES_SOURCE)
    texas = client.post(
        URL, json={**PLACES_SOURCE, "state": "TX", "download_url": "https://tx.example.com/a.zip"}
    )

    assert federal.status_code == 201
    assert federal.json()["state"] is None
    assert texas.status_code == 201
    assert texas.json()["state"] == "TX"
    listed = client.get(URL).json()
    assert [(item["layer"], item["state"]) for item in listed] == [
        ("boundaries.places", None),
        ("boundaries.places", "TX"),
    ]


def test_second_federal_source_conflicts(api_engine: Engine) -> None:
    """A layer can't have two federal sources."""
    client.post(URL, json=PLACES_SOURCE)

    response = client.post(URL, json=PLACES_SOURCE)

    assert response.status_code == 409
    assert response.json() == {"detail": "boundaries.places already has a federal source"}


def test_second_state_source_conflicts(api_engine: Engine) -> None:
    """A layer can't have two sources for the same state."""
    client.post(URL, json={**PLACES_SOURCE, "state": "TX"})

    response = client.post(URL, json={**PLACES_SOURCE, "state": "TX"})

    assert response.status_code == 409
    assert response.json() == {"detail": "boundaries.places already has a source for TX"}


def test_unknown_layer(api_engine: Engine) -> None:
    """A source for a table that isn't a layer is rejected."""
    response = client.post(URL, json={**PLACES_SOURCE, "layer": "public.load_runs"})

    assert response.status_code == 422
    assert response.json() == {"detail": "No layer named 'public.load_runs'"}


def test_unknown_state(api_engine: Engine) -> None:
    """A state code that isn't a state is rejected."""
    response = client.post(URL, json={**PLACES_SOURCE, "state": "ZZ"})

    assert response.status_code == 422
    assert response.json() == {"detail": "Unknown state code 'ZZ'"}


def test_unknown_access_type(api_engine: Engine) -> None:
    """The access type must be file or service."""
    response = client.post(URL, json={**PLACES_SOURCE, "access_type": "ftp"})

    assert response.status_code == 422


def test_edit_source(api_engine: Engine) -> None:
    """Editing a source changes only the fields sent."""
    created = client.post(URL, json=PLACES_SOURCE).json()
    new_url = "https://example.com/TIGER2027/tl_2027_{fips}_place.zip"

    response = client.patch(f"{URL}/{created['id']}", json={"download_url": new_url})

    assert response.status_code == 200
    assert response.json()["download_url"] == new_url
    assert response.json()["field_mapping"] == PLACES_SOURCE["field_mapping"]


def test_edit_missing_source(api_engine: Engine) -> None:
    """Editing a source that doesn't exist answers 404."""
    response = client.patch(f"{URL}/999999", json={"is_enabled": False})

    assert response.status_code == 404


def check_events(response_text: str) -> list[dict[str, Any]]:
    """Parse the JSON lines a check streams back."""
    return [json.loads(line) for line in response_text.splitlines()]


def test_check_bad_link(api_engine: Engine) -> None:
    """A link that can't be opened streams the reason as the last line."""
    response = client.post(
        f"{URL}/check",
        json={
            "layer": "boundaries.places",
            "state": "TX",
            "download_url": "http://127.0.0.1:9/none.zip",
        },
    )

    assert response.status_code == 200
    *_, last = check_events(response.text)
    assert last["stage"] == "failed"
    assert last["error"]


def test_check_unknown_layer(api_engine: Engine) -> None:
    """An unknown layer answers 422 before anything is checked."""
    response = client.post(
        f"{URL}/check",
        json={"layer": "nope.nope", "state": "TX", "download_url": "https://example.com/a.zip"},
    )

    assert response.status_code == 422


def test_check_streams_progress_then_the_result(
    api_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A link check streams the download, then the unzip, then reading, then the result."""

    def fake_check_link(*_args: Any, progress: Any) -> CheckedLink:
        progress("downloading", 340, 1200)
        progress("unzipping", 500, 4000)
        progress("reading", None, None)
        return CheckedLink(
            format="GPKG",
            layers=[SourceLayer(name="places", fields=["NAME"])],
            source_layer=None,
            field_mapping={"name": "NAME", "geoid": None},
        )

    monkeypatch.setitem(vars(api), "check_link", fake_check_link)

    response = client.post(
        f"{URL}/check",
        json={"layer": "boundaries.places", "state": "TX", "download_url": "https://example.com/a"},
    )

    assert response.headers["content-type"].startswith("application/x-ndjson")
    assert check_events(response.text) == [
        {"stage": "downloading", "progress_done": 340, "progress_total": 1200},
        {"stage": "unzipping", "progress_done": 500, "progress_total": 4000},
        {"stage": "reading"},
        {
            "stage": "done",
            "result": {
                "format": "GPKG",
                "layers": [{"name": "places", "fields": ["NAME"]}],
                "source_layer": None,
                "field_mapping": {"name": "NAME", "geoid": None},
            },
        },
    ]


def add_check(
    engine: Engine, layer: str, state: str, checked: datetime, *, update: bool, error: str | None
) -> None:
    """Insert one ``public.source_checks`` row."""
    with engine.begin() as connection:
        connection.execute(
            insert(SourceCheck).values(
                layer=layer,
                state=state,
                checked_at=checked,
                update_available=update,
                error=error,
            )
        )


def test_run_source_checks_streams_each_source(
    api_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Check for updates streams each source as it's checked, then how many were checked."""

    def fake_check_sources(engine: Engine, *, progress: Any) -> int:
        assert engine is api_engine
        progress(0, 2, "hydro.wetlands", "NC")
        progress(1, 2, "hydro.wetlands", "TX")
        return 2

    monkeypatch.setitem(vars(api), "check_sources", fake_check_sources)

    response = client.post(f"{URL}/checks")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/x-ndjson")
    assert check_events(response.text) == [
        {"stage": "checking", "checked": 0, "total": 2, "layer": "hydro.wetlands", "state": "NC"},
        {"stage": "checking", "checked": 1, "total": 2, "layer": "hydro.wetlands", "state": "TX"},
        {"stage": "done", "checked": 2, "total": 2},
    ]


def test_run_source_checks_with_nothing_loaded(api_engine: Engine) -> None:
    """With no layer loaded yet, the check ends right away with nothing checked."""
    response = client.post(f"{URL}/checks")

    assert check_events(response.text) == [{"stage": "done", "checked": 0, "total": 0}]


def test_run_source_checks_failure(api_engine: Engine, monkeypatch: pytest.MonkeyPatch) -> None:
    """A check that can't finish streams the reason as the last line."""

    def failing_check_sources(_engine: Engine, *, progress: Any) -> int:
        progress(0, 1, "hydro.wetlands", "TX")
        raise SQLAlchemyError("the reference database went away")

    monkeypatch.setitem(vars(api), "check_sources", failing_check_sources)

    response = client.post(f"{URL}/checks")

    *_, last = check_events(response.text)
    assert last == {"stage": "failed", "error": "the reference database went away"}


def test_updates_from_the_last_check(api_engine: Engine) -> None:
    """Only the layers whose last check found an update or an error are listed."""
    pulled = datetime(2026, 11, 1, tzinfo=UTC)
    with api_engine.begin() as connection:
        connection.execute(
            insert(LoadRun).values(
                layer="boundaries.states",
                state="TX",
                status="succeeded",
                started_at=pulled,
                finished_at=pulled,
            )
        )
    first = datetime(2026, 11, 2, tzinfo=UTC)
    last = datetime(2026, 11, 9, tzinfo=UTC)
    add_check(api_engine, "boundaries.states", "TX", first, update=False, error=None)
    add_check(api_engine, "boundaries.states", "TX", last, update=True, error=None)
    add_check(api_engine, "boundaries.states", "LA", last, update=False, error=None)
    add_check(api_engine, "hydro.wetlands", "TX", last, update=False, error="HTTP 404")

    response = client.get(f"{URL}/checks")

    assert response.json() == {
        "checked_at": "2026-11-09T00:00:00Z",
        "updates": [
            {
                "layer": "boundaries.states",
                "state": "TX",
                "last_pulled": "2026-11-01T00:00:00Z",
                "error": None,
            },
            {"layer": "hydro.wetlands", "state": "TX", "last_pulled": None, "error": "HTTP 404"},
        ],
    }


def test_no_checks_yet(api_engine: Engine) -> None:
    """Before the first check, there's no check time and nothing to list."""
    assert client.get(f"{URL}/checks").json() == {"checked_at": None, "updates": []}

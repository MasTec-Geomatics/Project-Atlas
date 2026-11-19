"""Tests for the sources endpoints, used by the admin page's source forms."""

from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import Engine

from src.app import app

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


def test_check_bad_link(api_engine: Engine) -> None:
    """A link that can't be opened answers 422 with the reason."""
    response = client.post(
        f"{URL}/check",
        json={
            "layer": "boundaries.places",
            "state": "TX",
            "download_url": "http://127.0.0.1:9/none.zip",
        },
    )

    assert response.status_code == 422

"""Tests for the reference sources endpoints, ``/api/v1/reference/sources``."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, insert

from src.app import app
from src.reference.load import enabled_sources
from src.reference.models.public import Source

client = TestClient(app)

TX_URL = "https://example.com/TX_geopackage_wetlands.zip"
LA_URL = "https://example.com/LA_geopackage_wetlands.zip"


def add_source(engine: Engine, state: str, url: str, *, is_enabled: bool = True) -> None:
    """Insert one ``hydro.wetlands`` row into ``public.sources``."""
    with engine.begin() as connection:
        connection.execute(
            insert(Source).values(
                layer="hydro.wetlands",
                state=state,
                download_url=url,
                format="gpkg",
                is_enabled=is_enabled,
            )
        )


@pytest.mark.usefixtures("api_engine")
def test_create_source() -> None:
    """A new source is saved and returned with its id and defaults."""
    response = client.post(
        "/api/v1/reference/sources",
        json={
            "layer": "hydro.wetlands",
            "state": "TX",
            "download_url": TX_URL,
            "format": "gpkg",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["id"] > 0
    assert body["layer"] == "hydro.wetlands"
    assert body["state"] == "TX"
    assert body["download_url"] == TX_URL
    assert body["format"] == "gpkg"
    assert body["license"] is None
    assert body["attribution"] is None
    assert body["is_enabled"] is True
    assert body["updated_at"]


@pytest.mark.usefixtures("api_engine")
def test_create_source_rejects_layer_without_loader() -> None:
    """A layer no loader handles answers 422 and saves nothing."""
    response = client.post(
        "/api/v1/reference/sources",
        json={"layer": "hydro.nothing", "state": "TX", "download_url": TX_URL, "format": "gpkg"},
    )

    assert response.status_code == 422
    assert response.json() == {"detail": "No loader for layer 'hydro.nothing'"}
    assert client.get("/api/v1/reference/sources").json() == []


@pytest.mark.usefixtures("api_engine")
@pytest.mark.parametrize("state", ["tx", "TEX", "T"])
def test_create_source_rejects_bad_state(state: str) -> None:
    """The state must be a two-letter uppercase code."""
    response = client.post(
        "/api/v1/reference/sources",
        json={"layer": "hydro.wetlands", "state": state, "download_url": TX_URL, "format": "gpkg"},
    )

    assert response.status_code == 422


@pytest.mark.usefixtures("api_engine")
def test_create_source_rejects_non_http_url() -> None:
    """The download link must be an http or https URL."""
    response = client.post(
        "/api/v1/reference/sources",
        json={
            "layer": "hydro.wetlands",
            "state": "TX",
            "download_url": "ftp://example.com/TX.zip",
            "format": "gpkg",
        },
    )

    assert response.status_code == 422


def test_create_source_rejects_duplicate(api_engine: Engine) -> None:
    """A layer can have only one source per state."""
    add_source(api_engine, "TX", TX_URL)

    response = client.post(
        "/api/v1/reference/sources",
        json={"layer": "hydro.wetlands", "state": "TX", "download_url": TX_URL, "format": "gpkg"},
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "hydro.wetlands already has a source for TX"}


def test_list_sources(api_engine: Engine) -> None:
    """Sources are listed by layer, then state."""
    add_source(api_engine, "TX", TX_URL)
    add_source(api_engine, "LA", LA_URL, is_enabled=False)

    response = client.get("/api/v1/reference/sources")

    assert response.status_code == 200
    assert [(s["state"], s["is_enabled"]) for s in response.json()] == [
        ("LA", False),
        ("TX", True),
    ]


def test_update_source(api_engine: Engine) -> None:
    """Only the fields sent are changed."""
    add_source(api_engine, "TX", TX_URL)
    source_id = client.get("/api/v1/reference/sources").json()[0]["id"]
    new_url = "https://example.com/new/TX_geopackage_wetlands.zip"

    response = client.patch(
        f"/api/v1/reference/sources/{source_id}",
        json={"download_url": new_url, "is_enabled": False},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["download_url"] == new_url
    assert body["is_enabled"] is False
    assert body["format"] == "gpkg"
    assert (body["layer"], body["state"]) == ("hydro.wetlands", "TX")


@pytest.mark.usefixtures("api_engine")
def test_update_missing_source() -> None:
    """Updating a source that doesn't exist answers 404."""
    response = client.patch("/api/v1/reference/sources/999999", json={"is_enabled": False})

    assert response.status_code == 404
    assert response.json() == {"detail": "No source with id 999999"}


def test_enabled_sources_skips_disabled_rows(api_engine: Engine) -> None:
    """Only enabled sources are loaded, ordered by state."""
    add_source(api_engine, "TX", TX_URL)
    add_source(api_engine, "OK", "https://example.com/OK.zip")
    add_source(api_engine, "LA", LA_URL, is_enabled=False)

    sources = enabled_sources(api_engine, "hydro.wetlands")

    assert [source.state for source in sources] == ["OK", "TX"]


def test_enabled_sources_for_one_state(api_engine: Engine) -> None:
    """Passing a state returns only that state's enabled source."""
    add_source(api_engine, "TX", TX_URL)
    add_source(api_engine, "LA", LA_URL)

    sources = enabled_sources(api_engine, "hydro.wetlands", "LA")

    assert [(source.state, source.download_url) for source in sources] == [("LA", LA_URL)]

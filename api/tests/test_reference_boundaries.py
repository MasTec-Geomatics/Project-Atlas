"""Tests for the boundaries loaders: states, counties, and places (ADR 0021).

Each test builds small TIGER/Line-style shapefiles, zips them like the Census downloads,
and serves them from a local HTTP server, so the full download, stage, swap, and record
steps run without the internet.
"""

import json
import threading
import zipfile
from collections.abc import Iterator
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
from sqlalchemy import Engine, TextClause, delete, insert, text

from src.reference import load
from src.reference.load import Loader, LoadError, enabled_sources, run_loads
from src.reference.loaders import LOADERS
from src.reference.models.boundaries import County, Place, State
from src.reference.models.public import LoadRun, Source


def square(lon: float, lat: float) -> list[list[float]]:
    """Return a small square ring with its lower-left corner at ``lon``, ``lat``."""
    return [[lon, lat], [lon, lat + 0.1], [lon + 0.1, lat + 0.1], [lon + 0.1, lat], [lon, lat]]


# National files hold every state; each load must keep only its own state's rows.
STATES: list[dict[str, object]] = [
    {"STATEFP": "48", "STUSPS": "TX", "NAME": "Texas", "ring": square(-98.0, 31.0)},
    {"STATEFP": "22", "STUSPS": "LA", "NAME": "Louisiana", "ring": square(-92.0, 31.0)},
]
COUNTIES: list[dict[str, object]] = [
    {"STATEFP": "48", "GEOID": "48453", "NAME": "Travis", "ring": square(-97.8, 30.2)},
    {"STATEFP": "48", "GEOID": "48201", "NAME": "Harris", "ring": square(-95.4, 29.7)},
    {"STATEFP": "22", "GEOID": "22033", "NAME": "East Baton Rouge", "ring": square(-91.1, 30.4)},
]
PLACES: list[dict[str, object]] = [
    {"STATEFP": "48", "GEOID": "4805000", "NAME": "Austin", "ring": square(-97.75, 30.25)},
    {"STATEFP": "48", "GEOID": "4835000", "NAME": "Houston", "ring": square(-95.35, 29.75)},
]


def write_shapefile_zip(directory: Path, name: str, features: list[dict[str, object]]) -> None:
    """Write ``<name>.zip`` holding one shapefile, the way the Census packages TIGER/Line.

    The shapefile is stored in EPSG:4269 (NAD83, as TIGER/Line is), so the staging step
    has to reproject it.

    Args:
        directory: Folder the local HTTP server serves.
        name: File name without extension, such as ``tl_2026_us_state``.
        features: Attributes plus a ``ring`` for each polygon.
    """
    collection = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {k: v for k, v in feature.items() if k != "ring"},
                "geometry": {"type": "Polygon", "coordinates": [feature["ring"]]},
            }
            for feature in features
        ],
    }
    build = directory / "build" / name
    build.mkdir(parents=True, exist_ok=True)
    geojson = build / f"{name}.geojson"
    geojson.write_text(json.dumps(collection))
    load.run_ogr2ogr(
        ["-f", "ESRI Shapefile", str(build / f"{name}.shp"), str(geojson), "-a_srs", "EPSG:4269"]
    )

    with zipfile.ZipFile(directory / f"{name}.zip", "w") as archive:
        for part in build.iterdir():
            if part.suffix != ".geojson":
                archive.write(part, part.name)


@pytest.fixture
def clean_tables(reference_engine: Engine) -> Iterator[None]:
    """Empty the tables these tests write to, before and after each test."""

    def empty() -> None:
        with reference_engine.begin() as connection:
            for model in (State, County, Place, LoadRun, Source):
                connection.execute(delete(model))

    empty()
    yield
    empty()


@pytest.fixture
def server(tmp_path: Path, clean_tables: None) -> Iterator[tuple[Path, str]]:
    """Serve ``tmp_path`` over HTTP.

    Yields:
        The served folder and its base URL.
    """
    handler = partial(SimpleHTTPRequestHandler, directory=str(tmp_path))
    http_server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=http_server.serve_forever, daemon=True)
    thread.start()
    yield tmp_path, f"http://127.0.0.1:{http_server.server_port}"
    http_server.shutdown()
    http_server.server_close()


def add_source(engine: Engine, layer: str, state: str, url: str) -> None:
    """Insert one ``public.sources`` row with format ``shp``."""
    with engine.begin() as connection:
        connection.execute(
            insert(Source).values(layer=layer, state=state, download_url=url, format="shp")
        )


def load_layer(engine: Engine, loader: Loader) -> None:
    """Load every enabled source of a layer, the way the load endpoint does."""
    sources = enabled_sources(engine, loader.layer)
    run_loads(engine, [loader.layer_source(source) for source in sources])


def rows(engine: Engine, query: TextClause) -> list[tuple[object, ...]]:
    """Run a query and return its rows as tuples."""
    with engine.connect() as connection:
        return [tuple(row) for row in connection.execute(query)]


def test_loaders_are_registered() -> None:
    """The three boundaries layers can be loaded through the API."""
    assert LOADERS["states"].layer == "boundaries.states"
    assert LOADERS["counties"].layer == "boundaries.counties"
    assert LOADERS["places"].layer == "boundaries.places"


def test_states_load_only_the_source_state(
    reference_engine: Engine, server: tuple[Path, str]
) -> None:
    """The national state file loads only the row for the source's state."""
    folder, base_url = server
    write_shapefile_zip(folder, "tl_2026_us_state", STATES)
    add_source(reference_engine, "boundaries.states", "TX", f"{base_url}/tl_2026_us_state.zip")

    load_layer(reference_engine, LOADERS["states"])

    assert rows(
        reference_engine,
        text("SELECT state, name, GeometryType(geom), ST_SRID(geom) FROM boundaries.states"),
    ) == [("TX", "Texas", "MULTIPOLYGON", 4326)]


def test_counties_load_only_the_source_state(
    reference_engine: Engine, server: tuple[Path, str]
) -> None:
    """The national county file loads only the source state's counties, by state FIPS code."""
    folder, base_url = server
    write_shapefile_zip(folder, "tl_2026_us_county", COUNTIES)
    add_source(reference_engine, "boundaries.counties", "TX", f"{base_url}/tl_2026_us_county.zip")

    load_layer(reference_engine, LOADERS["counties"])

    assert rows(
        reference_engine,
        text(
            "SELECT state, geoid, name, GeometryType(geom) FROM boundaries.counties ORDER BY geoid"
        ),
    ) == [
        ("TX", "48201", "Harris", "MULTIPOLYGON"),
        ("TX", "48453", "Travis", "MULTIPOLYGON"),
    ]


def test_places_load_the_state_file(reference_engine: Engine, server: tuple[Path, str]) -> None:
    """The per-state place file loads every place in it."""
    folder, base_url = server
    write_shapefile_zip(folder, "tl_2026_48_place", PLACES)
    add_source(reference_engine, "boundaries.places", "TX", f"{base_url}/tl_2026_48_place.zip")

    load_layer(reference_engine, LOADERS["places"])

    assert rows(
        reference_engine, text("SELECT state, geoid, name FROM boundaries.places ORDER BY geoid")
    ) == [("TX", "4805000", "Austin"), ("TX", "4835000", "Houston")]


def test_places_in_a_county_by_overlap(reference_engine: Engine, server: tuple[Path, str]) -> None:
    """A county's places are found by spatial overlap, with no county column on places."""
    folder, base_url = server
    write_shapefile_zip(folder, "tl_2026_us_county", COUNTIES)
    write_shapefile_zip(folder, "tl_2026_48_place", PLACES)
    add_source(reference_engine, "boundaries.counties", "TX", f"{base_url}/tl_2026_us_county.zip")
    add_source(reference_engine, "boundaries.places", "TX", f"{base_url}/tl_2026_48_place.zip")
    load_layer(reference_engine, LOADERS["counties"])
    load_layer(reference_engine, LOADERS["places"])

    assert rows(
        reference_engine,
        text(
            "SELECT p.name FROM boundaries.places p JOIN boundaries.counties c "
            "ON ST_Intersects(p.geom, c.geom) WHERE c.name = 'Travis'"
        ),
    ) == [("Austin",)]


def test_one_download_for_states_sharing_a_file(
    reference_engine: Engine, server: tuple[Path, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Two states from the same national file are loaded from a single download."""
    folder, base_url = server
    write_shapefile_zip(folder, "tl_2026_us_state", STATES)
    url = f"{base_url}/tl_2026_us_state.zip"
    add_source(reference_engine, "boundaries.states", "TX", url)
    add_source(reference_engine, "boundaries.states", "LA", url)

    downloads: list[str] = []
    real_download = load.download

    def counting_download(
        source_url: str, work_dir: Path, file_suffix: str
    ) -> tuple[Path, str | None]:
        downloads.append(source_url)
        return real_download(source_url, work_dir, file_suffix)

    monkeypatch.setitem(vars(load), "download", counting_download)

    load_layer(reference_engine, LOADERS["states"])

    assert downloads == [url]
    assert rows(
        reference_engine, text("SELECT state, name FROM boundaries.states ORDER BY state")
    ) == [("LA", "Louisiana"), ("TX", "Texas")]
    assert rows(
        reference_engine,
        text("SELECT state, status FROM public.load_runs ORDER BY state"),
    ) == [("LA", "succeeded"), ("TX", "succeeded")]


def test_failed_download_fails_every_state_sharing_it(
    reference_engine: Engine, server: tuple[Path, str]
) -> None:
    """When a shared download fails, every state that uses it is recorded as failed."""
    _, base_url = server
    url = f"{base_url}/missing.zip"
    add_source(reference_engine, "boundaries.states", "TX", url)
    add_source(reference_engine, "boundaries.states", "LA", url)

    with pytest.raises(LoadError, match="404"):
        load_layer(reference_engine, LOADERS["states"])

    assert rows(
        reference_engine,
        text("SELECT state, status FROM public.load_runs ORDER BY state"),
    ) == [("LA", "failed"), ("TX", "failed")]

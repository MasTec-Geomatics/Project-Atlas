"""Tests for the reference loader framework (#69) and the wetlands loader (#70).

Each test builds a small NWI-style GeoPackage, zips it like the USFWS state download,
and serves it from a local HTTP server, so the full download, stage, swap, and record
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
from sqlalchemy import Engine, Row, text

from src.reference import load
from src.reference.load import LoadError
from src.reference.loaders import wetlands

# Two NWI-style features in EPSG:4326. Plain Polygons, so the test also proves they
# arrive in the final table as MultiPolygons.
FEATURES = [
    {
        "ATTRIBUTE": "PEM1C",
        "WETLAND_TYPE": "Freshwater Emergent Wetland",
        "ACRES": 1.25,
        "ring": [[-97.0, 30.0], [-97.0, 30.01], [-96.99, 30.01], [-96.99, 30.0], [-97.0, 30.0]],
    },
    {
        "ATTRIBUTE": "PUBHh",
        "WETLAND_TYPE": "Freshwater Pond",
        "ACRES": 0.5,
        "ring": [[-98.0, 31.0], [-98.0, 31.01], [-97.99, 31.01], [-97.99, 31.0], [-98.0, 31.0]],
    },
]


def write_download(directory: Path, *, drop_field: str | None = None) -> None:
    """Write ``TX_geopackage_wetlands.zip`` the way USFWS packages a state download.

    The GeoPackage is stored in EPSG:5070 (NWI's Albers projection), so the staging
    step has to reproject it.

    Args:
        directory: Folder the local HTTP server serves.
        drop_field: Source field to leave out, to simulate a source structure change.
    """
    features = []
    for feature in FEATURES:
        properties = {k: v for k, v in feature.items() if k not in ("ring", drop_field)}
        geometry = {"type": "Polygon", "coordinates": [feature["ring"]]}
        features.append({"type": "Feature", "properties": properties, "geometry": geometry})

    build = directory / "build"
    build.mkdir(exist_ok=True)
    geojson = build / "wetlands.geojson"
    geojson.write_text(json.dumps({"type": "FeatureCollection", "features": features}))

    gpkg = build / "TX_Wetlands.gpkg"
    gpkg.unlink(missing_ok=True)
    load.run_ogr2ogr(
        ["-f", "GPKG", str(gpkg), str(geojson), "-nln", "TX_Wetlands", "-t_srs", "EPSG:5070"]
    )

    with zipfile.ZipFile(directory / "TX_geopackage_wetlands.zip", "w") as archive:
        archive.write(gpkg, "TX_geopackage_wetlands/TX_Wetlands.gpkg")
        archive.writestr("TX_geopackage_wetlands/readme.txt", "NWI sample")


@pytest.fixture
def served(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Serve ``tmp_path`` over HTTP and point the wetlands loader at it.

    Yields:
        The served folder; tests write the download into it.
    """
    handler = partial(SimpleHTTPRequestHandler, directory=str(tmp_path))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    url = f"http://127.0.0.1:{server.server_port}/TX_geopackage_wetlands.zip"
    monkeypatch.setattr(wetlands, "SOURCES", {"TX": url})
    yield tmp_path

    server.shutdown()
    server.server_close()


@pytest.fixture
def clean_tables(reference_engine: Engine) -> Iterator[None]:
    """Empty the tables these tests write to, before and after each test."""

    # noinspection SqlWithoutWhere
    def empty() -> None:
        with reference_engine.begin() as connection:
            connection.execute(text("DELETE FROM hydro.wetlands"))
            connection.execute(text("DELETE FROM public.load_runs"))

    empty()
    yield
    empty()


def latest_run(engine: Engine) -> Row:
    """Return the most recent ``public.load_runs`` row."""
    with engine.connect() as connection:
        return connection.execute(
            text("SELECT * FROM public.load_runs ORDER BY id DESC LIMIT 1")
        ).one()


def wetland_rows(engine: Engine) -> list[Row]:
    """Return every ``hydro.wetlands`` row with its geometry type and SRID."""
    with engine.connect() as connection:
        return list(
            connection.execute(
                text(
                    "SELECT state, cowardin_code, wetland_type, acres, "
                    "GeometryType(geom) AS geom_type, ST_SRID(geom) AS srid, "
                    "ST_X(ST_Centroid(geom)) AS lon, ST_Y(ST_Centroid(geom)) AS lat "
                    "FROM hydro.wetlands ORDER BY cowardin_code"
                )
            )
        )


@pytest.mark.usefixtures("clean_tables")
def test_load_fills_table_with_mapped_columns(reference_engine: Engine, served: Path) -> None:
    """A load maps NWI fields to the final columns as 4326 MultiPolygons."""
    write_download(served)

    wetlands.load_wetlands(reference_engine)

    rows = wetland_rows(reference_engine)
    assert [(r.state, r.cowardin_code, r.wetland_type, float(r.acres)) for r in rows] == [
        ("TX", "PEM1C", "Freshwater Emergent Wetland", 1.25),
        ("TX", "PUBHh", "Freshwater Pond", 0.5),
    ]
    assert {(r.geom_type, r.srid) for r in rows} == {("MULTIPOLYGON", 4326)}
    assert rows[0].lon == pytest.approx(-96.995, abs=1e-6)
    assert rows[0].lat == pytest.approx(30.005, abs=1e-6)


@pytest.mark.usefixtures("clean_tables")
def test_load_records_succeeded_run(reference_engine: Engine, served: Path) -> None:
    """A good load is recorded as succeeded with its row count and source version."""
    write_download(served)

    wetlands.load_wetlands(reference_engine)

    run = latest_run(reference_engine)
    assert (run.layer, run.state, run.status) == ("hydro.wetlands", "TX", "succeeded")
    assert run.rows_loaded == 2
    assert run.source_version  # Last-Modified from the server
    assert run.error is None
    assert run.finished_at is not None


@pytest.mark.usefixtures("clean_tables")
def test_reload_replaces_rows(reference_engine: Engine, served: Path) -> None:
    """Loading again replaces the state's rows instead of adding to them."""
    write_download(served)

    wetlands.load_wetlands(reference_engine)
    wetlands.load_wetlands(reference_engine)

    assert len(wetland_rows(reference_engine)) == 2


@pytest.mark.usefixtures("clean_tables")
def test_staging_table_is_dropped_after_swap(reference_engine: Engine, served: Path) -> None:
    """The raw staged copy is removed once the final table has the data."""
    write_download(served)

    wetlands.load_wetlands(reference_engine)

    with reference_engine.connect() as connection:
        staged = connection.scalar(text("SELECT to_regclass('staging.wetlands')"))
    assert staged is None


@pytest.mark.usefixtures("clean_tables")
def test_missing_field_fails_and_keeps_previous_data(
    reference_engine: Engine, served: Path
) -> None:
    """A source missing an expected field fails loudly and leaves the final table alone."""
    write_download(served)
    wetlands.load_wetlands(reference_engine)

    write_download(served, drop_field="WETLAND_TYPE")
    with pytest.raises(LoadError, match="wetland_type"):
        wetlands.load_wetlands(reference_engine)

    assert len(wetland_rows(reference_engine)) == 2
    run = latest_run(reference_engine)
    assert run.status == "failed"
    assert "wetland_type" in run.error
    assert run.finished_at is not None


@pytest.mark.usefixtures("clean_tables")
def test_failed_download_is_recorded(reference_engine: Engine, served: Path) -> None:
    """A download error (here a 404, nothing written to the served folder) is recorded."""
    with pytest.raises(LoadError, match="404"):
        wetlands.load_wetlands(reference_engine)

    assert latest_run(reference_engine).status == "failed"


@pytest.mark.usefixtures("clean_tables")
def test_main_exit_codes(
    reference_engine: Engine, served: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The command exits 0 when the load succeeds and 1 when it fails."""
    monkeypatch.setattr(load, "reference_engine", reference_engine)

    assert load.main(["wetlands"]) == 1  # nothing served yet

    write_download(served)
    assert load.main(["wetlands"]) == 0


def test_main_rejects_unknown_layer() -> None:
    """An unknown layer name exits with argparse's usage error code."""
    with pytest.raises(SystemExit) as exit_info:
        load.main(["not_a_layer"])

    assert exit_info.value.code == 2

"""Tests for the reference loader (ADR 0018, ADR 0021).

Each test builds small datasets, zips them like the providers do, and serves them from a
local HTTP server, so the full download, stage, swap, and record steps run without the
internet.
"""

import json
import os
import shutil
import threading
import time
import zipfile
from collections.abc import Iterator, Sequence
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import delete, Engine, insert, text, TextClause

from src.reference import load
from src.reference.load import check_link, fill, LoadError, plan_load, run_loads
from src.reference.models import metadata
from src.reference.models.public import LoadRun, Source


def square(lon: float, lat: float, size: float = 0.1) -> list[list[float]]:
    """Return a square ring with its lower-left corner at ``lon``, ``lat``."""
    return [[lon, lat], [lon, lat + size], [lon + size, lat + size], [lon + size, lat], [lon, lat]]


# National files hold every state; each load keeps only its own state's rows.
STATES: list[dict[str, Any]]   = [
        {"STATEFP": "48", "STUSPS": "TX", "NAME": "Texas", "ring": square(-98.0, 31.0, 1.0)},
        {"STATEFP": "22", "STUSPS": "LA", "NAME": "Louisiana", "ring": square(-92.0, 31.0, 1.0)},
        ]
COUNTIES: list[dict[str, Any]] = [
        {"STATEFP": "48", "GEOID": "48453", "NAME": "Travis", "ring": square(-97.8, 30.2)},
        {"STATEFP": "48", "GEOID": "48201", "NAME": "Harris", "ring": square(-95.4, 29.7)},
        {
                "STATEFP": "22", "GEOID": "22033", "NAME": "East Baton Rouge",
                "ring": square(-91.1, 30.4),
                },
        ]
PLACES: list[dict[str, Any]]   = [
        {"GEOID": "4805000", "NAME": "Austin", "ring": square(-97.75, 30.25)},
        {"GEOID": "4835000", "NAME": "Houston", "ring": square(-95.35, 29.75)},
        ]
WETLANDS: list[dict[str, Any]] = [
        {
                "ATTRIBUTE": "PEM1C",
                "WETLAND_TYPE": "Freshwater Emergent Wetland",
                "ACRES": 2.5,
                "ring": square(-97.5, 31.5),
                },
        {"ATTRIBUTE": "L1UBH", "WETLAND_TYPE": "Lake", "ACRES": 40.0, "ring": square(-97.4, 31.4)},
        ]


def write_zip(
        directory: Path,
        name: str,
        features: list[dict[str, Any]],
        *,
        gdal_format: str = "ESRI Shapefile",
        layer_name: str | None = None,
        ) -> None:
    """Write ``<name>.zip`` holding one dataset, the way providers package downloads.

    The dataset is stored in EPSG:4269 (NAD83), so the staging step has to reproject it.

    Args:
        directory: Folder the local HTTP server serves.
        name: File name without extension, such as ``tl_2026_us_state``.
        features: Attributes plus a ``ring`` for each polygon.
        gdal_format: ``ESRI Shapefile`` or ``GPKG``.
        layer_name: Layer name inside a GeoPackage.
    """
    collection = {
            "type": "FeatureCollection",
            "features": [
                    {
                            "type": "Feature",
                            "properties": {key: value for key, value in feature.items() if
                                           key != "ring"},
                            "geometry": {"type": "Polygon", "coordinates": [feature["ring"]]},
                            }
                    for feature in features
                    ],
            }
    build      = directory / "build" / name
    build.mkdir(parents=True, exist_ok=True)
    geojson = build / f"{name}.geojson"
    geojson.write_text(json.dumps(collection))
    suffix = ".shp" if gdal_format == "ESRI Shapefile" else ".gpkg"
    layer  = [] if layer_name is None else ["-nln", layer_name]
    load.run_gdal(
            "ogr2ogr",
            [
                    "-f",
                    gdal_format,
                    str(build / f"{name}{suffix}"),
                    str(geojson),
                    "-a_srs",
                    "EPSG:4269",
                    *layer,
                    ],
            )

    with zipfile.ZipFile(directory / f"{name}.zip", "w") as archive:
        for part in build.iterdir():
            if part.suffix != ".geojson":
                archive.write(part, part.name)


@pytest.fixture
def server(tmp_path: Path, clean_engine: Engine) -> Iterator[tuple[Path, str]]:
    """Serve ``tmp_path`` over HTTP, with empty layer tables.

    Yields:
        The served folder and its base URL.
    """
    with clean_engine.begin() as connection:
        for layer in (
                    "boundaries.states",
                    "boundaries.counties",
                    "boundaries.places",
                    "hydro.wetlands",
                ):
            connection.execute(delete(metadata.tables[layer]))

    handler     = partial(SimpleHTTPRequestHandler, directory=str(tmp_path))
    http_server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread      = threading.Thread(target=http_server.serve_forever, daemon=True)
    thread.start()
    yield tmp_path, f"http://127.0.0.1:{http_server.server_port}"
    http_server.shutdown()
    http_server.server_close()
    shutil.rmtree(load.DOWNLOADS_DIR, ignore_errors=True)


def add_source(engine: Engine, **values: Any) -> None:
    """Insert one ``public.sources`` row, with a shapefile download by default."""
    row = {"access_type": "file", "format": "ESRI Shapefile", **values}
    with engine.begin() as connection:
        connection.execute(insert(Source).values(**row))


def load_states(engine: Engine, layer: str, states: list[str]) -> None:
    """Load a layer for the given states, the way the load endpoint does."""
    run_loads(engine, [plan_load(engine, layer, state) for state in states])


def rows(engine: Engine, query: TextClause) -> list[tuple[object, ...]]:
    """Run a query and return its rows as tuples."""
    with engine.connect() as connection:
        return [tuple(row) for row in connection.execute(query)]


def add_state_outlines(engine: Engine, base_url: str, folder: Path, states: list[str]) -> None:
    """Load ``boundaries.states`` for the given states from a national state file."""
    write_zip(folder, "tl_2026_us_state", STATES)
    add_source(
            engine,
            layer="boundaries.states",
            download_url=f"{base_url}/tl_2026_us_state.zip",
            field_mapping={"name": "NAME"},
            keep={"STUSPS": ["{state}"]},
            )
    load_states(engine, "boundaries.states", states)


def test_fill() -> None:
    """``{state}`` and ``{fips}`` are filled in for the state."""
    assert fill("tl_2026_{fips}_place.zip", "TX") == "tl_2026_48_place.zip"
    assert fill("{state}_Wetlands", "LA") == "LA_Wetlands"


def test_national_file_keeps_only_the_state(clean_engine: Engine, server: tuple[Path, str]) -> None:
    """A federal source on a national file keeps only the loaded state's row."""
    folder, base_url = server
    add_state_outlines(clean_engine, base_url, folder, ["TX"])

    assert rows(
            clean_engine,
            text("SELECT state, name, geometrytype(geom), st_srid(geom) FROM boundaries.states"),
            ) == [("TX", "Texas", "MULTIPOLYGON", 4326)]


def test_keep_by_fips(clean_engine: Engine, server: tuple[Path, str]) -> None:
    """``{fips}`` in a keep value keeps the state's counties."""
    folder, base_url = server
    write_zip(folder, "tl_2026_us_county", COUNTIES)
    add_source(
            clean_engine,
            layer="boundaries.counties",
            download_url=f"{base_url}/tl_2026_us_county.zip",
            field_mapping={"geoid": "GEOID", "name": "NAME"},
            keep={"STATEFP": ["{fips}"]},
            )

    load_states(clean_engine, "boundaries.counties", ["TX"])

    assert rows(
            clean_engine, text("SELECT state, geoid, name FROM boundaries.counties ORDER BY geoid"),
            ) == [("TX", "48201", "Harris"), ("TX", "48453", "Travis")]


def test_link_filled_per_state(clean_engine: Engine, server: tuple[Path, str]) -> None:
    """``{fips}`` in the link downloads the state's own file."""
    folder, base_url = server
    write_zip(folder, "tl_2026_48_place", PLACES)
    add_source(
            clean_engine,
            layer="boundaries.places",
            download_url=f"{base_url}/tl_2026_{{fips}}_place.zip",
            field_mapping={"geoid": "GEOID", "name": "NAME"},
            )

    load_states(clean_engine, "boundaries.places", ["TX"])

    assert rows(
            clean_engine, text("SELECT state, geoid, name FROM boundaries.places ORDER BY geoid"),
            ) == [("TX", "4805000", "Austin"), ("TX", "4835000", "Houston")]


def test_state_source_wins(clean_engine: Engine, server: tuple[Path, str]) -> None:
    """A state source is used for its state instead of the federal source."""
    folder, base_url = server
    write_zip(folder, "texas_places", PLACES[:1])
    add_source(
            clean_engine,
            layer="boundaries.places",
            download_url=f"{base_url}/missing_{{fips}}.zip",
            field_mapping={"geoid": "GEOID", "name": "NAME"},
            )
    add_source(
            clean_engine,
            layer="boundaries.places",
            state="TX",
            download_url=f"{base_url}/texas_places.zip",
            field_mapping={"geoid": "GEOID", "name": "NAME"},
            )

    load_states(clean_engine, "boundaries.places", ["TX"])

    assert rows(clean_engine, text("SELECT name FROM boundaries.places")) == [("Austin",)]


def test_geopackage_layer_and_keep(clean_engine: Engine, server: tuple[Path, str]) -> None:
    """The ``{state}`` layer inside a GeoPackage is loaded, keeping only listed values."""
    folder, base_url = server
    write_zip(
            folder, "TX_geopackage_wetlands", WETLANDS, gdal_format="GPKG", layer_name="TX_Wetlands",
            )
    add_source(
            clean_engine,
            layer="hydro.wetlands",
            download_url=f"{base_url}/{{state}}_geopackage_wetlands.zip",
            format="GPKG",
            source_layer="{state}_Wetlands",
            field_mapping={
                    "cowardin_code": "ATTRIBUTE",
                    "wetland_type": "WETLAND_TYPE",
                    "acres": "ACRES",
                    },
            keep={"WETLAND_TYPE": ["Freshwater Emergent Wetland"]},
            )

    load_states(clean_engine, "hydro.wetlands", ["TX"])

    assert rows(
            clean_engine, text("SELECT state, cowardin_code, wetland_type FROM hydro.wetlands"),
            ) == [("TX", "PEM1C", "Freshwater Emergent Wetland")]


def test_clip_to_state(clean_engine: Engine, server: tuple[Path, str]) -> None:
    """With ``clip_to_state``, a shape crossing the state line keeps only its part inside."""
    folder, base_url = server
    add_state_outlines(clean_engine, base_url, folder, ["TX"])
    crossing = [{"GEOID": "1", "NAME": "Across", "ring": square(-97.5, 31.5, 1.0)}]
    write_zip(folder, "crossing", crossing)
    add_source(
            clean_engine,
            layer="boundaries.places",
            download_url=f"{base_url}/crossing.zip",
            field_mapping={"geoid": "GEOID", "name": "NAME"},
            clip_to_state=True,
            )

    load_states(clean_engine, "boundaries.places", ["TX"])

    [(area,)] = rows(clean_engine, text("SELECT st_area(geom) FROM boundaries.places"))
    assert area == pytest.approx(0.25, rel=1e-3)


def test_clip_needs_the_state_outline(clean_engine: Engine, server: tuple[Path, str]) -> None:
    """A clipped load fails when the state's outline isn't loaded."""
    folder, base_url = server
    write_zip(folder, "tl_2026_48_place", PLACES)
    add_source(
            clean_engine,
            layer="boundaries.places",
            download_url=f"{base_url}/tl_2026_{{fips}}_place.zip",
            field_mapping={"geoid": "GEOID", "name": "NAME"},
            clip_to_state=True,
            )

    with pytest.raises(LoadError, match=r"Load boundaries\.states for TX first"):
        load_states(clean_engine, "boundaries.places", ["TX"])


def test_one_download_for_states_sharing_a_file(
        clean_engine: Engine, server: tuple[Path, str], monkeypatch: pytest.MonkeyPatch,
        ) -> None:
    """Two states from the same national file are loaded from a single download."""
    folder, base_url = server
    write_zip(folder, "tl_2026_us_state", STATES)
    url = f"{base_url}/tl_2026_us_state.zip"
    add_source(
            clean_engine,
            layer="boundaries.states",
            download_url=url,
            field_mapping={"name": "NAME"},
            keep={"STUSPS": ["{state}"]},
            )
    downloads: list[str] = []
    real_download        = load.download

    def counting_download(
            source_url: str, on_progress: load.Counted | None = None,
            ) -> tuple[Path, str | None]:
        downloads.append(source_url)
        return real_download(source_url, on_progress)

    monkeypatch.setitem(vars(load), "download", counting_download)

    load_states(clean_engine, "boundaries.states", ["TX", "LA"])

    assert downloads == [url]
    assert rows(clean_engine, text("SELECT state, name FROM boundaries.states ORDER BY state")) == [
            ("LA", "Louisiana"),
            ("TX", "Texas"),
            ]
    assert rows(
            clean_engine, text("SELECT state, status FROM public.load_runs ORDER BY state"),
            ) == [("LA", "succeeded"), ("TX", "succeeded")]


def test_failed_download_fails_every_state(clean_engine: Engine, server: tuple[Path, str]) -> None:
    """When a shared download fails, every state that uses it is recorded as failed."""
    _, base_url = server
    add_source(
            clean_engine,
            layer="boundaries.states",
            download_url=f"{base_url}/missing.zip",
            field_mapping={"name": "NAME"},
            )

    with pytest.raises(LoadError, match="404"):
        load_states(clean_engine, "boundaries.states", ["TX", "LA"])

    assert rows(
            clean_engine, text("SELECT state, status FROM public.load_runs ORDER BY state"),
            ) == [("LA", "failed"), ("TX", "failed")]


def test_renamed_field_leaves_the_table_alone(
        clean_engine: Engine, server: tuple[Path, str],
        ) -> None:
    """A mapped field missing from the source fails the load without touching the table."""
    folder, base_url = server
    add_state_outlines(clean_engine, base_url, folder, ["TX"])
    with clean_engine.begin() as connection:
        connection.execute(
                text(
                        'UPDATE public.sources SET field_mapping = \'{"name": "FULL_NAME"}\' '
                        "WHERE layer = 'boundaries.states'",
                        ),
                )

    with pytest.raises(LoadError, match="full_name"):
        load_states(clean_engine, "boundaries.states", ["TX"])

    assert rows(clean_engine, text("SELECT name FROM boundaries.states")) == [("Texas",)]


def test_no_source(clean_engine: Engine) -> None:
    """A layer with no enabled source for the state can't be planned."""
    with pytest.raises(LoadError, match=r"No enabled source for hydro\.wetlands in TX"):
        plan_load(clean_engine, "hydro.wetlands", "TX")


def test_check_link_matches_fields(clean_engine: Engine, server: tuple[Path, str]) -> None:
    """Checking a link reports its layers and matches fields to the current source."""
    folder, base_url = server
    renamed          = [
            {"ATTRIBUTE": "PEM1C", "WETLAND_CLASS": "x", "ACRES": 1.0, "ring": square(0, 0)},
            ]
    write_zip(
            folder, "TX_geopackage_wetlands", renamed, gdal_format="GPKG", layer_name="TX_Wetlands",
            )
    add_source(
            clean_engine,
            layer="hydro.wetlands",
            download_url=f"{base_url}/old.zip",
            format="GPKG",
            source_layer="{state}_Wetlands",
            field_mapping={
                    "cowardin_code": "ATTRIBUTE",
                    "wetland_type": "WETLAND_TYPE",
                    "acres": "ACRES",
                    },
            )

    checked = check_link(
            clean_engine,
            "hydro.wetlands",
            "TX",
            f"{base_url}/{{state}}_geopackage_wetlands.zip",
            "file",
            )

    assert checked.format == "GPKG"
    assert [item.name for item in checked.layers] == ["TX_Wetlands"]
    assert checked.field_mapping == {
            "cowardin_code": "ATTRIBUTE",
            "wetland_type": None,
            "acres": "ACRES",
            }


def kept_downloads() -> list[Path]:
    """The files in the kept downloads folder."""
    if not load.DOWNLOADS_DIR.exists():
        return []
    return sorted(load.DOWNLOADS_DIR.iterdir())


def test_load_uses_the_checked_download(clean_engine: Engine, server: tuple[Path, str]) -> None:
    """A load uses the file Check link downloaded instead of downloading it again."""
    folder, base_url = server
    write_zip(folder, "tl_2026_us_state", STATES)
    url = f"{base_url}/tl_2026_us_state.zip"
    add_source(
            clean_engine,
            layer="boundaries.states",
            download_url=url,
            field_mapping={"name": "NAME"},
            keep={"STUSPS": ["{state}"]},
            )
    check_link(clean_engine, "boundaries.states", "TX", url, "file")
    (folder / "tl_2026_us_state.zip").unlink()

    load_states(clean_engine, "boundaries.states", ["TX"])

    assert rows(clean_engine, text("SELECT name FROM boundaries.states")) == [("Texas",)]


def test_load_deletes_the_download_after_the_swap(
        clean_engine: Engine, server: tuple[Path, str],
        ) -> None:
    """Once every state is swapped in, the kept download is deleted."""
    folder, base_url = server
    url              = f"{base_url}/tl_2026_us_state.zip"
    write_zip(folder, "tl_2026_us_state", STATES)
    check_link(clean_engine, "boundaries.states", "TX", url, "file")
    assert kept_downloads()

    add_state_outlines(clean_engine, base_url, folder, ["TX", "LA"])

    assert kept_downloads() == []


def test_failed_swap_keeps_the_download(clean_engine: Engine, server: tuple[Path, str]) -> None:
    """A failed swap keeps the download, and the next load uses it."""
    folder, base_url = server
    write_zip(folder, "tl_2026_us_state", STATES)
    add_source(
            clean_engine,
            layer="boundaries.states",
            download_url=f"{base_url}/tl_2026_us_state.zip",
            field_mapping={"name": "FULL_NAME"},
            keep={"STUSPS": ["{state}"]},
            )
    with pytest.raises(LoadError, match="full_name"):
        load_states(clean_engine, "boundaries.states", ["TX"])
    assert kept_downloads()

    (folder / "tl_2026_us_state.zip").unlink()
    with clean_engine.begin() as connection:
        connection.execute(
                text(
                        'UPDATE public.sources SET field_mapping = \'{"name": "NAME"}\' '
                        "WHERE layer = 'boundaries.states'",
                        ),
                )
    load_states(clean_engine, "boundaries.states", ["TX"])

    assert rows(clean_engine, text("SELECT name FROM boundaries.states")) == [("Texas",)]
    assert kept_downloads() == []


def current_run(engine: Engine) -> list[tuple[object, ...]]:
    """The status, stage, and stage progress of every ``public.load_runs`` row."""
    return rows(
            engine,
            text("SELECT status, stage, progress_done, progress_total FROM public.load_runs"),
            )


def unzipped_size(archive: Path) -> int:
    """The total size of the files inside a zip, once unzipped."""
    with zipfile.ZipFile(archive) as opened:
        return sum(member.file_size for member in opened.infolist())


def stage_order(stages: Sequence[object]) -> list[object]:
    """The stages in the order they came, each listed once per run of repeats."""
    return [stage for index, stage in enumerate(stages) if index == 0 or stages[index - 1] != stage]


def test_load_records_each_stage(
        clean_engine: Engine, server: tuple[Path, str], monkeypatch: pytest.MonkeyPatch,
        ) -> None:
    """A running load records each stage in turn, with how far along it is.

    Downloading and unzipping count bytes, copying counts percent, and swapping has no
    count. The progress is cleared when the load ends.
    """
    folder, base_url = server
    write_zip(folder, "tl_2026_us_state", STATES)
    archive  = folder / "tl_2026_us_state.zip"
    size     = archive.stat().st_size
    unzipped = unzipped_size(archive)
    add_source(
            clean_engine,
            layer="boundaries.states",
            download_url=f"{base_url}/tl_2026_us_state.zip",
            field_mapping={"name": "NAME"},
            keep={"STUSPS": ["{state}"]},
            )
    seen: list[tuple[object, ...]] = []

    def watch(recorder: str) -> Any:
        """Wrap a recorder so the load's row is read back each time it's written."""
        recorder_function = vars(load)[recorder]

        def watching(*args: Any) -> None:
            recorder_function(*args)
            seen.extend(current_run(clean_engine))

        return watching

    for recorder_name in ("set_stage", "record_progress"):
        monkeypatch.setitem(vars(load), recorder_name, watch(recorder_name))

    load_states(clean_engine, "boundaries.states", ["TX"])

    assert stage_order([row[1] for row in seen]) == [
            "downloading",
            "unzipping",
            "copying",
            "swapping",
            ]
    last = {row[1]: row for row in seen}
    assert last["downloading"] == ("running", "downloading", size, size)
    assert last["unzipping"] == ("running", "unzipping", unzipped, unzipped)
    assert last["copying"] == ("running", "copying", 100, 100)
    assert last["swapping"] == ("running", "swapping", None, None)
    assert current_run(clean_engine) == [("succeeded", None, None, None)]


def test_unzip_refuses_a_path_outside_its_folder(
        clean_engine: Engine, server: tuple[Path, str],
        ) -> None:
    """A zip holding a path that climbs out of the unzip folder fails the load."""
    folder, base_url = server
    with zipfile.ZipFile(folder / "climbing.zip", "w") as archive:
        archive.writestr("../outside.shp", "x")
    add_source(
            clean_engine,
            layer="boundaries.states",
            download_url=f"{base_url}/climbing.zip",
            field_mapping={"name": "NAME"},
            )

    with pytest.raises(LoadError, match=r"outside\.shp"):
        load_states(clean_engine, "boundaries.states", ["TX"])


def test_clipped_load_stages_only_the_state_area(
        clean_engine: Engine, server: tuple[Path, str], monkeypatch: pytest.MonkeyPatch,
        ) -> None:
    """A load cut at the state line stages only what's inside the state's rectangle."""
    folder, base_url = server
    add_state_outlines(clean_engine, base_url, folder, ["TX"])
    write_zip(folder, "tl_2026_48_place", PLACES)
    add_source(
            clean_engine,
            layer="boundaries.places",
            download_url=f"{base_url}/tl_2026_{{fips}}_place.zip",
            field_mapping={"geoid": "GEOID", "name": "NAME"},
            clip_to_state=True,
            )
    commands: list[list[str]] = []
    real_run_gdal             = load.run_gdal

    def recording_run_gdal(
            tool: str,
            arguments: list[str],
            *,
            password: str | None = None,
            on_progress: load.Counted | None = None,
            ) -> str:
        commands.append(arguments)
        return real_run_gdal(tool, arguments, password=password, on_progress=on_progress)

    monkeypatch.setitem(vars(load), "run_gdal", recording_run_gdal)

    load_states(clean_engine, "boundaries.places", ["TX"])

    [staging_command] = commands
    spat              = staging_command.index("-spat")
    assert [float(value) for value in staging_command[spat + 1: spat + 5]] == pytest.approx(
            [-98.0, 31.0, -97.0, 32.0], abs=1e-3,
            )
    assert staging_command[spat + 5: spat + 7] == ["-spat_srs", "EPSG:4326"]


def test_restart_fails_interrupted_loads(clean_engine: Engine) -> None:
    """Loads left running when the API stopped are recorded as failed."""
    with clean_engine.begin() as connection:
        connection.execute(
                insert(LoadRun).values(
                        layer="hydro.wetlands", state="TX", status="running", stage="downloading",
                        ),
                )

    load.fail_interrupted_runs(clean_engine)

    assert rows(
            clean_engine,
            text("SELECT status, stage, error, finished_at IS NOT NULL FROM public.load_runs"),
            ) == [("failed", None, "The API restarted during this load.", True)]


def test_check_link_reports_its_progress(clean_engine: Engine, server: tuple[Path, str]) -> None:
    """Checking a link reports the download, then the unzip, then reading the fields."""
    folder, base_url = server
    write_zip(folder, "tl_2026_us_state", STATES)
    archive                                            = folder / "tl_2026_us_state.zip"
    size                                               = archive.stat().st_size
    unzipped                                           = unzipped_size(archive)
    progress: list[tuple[str, int | None, int | None]] = []

    def report(stage: str, done: int | None, total: int | None) -> None:
        progress.append((stage, done, total))

    check_link(
            clean_engine,
            "boundaries.states",
            "TX",
            f"{base_url}/tl_2026_us_state.zip",
            "file",
            progress=report,
            )

    assert stage_order([stage for stage, _, _ in progress]) == [
            "downloading",
            "unzipping",
            "reading",
            ]
    last = {stage: (done, total) for stage, done, total in progress}
    assert last == {
            "downloading": (size, size),
            "unzipping": (unzipped, unzipped),
            "reading": (None, None),
            }


def source_checks(engine: Engine) -> list[tuple[object, ...]]:
    """The layer, state, result, and error of every ``public.source_checks`` row."""
    return rows(
            engine,
            text(
                    "SELECT layer, state, update_available, error FROM public.source_checks "
                    "ORDER BY checked_at, id",
                    ),
            )


def test_source_check_finds_a_newer_file(clean_engine: Engine, server: tuple[Path, str]) -> None:
    """A source whose file changed since the last load is marked as having an update."""
    folder, base_url = server
    add_state_outlines(clean_engine, base_url, folder, ["TX"])

    load.check_sources(clean_engine)
    later = time.time() + 3600
    os.utime(folder / "tl_2026_us_state.zip", (later, later))
    load.check_sources(clean_engine)

    assert source_checks(clean_engine) == [
            ("boundaries.states", "TX", False, None),
            ("boundaries.states", "TX", True, None),
            ]


def test_source_check_reports_each_source(clean_engine: Engine, server: tuple[Path, str]) -> None:
    """A change check reports each layer and state before asking its source.

    The two states share one national file, so the file is asked once, but each state is
    still reported and recorded.
    """
    folder, base_url = server
    add_state_outlines(clean_engine, base_url, folder, ["LA", "TX"])
    progress: list[tuple[int, int, str, str]] = []

    def report(checked: int, total: int, layer: str, state: str) -> None:
        progress.append((checked, total, layer, state))

    count = load.check_sources(clean_engine, progress=report)

    assert count == 2
    assert progress == [
            (0, 2, "boundaries.states", "LA"),
            (1, 2, "boundaries.states", "TX"),
            ]
    assert len(source_checks(clean_engine)) == 2


def test_source_check_records_an_unreachable_source(
        clean_engine: Engine, server: tuple[Path, str],
        ) -> None:
    """A source that can't be reached is recorded with the reason."""
    folder, base_url = server
    add_state_outlines(clean_engine, base_url, folder, ["TX"])
    (folder / "tl_2026_us_state.zip").unlink()

    load.check_sources(clean_engine)

    [(layer, state, update_available, error)] = source_checks(clean_engine)
    assert (layer, state, update_available) == ("boundaries.states", "TX", False)
    assert isinstance(error, str)
    assert "404" in error

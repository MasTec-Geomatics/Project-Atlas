"""Load one reference layer (ADR 0018).

Loads are started through the API (ADR 0018):

- ``POST /api/v1/reference/loads/{layer}`` loads every enabled state of a layer.
- ``POST /api/v1/reference/loads/{layer}/{state}`` loads one state.

Download links come from ``public.sources``, one row per layer and state (ADR 0021).

Every layer goes through the same four steps:

1. Download the source file with ``httpx``.
2. Stage it as-is into the ``staging`` schema with ``ogr2ogr``, reprojected to EPSG:4326.
3. Swap it into the final table in one transaction. Users see the previous data until
   the transaction commits.
4. Record the run in ``public.load_runs``.

A layer's loader in ``src/reference/loaders/`` only supplies what is different about
it: a ``Loader`` that turns a ``public.sources`` row into a ``LayerSource``.
"""

import os
import shutil
import subprocess
import tempfile
import zipfile
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

import httpx
import structlog
from geoalchemy2 import Geometry
from sqlalchemy import Engine, MetaData, Table, delete, func, insert, literal, select, update
from sqlalchemy.orm import Session

from src.core.config import settings
from src.core.database import ReferenceBase
from src.reference.models.public import LoadRun, Source

log = structlog.get_logger(__name__)

STAGING_SCHEMA = "staging"

# Connect and read timeouts. Read is per chunk, so large downloads are not cut off.
DOWNLOAD_TIMEOUT = httpx.Timeout(60.0)


class LoadError(Exception):
    """A load failed for a reason the maintainer has to look at."""


@dataclass(frozen=True)
class LayerSource:
    """One layer's source for one state.

    Attributes:
        model: Final table model, such as ``Wetland``.
        state: Two-letter state code, such as ``TX``.
        url: Download link for the source file.
        file_suffix: Suffix of the dataset inside a downloaded zip, such as ``.gpkg``.
        columns: Final column name to staged source field name. ``ogr2ogr`` lowercases
            source field names when it stages them. ``state`` and ``geom`` are filled
            by the framework and are not listed here.
        source_layer: Layer name inside the downloaded file, such as ``TX_Wetlands``.
            ``None`` stages the file's only layer, as with a shapefile.
        keep: Staged source field name to the values to load. Staged rows with any other
            value in that field are left out. Empty loads every row.
    """

    model: type[ReferenceBase]
    state: str
    url: str
    file_suffix: str
    columns: dict[str, str]
    source_layer: str | None = None
    keep: dict[str, tuple[str, ...]] = field(default_factory=dict)


@dataclass(frozen=True)
class Loader:
    """One layer's loader.

    Attributes:
        model: Final table model, such as ``Wetland``.
        layer_source: Builds the ``LayerSource`` for one ``public.sources`` row.
    """

    model: type[ReferenceBase]
    layer_source: Callable[[Source], LayerSource]

    @property
    def layer(self) -> str:
        """The layer name used in ``public.sources``, such as ``hydro.wetlands``."""
        return final_table(self.model).fullname


def enabled_sources(engine: Engine, layer: str, state: str | None = None) -> list[Source]:
    """Return a layer's enabled ``public.sources`` rows, ordered by state.

    Args:
        engine: Engine for the reference database.
        layer: Layer name, such as ``hydro.wetlands``.
        state: Two-letter state code to return only that state's row. ``None`` returns
            every enabled state.

    Returns:
        The enabled sources.
    """
    query = (
        select(Source)
        .where(Source.layer == layer, Source.is_enabled.is_(True))
        .order_by(Source.state)
    )
    if state is not None:
        query = query.where(Source.state == state)
    with Session(engine) as session:
        return list(session.scalars(query))


def run_loads(engine: Engine, sources: Sequence[LayerSource]) -> None:
    """Load each source in order, one state at a time.

    Args:
        engine: Engine for the reference database.
        sources: The layer and state of each load.

    Raises:
        LoadError: A load failed. It is recorded as ``failed``, and the states after it
            are not loaded.
    """
    for source in sources:
        run_load(engine, source)


def run_load(engine: Engine, source: LayerSource) -> None:
    """Download, stage, swap, and record one layer for one state.

    Args:
        engine: Engine for the reference database.
        source: The layer and state to load.

    Raises:
        LoadError: The download, staging, or swap failed. The run is recorded as
            ``failed`` and the final table is unchanged.
    """
    table = final_table(source.model)
    run_id = start_run(engine, table.fullname, source.state)
    run_log = log.bind(layer=table.fullname, state=source.state, run_id=run_id)
    run_log.info("load_started", url=source.url)

    try:
        settings.reference_work_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(
            prefix="reference-load-", dir=settings.reference_work_dir
        ) as work_dir:
            dataset, source_version = download(source.url, Path(work_dir), source.file_suffix)
            stage(engine, source, table, dataset)
        rows_loaded = swap(engine, source, table)
    except BaseException as error:
        # BaseException so Ctrl+C is recorded too, instead of leaving a 'running' row.
        finish_run(engine, run_id, status="failed", error=str(error) or repr(error))
        run_log.exception("load_failed")
        raise

    finish_run(
        engine,
        run_id,
        status="succeeded",
        source_version=source_version,
        rows_loaded=rows_loaded,
    )
    run_log.info("load_succeeded", rows_loaded=rows_loaded, source_version=source_version)


def final_table(model: type[ReferenceBase]) -> Table:
    """Return the ``Table`` behind a reference model."""
    table = model.__table__
    if not isinstance(table, Table):
        raise TypeError(f"{model.__name__} is not mapped to a single table")
    return table


def download(url: str, work_dir: Path, file_suffix: str) -> tuple[Path, str | None]:
    """Download the source file and return the dataset path and source version.

    Args:
        url: Download link.
        work_dir: Temporary folder for the download.
        file_suffix: Suffix of the dataset to find inside a zip, such as ``.gpkg``.

    Returns:
        Path to the dataset, and the source's ``Last-Modified`` (or ``ETag``) header.

    Raises:
        LoadError: The link did not return the file, or the zip has no matching dataset.
    """
    downloaded = work_dir / "download"
    with httpx.stream("GET", url, follow_redirects=True, timeout=DOWNLOAD_TIMEOUT) as response:
        if response.is_error:
            raise LoadError(f"Download failed: HTTP {response.status_code} from {url}")
        source_version = response.headers.get("last-modified") or response.headers.get("etag")
        with downloaded.open("wb") as file:
            for chunk in response.iter_bytes():
                file.write(chunk)

    if not zipfile.is_zipfile(downloaded):
        return downloaded.rename(work_dir / f"download{file_suffix}"), source_version

    extracted = work_dir / "extracted"
    with zipfile.ZipFile(downloaded) as archive:
        archive.extractall(extracted)
    downloaded.unlink()

    matches = sorted(extracted.rglob(f"*{file_suffix}"))
    if len(matches) != 1:
        found = [path.name for path in matches]
        raise LoadError(f"Expected one {file_suffix} dataset in the download, found {found}")
    return matches[0], source_version


def stage(engine: Engine, source: LayerSource, table: Table, dataset: Path) -> None:
    """Copy the source layer into ``staging.<table>`` as-is, reprojected to EPSG:4326.

    Args:
        engine: Engine for the reference database.
        source: The layer being loaded.
        table: The final table; the staging table gets the same name.
        dataset: Path to the downloaded dataset.

    Raises:
        LoadError: ``ogr2ogr`` is missing or failed.
    """
    url = engine.url
    connection = (
        f"PG:host={url.host} port={url.port or 5432} dbname={url.database} user={url.username}"
    )
    layer = [] if source.source_layer is None else [source.source_layer]
    run_ogr2ogr(
        [
            "-f",
            "PostgreSQL",
            connection,
            str(dataset),
            *layer,
            "-nln",
            f"{STAGING_SCHEMA}.{table.name}",
            "-overwrite",
            "-t_srs",
            "EPSG:4326",
            "-nlt",
            final_geometry_type(table),
            "-lco",
            "GEOMETRY_NAME=geom",
            "-lco",
            "SPATIAL_INDEX=NONE",
        ],
        password=url.password,
    )


def run_ogr2ogr(arguments: list[str], *, password: str | None = None) -> None:
    """Run GDAL's ``ogr2ogr`` with the given arguments.

    Args:
        arguments: Everything after ``ogr2ogr`` on the command line.
        password: PostgreSQL password, passed in the environment so it never shows in
            the process list.

    Raises:
        LoadError: ``ogr2ogr`` is not installed or exited with an error.
    """
    ogr2ogr = shutil.which("ogr2ogr")
    if ogr2ogr is None:
        raise LoadError("ogr2ogr was not found. Install GDAL on this machine.")

    environment = {**os.environ, "PGPASSWORD": password or ""}
    result = subprocess.run([ogr2ogr, *arguments], env=environment, capture_output=True, text=True)  # noqa: S603
    if result.returncode != 0:
        raise LoadError(f"ogr2ogr failed: {result.stderr.strip()}")


def final_geometry_type(table: Table) -> str:
    """Return the final table's geometry type, such as ``MULTIPOLYGON``, for ``ogr2ogr -nlt``."""
    geometry = table.c.geom.type
    if not isinstance(geometry, Geometry) or geometry.geometry_type is None:
        raise TypeError(f"{table.fullname}.geom is not a typed PostGIS geometry column")
    return geometry.geometry_type


def swap(engine: Engine, source: LayerSource, table: Table) -> int:
    """Replace the state's rows in the final table with the staged rows, in one transaction.

    Args:
        engine: Engine for the reference database.
        source: The layer being loaded.
        table: The final table.

    Returns:
        Number of rows loaded.

    Raises:
        LoadError: The staged source is missing an expected field.
    """
    with engine.begin() as connection:
        staged = Table(table.name, MetaData(), schema=STAGING_SCHEMA, autoload_with=connection)

        expected = [*source.columns.values(), *source.keep, "geom"]
        missing = [name for name in expected if name not in staged.c]
        if missing:
            raise LoadError(
                f"Staged source for {table.fullname} is missing expected fields {missing}. "
                f"The source may have changed; the final table was not touched."
            )

        kept = (staged.c[name].in_(values) for name, values in source.keep.items())
        rows = select(
            literal(source.state),
            *(staged.c[name] for name in source.columns.values()),
            staged.c.geom,
        ).where(*kept)

        in_state = table.c.state == source.state
        connection.execute(delete(table).where(in_state))
        connection.execute(insert(table).from_select(["state", *source.columns, "geom"], rows))
        rows_loaded = connection.scalar(select(func.count()).select_from(table).where(in_state))
        staged.drop(connection)
        return rows_loaded or 0


def start_run(engine: Engine, layer: str, state: str) -> int:
    """Record a ``running`` load and return its id. Committed right away so it's visible."""
    with Session(engine) as session, session.begin():
        run = LoadRun(layer=layer, state=state, status="running")
        session.add(run)
        session.flush()
        return run.id


def finish_run(
    engine: Engine,
    run_id: int,
    *,
    status: str,
    source_version: str | None = None,
    rows_loaded: int | None = None,
    error: str | None = None,
) -> None:
    """Record how a load ended."""
    with engine.begin() as connection:
        connection.execute(
            update(LoadRun)
            .where(LoadRun.id == run_id)
            .values(
                status=status,
                source_version=source_version,
                rows_loaded=rows_loaded,
                error=error,
                finished_at=func.now(),
            )
        )

"""The reference loader (ADR 0018).

There is one loader for every layer. Everything that differs between layers is data in
``public.sources``: the link, access type, format, layer name inside the file, field
mapping, rows to keep, and whether to cut the data at the state line.

A load is one layer for one state. It uses the state source if there is one, otherwise
the federal source. ``{state}`` and ``{fips}`` in a source's link, layer name, and keep
values are filled in for the state being loaded.

Each download link goes through the same steps, once per link:

1. Download the file with ``httpx`` into the kept downloads folder, or use the file
   Check link already downloaded there. A web service is read directly instead.
2. Stage it as-is into the ``staging`` schema with ``ogr2ogr``, reprojected to EPSG:4326.
   A load cut at the state line stages only what's inside the state's rectangle.
3. Swap each state into the final table in its own transaction. Users see the previous
   data until that transaction commits.
4. Record each state's run in ``public.load_runs``, with its stage (downloading, copying,
   swapping) and download progress while it runs, for the admin page.
5. Delete the kept download once every state is swapped in. After a failed swap it stays,
   for the next load to use.

A change check asks each loaded layer's source whether its file changed since the last
load, without downloading it, and records the answer in ``public.source_checks``.
"""

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import time
import zipfile
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
import structlog
from geoalchemy2 import Geometry
from sqlalchemy import (
    ColumnElement,
    Engine,
    MetaData,
    Select,
    Table,
    delete,
    func,
    insert,
    literal,
    nulls_last,
    or_,
    select,
    update,
)
from sqlalchemy.dialects.postgresql import distinct_on
from sqlalchemy.orm import Session

from src.core.config import settings
from src.reference.models import metadata
from src.reference.models.boundaries import State
from src.reference.models.public import LoadRun, Source, SourceCheck
from src.reference.state_codes import STATE_FIPS

log = structlog.get_logger(__name__)

STAGING_SCHEMA = "staging"

# Connect and read timeouts. Read is per chunk, so large downloads are not cut off.
DOWNLOAD_TIMEOUT = httpx.Timeout(60.0)

# Downloads kept between Check link and the load, so a file is downloaded once. The load
# deletes a file after every state that uses it is swapped in.
DOWNLOADS_DIR = settings.reference_work_dir / "downloads"

# Seconds between download progress reports, so a large download isn't reported per chunk.
PROGRESS_INTERVAL = 1.0

# Reports how much of a download has arrived: bytes downloaded, then the total if known.
DownloadProgress = Callable[[int, int | None], None]

# Reports a link check's stage (``downloading`` or ``reading``) and, while downloading,
# the bytes downloaded and the total if known.
CheckProgress = Callable[[str, int | None, int | None], None]

# GDAL format name to the dataset's file suffix inside a downloaded zip.
DATASET_SUFFIXES = {
    "ESRI Shapefile": ".shp",
    "GPKG": ".gpkg",
    "OpenFileGDB": ".gdb",
    "GeoJSON": ".geojson",
}

# Final geometry type to the PostGIS dimension kept when a geometry is cut at a state line.
CLIP_DIMENSIONS = {"MULTIPOINT": 1, "MULTILINESTRING": 2, "MULTIPOLYGON": 3}

# Columns every layer table has that a source does not fill.
FRAMEWORK_COLUMNS = ("id", "state", "geom")


class LoadError(Exception):
    """A load failed for a reason the maintainer has to look at."""


@dataclass(frozen=True)
class Load:
    """One layer for one state, with its source filled in for that state.

    Attributes:
        table: The final table, such as ``boundaries.places``.
        state: Two-letter state code, such as ``TX``.
        url: The source link for this state.
        access_type: ``file`` or ``service``.
        format: GDAL format name, such as ``ESRI Shapefile``.
        source_layer: Layer name inside the dataset, or ``None`` for its only layer.
        field_mapping: Final column to provider field.
        keep: Provider field to the values to keep. Empty keeps every row.
        clip_to_state: Whether to cut the data at the state line.
    """

    table: Table
    state: str
    url: str
    access_type: str
    format: str
    source_layer: str | None
    field_mapping: dict[str, str]
    keep: dict[str, list[str]]
    clip_to_state: bool

    @property
    def layer(self) -> str:
        """The layer name, such as ``boundaries.places``."""
        return self.table.fullname


def fill(text: str, state: str) -> str:
    """Fill ``{state}`` and ``{fips}`` in a source value for one state.

    Args:
        text: A link, layer name, or keep value, such as ``tl_2026_{fips}_place.zip``.
        state: Two-letter state code, such as ``TX``.

    Returns:
        The value for that state, such as ``tl_2026_48_place.zip``.
    """
    return text.replace("{state}", state).replace("{fips}", STATE_FIPS[state])


def layer_table(layer: str) -> Table | None:
    """Return the final table for a layer name, or ``None`` if it isn't a layer.

    Args:
        layer: Layer name, such as ``boundaries.places``.

    Returns:
        The table, when it exists and has ``state`` and ``geom`` columns.
    """
    table = metadata.tables.get(layer)
    if table is None or "state" not in table.c or "geom" not in table.c:
        return None
    return table


def find_source(engine: Engine, layer: str, state: str) -> Source | None:
    """Return the enabled source a layer uses for a state.

    Args:
        engine: Engine for the reference database.
        layer: Layer name, such as ``hydro.wetlands``.
        state: Two-letter state code, such as ``TX``.

    Returns:
        The state source if there is one, otherwise the federal source, or ``None``.
    """
    query = (
        select(Source)
        .where(
            Source.layer == layer,
            Source.is_enabled.is_(True),
            or_(Source.state == state, Source.state.is_(None)),
        )
        .order_by(nulls_last(Source.state))
        .limit(1)
    )
    with Session(engine) as session:
        return session.scalar(query)


def plan_load(engine: Engine, layer: str, state: str) -> Load:
    """Build the load for one layer and state from its source.

    Args:
        engine: Engine for the reference database.
        layer: Layer name, such as ``boundaries.places``.
        state: Two-letter state code, such as ``TX``.

    Returns:
        The load, with ``{state}`` and ``{fips}`` filled in.

    Raises:
        LoadError: The layer or state is unknown, or the layer has no enabled source.
    """
    table = layer_table(layer)
    if table is None:
        raise LoadError(f"No layer named '{layer}'")
    if state not in STATE_FIPS:
        raise LoadError(f"Unknown state code '{state}'")
    source = find_source(engine, layer, state)
    if source is None:
        raise LoadError(f"No enabled source for {layer} in {state}")

    return Load(
        table=table,
        state=state,
        url=fill(source.download_url, state),
        access_type=source.access_type,
        format=source.format,
        source_layer=None if source.source_layer is None else fill(source.source_layer, state),
        field_mapping=source.field_mapping,
        keep={
            field: [fill(value, state) for value in values]
            for field, values in (source.keep or {}).items()
        },
        clip_to_state=source.clip_to_state,
    )


def run_loads(engine: Engine, loads: Sequence[Load]) -> None:
    """Run each load, downloading each link only once.

    Loads that share a link, such as several states from one national file, are loaded
    from a single download. Links are loaded in the order they first appear.

    Args:
        engine: Engine for the reference database.
        loads: The layer and state of each load.

    Raises:
        LoadError: A load failed. Its states are recorded as ``failed``, and the links
            after it are not loaded.
    """
    by_url: dict[str, list[Load]] = {}
    for load in loads:
        by_url.setdefault(load.url, []).append(load)
    for url, url_loads in by_url.items():
        run_download(engine, url, url_loads)


def run_download(engine: Engine, url: str, loads: Sequence[Load]) -> None:
    """Download one link, then stage, swap, and record each load that uses it.

    Each final table and source layer is staged once from the download, then swapped in
    one state at a time. Each state gets its own ``public.load_runs`` row.

    Args:
        engine: Engine for the reference database.
        url: The link the loads share.
        loads: The layer and state loads that use this link.

    Raises:
        LoadError: The download, staging, or a swap failed. Every state not yet loaded is
            recorded as ``failed``, and its final table rows are unchanged.
    """
    runs = [(load, start_run(engine, load.layer, load.state)) for load in loads]
    run_ids = [run_id for _, run_id in runs]
    pending = set(run_ids)
    url_log = log.bind(url=url, loads=[f"{load.layer}:{load.state}" for load in loads])
    url_log.info("load_started")
    staged_tables: set[str] = set()

    try:
        settings.reference_work_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(
            prefix="reference-load-", dir=settings.reference_work_dir
        ) as work_dir:
            set_stage(engine, run_ids, "downloading")

            def record_download(done: int, total: int | None) -> None:
                record_progress(engine, run_ids, done, total)

            dataset, source_version = open_dataset(loads[0], Path(work_dir), record_download)
            staged: dict[tuple[str, str | None], str] = {}
            for load, run_id in runs:
                key = (load.layer, load.source_layer)
                if key not in staged:
                    staged[key] = f"{load.table.schema}_{load.table.name}_{len(staged)}"
                    set_stage(engine, sorted(pending), "copying")
                    clipped_states = [
                        item.state
                        for item in loads
                        if item.clip_to_state and (item.layer, item.source_layer) == key
                    ]
                    extent = state_extent(engine, clipped_states) if clipped_states else None
                    stage(engine, load, dataset, staged[key], extent)
                    staged_tables.add(staged[key])
                set_stage(engine, [run_id], "swapping")
                rows_loaded = swap(engine, load, staged[key])
                finish_run(
                    engine,
                    run_id,
                    status="succeeded",
                    source_version=source_version,
                    rows_loaded=rows_loaded,
                )
                pending.discard(run_id)
                url_log.info(
                    "load_succeeded",
                    layer=load.layer,
                    state=load.state,
                    run_id=run_id,
                    rows_loaded=rows_loaded,
                    source_version=source_version,
                )
        # Every state that uses the file is swapped in, so it's no longer needed. After a
        # failed swap it stays, for the next load to use.
        delete_download(url)
    except BaseException as error:
        # BaseException so Ctrl+C is recorded too, instead of leaving 'running' rows.
        for run_id in pending:
            finish_run(engine, run_id, status="failed", error=str(error) or repr(error))
        url_log.exception("load_failed", failed_run_ids=sorted(pending))
        raise
    finally:
        drop_staged(engine, staged_tables)


def open_dataset(
    load: Load, work_dir: Path, on_progress: DownloadProgress | None = None
) -> tuple[str, str | None]:
    """Return what ``ogr2ogr`` reads for a load, downloading it first when it's a file.

    Args:
        load: The load being run.
        work_dir: Temporary folder for the download.
        on_progress: Called as the download arrives.

    Returns:
        The dataset path or service address, and the source version if known.

    Raises:
        LoadError: The download failed or holds no dataset of the source's format.
    """
    if load.access_type == "service":
        return load.url, None
    suffix = DATASET_SUFFIXES.get(load.format)
    if suffix is None:
        raise LoadError(f"Files in format '{load.format}' can't be loaded")
    downloaded, source_version = download(load.url, on_progress)
    return str(find_dataset(downloaded, work_dir, [suffix])), source_version


def kept_download(url: str) -> Path:
    """Return where a link's download is kept. The same link always gets the same file."""
    return DOWNLOADS_DIR / hashlib.sha256(url.encode()).hexdigest()


def download(url: str, on_progress: DownloadProgress | None = None) -> tuple[Path, str | None]:
    """Download a file into the kept downloads folder, or reuse it if it's already there.

    The file is written under a temporary name and renamed when it's complete, so a
    download that stops partway is never reused.

    Args:
        url: Download link.
        on_progress: Called about once a second as the download arrives, and once when
            it's complete. A kept file reports as already complete.

    Returns:
        Path to the kept file, and the source's ``Last-Modified`` (or ``ETag``) header.

    Raises:
        LoadError: The link did not return the file.
    """
    kept = kept_download(url)
    version_file = kept.with_suffix(".version")
    if kept.exists():
        if on_progress is not None:
            size = kept.stat().st_size
            on_progress(size, size)
        version = version_file.read_text() if version_file.exists() else ""
        return kept, version or None

    DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)
    partial = kept.with_suffix(".part")
    try:
        with httpx.stream("GET", url, follow_redirects=True, timeout=DOWNLOAD_TIMEOUT) as response:
            if response.is_error:
                raise LoadError(f"Download failed: HTTP {response.status_code} from {url}")
            source_version = response.headers.get("last-modified") or response.headers.get("etag")
            length = response.headers.get("content-length")
            total = int(length) if length is not None and length.isdigit() else None
            reported_at = time.monotonic()
            with partial.open("wb") as file:
                for chunk in response.iter_raw():
                    file.write(chunk)
                    if on_progress is not None and (
                        time.monotonic() - reported_at >= PROGRESS_INTERVAL
                    ):
                        on_progress(response.num_bytes_downloaded, total)
                        reported_at = time.monotonic()
            if on_progress is not None:
                on_progress(response.num_bytes_downloaded, total)
    except BaseException:
        partial.unlink(missing_ok=True)
        raise

    version_file.write_text(source_version or "")
    partial.rename(kept)
    return kept, source_version


def delete_download(url: str) -> None:
    """Delete a link's kept download, if there is one."""
    kept = kept_download(url)
    kept.unlink(missing_ok=True)
    kept.with_suffix(".version").unlink(missing_ok=True)


def find_dataset(downloaded: Path, work_dir: Path, suffixes: Sequence[str]) -> Path:
    """Return the dataset in a download, unzipping it first when it's a zip.

    The kept download is left as it is: a zip is unzipped into ``work_dir``, and any
    other file is linked there under the dataset's suffix.

    Args:
        downloaded: The kept download.
        work_dir: Temporary folder to unzip or link into.
        suffixes: Dataset suffixes to look for, in order, such as ``[".gpkg"]``.

    Returns:
        Path to the one dataset with the first suffix found.

    Raises:
        LoadError: No dataset, or more than one, has that suffix.
    """
    if not zipfile.is_zipfile(downloaded):
        linked = work_dir / f"dataset{suffixes[0]}"
        linked.symlink_to(downloaded)
        return linked

    extracted = work_dir / "extracted"
    with zipfile.ZipFile(downloaded) as archive:
        archive.extractall(extracted)

    for suffix in suffixes:
        matches = sorted(extracted.rglob(f"*{suffix}"))
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            found = [path.name for path in matches]
            raise LoadError(f"Expected one {suffix} dataset in the download, found {found}")
    raise LoadError(f"No {' or '.join(suffixes)} dataset in the download")


def stage(
    engine: Engine,
    load: Load,
    dataset: str,
    staged_name: str,
    extent: tuple[float, float, float, float] | None = None,
) -> None:
    """Copy the source layer into ``staging.<staged_name>`` as-is, reprojected to EPSG:4326.

    Args:
        engine: Engine for the reference database.
        load: The load being run.
        dataset: The dataset path or service address.
        staged_name: Name of the staging table.
        extent: West, south, east, and north edges in EPSG:4326. Only features inside
            this rectangle are staged. ``None`` stages every feature.

    Raises:
        LoadError: ``ogr2ogr`` is missing or failed.
    """
    url = engine.url
    connection = (
        f"PG:host={url.host} port={url.port or 5432} dbname={url.database} user={url.username}"
    )
    source_layer = [] if load.source_layer is None else [load.source_layer]
    inside = [] if extent is None else ["-spat", *map(str, extent), "-spat_srs", "EPSG:4326"]
    run_gdal(
        "ogr2ogr",
        [
            "-f",
            "PostgreSQL",
            connection,
            dataset,
            *source_layer,
            "-nln",
            f"{STAGING_SCHEMA}.{staged_name}",
            "-overwrite",
            "-t_srs",
            "EPSG:4326",
            "-nlt",
            final_geometry_type(load.table),
            "-lco",
            "GEOMETRY_NAME=geom",
            "-lco",
            "SPATIAL_INDEX=NONE",
            *inside,
        ],
        password=url.password,
    )


def run_gdal(tool: str, arguments: list[str], *, password: str | None = None) -> str:
    """Run a GDAL command-line tool and return what it printed.

    Args:
        tool: ``ogr2ogr`` or ``ogrinfo``.
        arguments: Everything after the tool name on the command line.
        password: PostgreSQL password, passed in the environment so it never shows in
            the process list.

    Returns:
        The tool's standard output.

    Raises:
        LoadError: The tool is not installed or exited with an error.
    """
    executable = shutil.which(tool)
    if executable is None:
        raise LoadError(f"{tool} was not found. Install GDAL on this machine.")

    environment = {**os.environ, "PGPASSWORD": password or ""}
    result = subprocess.run(  # noqa: S603
        [executable, *arguments], env=environment, capture_output=True, text=True
    )
    if result.returncode != 0:
        raise LoadError(f"{tool} failed: {result.stderr.strip()}")
    return result.stdout


def final_geometry_type(table: Table) -> str:
    """Return the final table's geometry type, such as ``MULTIPOLYGON``."""
    geometry = table.c.geom.type
    if not isinstance(geometry, Geometry) or geometry.geometry_type is None:
        raise TypeError(f"{table.fullname}.geom is not a typed PostGIS geometry column")
    return geometry.geometry_type


def state_extent(engine: Engine, states: Sequence[str]) -> tuple[float, float, float, float] | None:
    """Return the rectangle around the given states' outlines, from ``boundaries.states``.

    Args:
        engine: Engine for the reference database.
        states: Two-letter state codes.

    Returns:
        West, south, east, and north edges in EPSG:4326, or ``None`` when none of the
        states' outlines are loaded.
    """
    extent = func.ST_Extent(State.geom)
    query = select(
        func.ST_XMin(extent), func.ST_YMin(extent), func.ST_XMax(extent), func.ST_YMax(extent)
    ).where(State.state.in_(states))
    with engine.connect() as connection:
        west, south, east, north = connection.execute(query).one()
    if west is None:
        return None
    return float(west), float(south), float(east), float(north)


def swap(engine: Engine, load: Load, staged_name: str) -> int:
    """Replace the state's rows in the final table with the staged rows, in one transaction.

    The staged table is kept, so other states can be swapped in from it.

    Args:
        engine: Engine for the reference database.
        load: The load being run.
        staged_name: Name of the staging table.

    Returns:
        Number of rows loaded.

    Raises:
        LoadError: The staged source is missing a mapped field, or the state's outline
            is needed and not loaded.
    """
    table = load.table
    # ogr2ogr lowercases field names when it stages them.
    mapping = {column: field.lower() for column, field in load.field_mapping.items()}
    keep = {field.lower(): values for field, values in load.keep.items()}

    with engine.begin() as connection:
        staged = Table(staged_name, MetaData(), schema=STAGING_SCHEMA, autoload_with=connection)

        missing = [name for name in [*mapping.values(), *keep] if name not in staged.c]
        if missing:
            raise LoadError(
                f"The source for {load.layer} has no fields {missing}. "
                f"The provider may have renamed them; the final table was not touched."
            )

        kept = [staged.c[field].in_(values) for field, values in keep.items()]
        columns = [staged.c[field] for field in mapping.values()]
        if load.clip_to_state:
            has_outline = connection.scalar(
                select(func.count()).select_from(State).where(State.state == load.state)
            )
            if not has_outline:
                raise LoadError(
                    f"{load.layer} is cut at the state line. Load boundaries.states for "
                    f"{load.state} first."
                )
            rows = clipped_rows(load, staged, columns, kept)
        else:
            rows = select(literal(load.state), *columns, staged.c.geom).where(*kept)

        in_state = table.c.state == load.state
        connection.execute(delete(table).where(in_state))
        connection.execute(insert(table).from_select(["state", *mapping, "geom"], rows))
        rows_loaded = connection.scalar(select(func.count()).select_from(table).where(in_state))
        return rows_loaded or 0


def clipped_rows(
    load: Load,
    staged: Table,
    columns: Sequence[Any],
    kept: Sequence[ColumnElement[bool]],
) -> Select[*tuple[Any, ...]]:
    """Select the staged rows cut at the state line, using ``boundaries.states``.

    Args:
        load: The load being run.
        staged: The staging table.
        columns: The staged fields, in final column order.
        kept: Conditions for the rows to keep.

    Returns:
        The state code, mapped fields, and cut geometry of each row inside the state.
    """
    outline = State.__table__
    geometry_type = final_geometry_type(load.table)
    cut: ColumnElement[Any]
    if geometry_type in CLIP_DIMENSIONS:
        cut = func.ST_Multi(
            func.ST_CollectionExtract(
                func.ST_Intersection(staged.c.geom, outline.c.geom),
                CLIP_DIMENSIONS[geometry_type],
            )
        )
    elif geometry_type == "POINT":
        cut = staged.c.geom
    else:
        cut = func.ST_Intersection(staged.c.geom, outline.c.geom)

    inside = (
        select(literal(load.state).label("state"), *columns, cut.label("geom"))
        .select_from(staged.join(outline, func.ST_Intersects(staged.c.geom, outline.c.geom)))
        .where(outline.c.state == load.state, *kept)
        .subquery()
    )
    return select(*inside.c).where(func.ST_IsEmpty(inside.c.geom).is_(False))


def drop_staged(engine: Engine, staged_names: set[str]) -> None:
    """Drop the given staging tables.

    Args:
        engine: Engine for the reference database.
        staged_names: Names of the staging tables.
    """
    with engine.begin() as connection:
        for name in staged_names:
            Table(name, MetaData(), schema=STAGING_SCHEMA).drop(connection, checkfirst=True)


def start_run(engine: Engine, layer: str, state: str) -> int:
    """Record a ``running`` load and return its id. Committed right away so it's visible."""
    with Session(engine) as session, session.begin():
        run = LoadRun(layer=layer, state=state, status="running")
        session.add(run)
        session.flush()
        return run.id


def set_stage(engine: Engine, run_ids: Sequence[int], stage_name: str) -> None:
    """Record the stage the given running loads are in, for the admin page."""
    with engine.begin() as connection:
        connection.execute(update(LoadRun).where(LoadRun.id.in_(run_ids)).values(stage=stage_name))


def record_progress(engine: Engine, run_ids: Sequence[int], done: int, total: int | None) -> None:
    """Record how much of the download the given loads share has arrived."""
    with engine.begin() as connection:
        connection.execute(
            update(LoadRun)
            .where(LoadRun.id.in_(run_ids))
            .values(bytes_downloaded=done, bytes_total=total)
        )


def fail_interrupted_runs(engine: Engine) -> int:
    """Record loads still ``running`` as failed. Run when the API starts.

    A load runs inside the API, so one still ``running`` when the API starts was stopped
    partway by the API stopping. Its final table rows were not changed.

    Args:
        engine: Engine for the reference database.

    Returns:
        How many loads were recorded as failed.
    """
    with engine.begin() as connection:
        result = connection.execute(
            update(LoadRun)
            .where(LoadRun.status == "running")
            .values(
                status="failed",
                stage=None,
                error="The API restarted during this load.",
                finished_at=func.now(),
            )
        )
    if result.rowcount:
        log.warning("interrupted_loads_failed", count=result.rowcount)
    return result.rowcount


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
                stage=None,
                source_version=source_version,
                rows_loaded=rows_loaded,
                error=error,
                finished_at=func.now(),
            )
        )


@dataclass(frozen=True)
class SourceLayer:
    """One layer found inside a dataset.

    Attributes:
        name: The layer's name, such as ``TX_Wetlands``.
        fields: The layer's field names, as the provider spells them.
    """

    name: str
    fields: list[str]


@dataclass(frozen=True)
class CheckedLink:
    """What a source link holds, and how it matches a layer's columns.

    Attributes:
        format: GDAL format name, such as ``GPKG``.
        layers: Every layer in the dataset.
        source_layer: The layer to load, as a pattern with ``{state}`` when the current
            source uses one, or ``None`` when it can't be picked.
        field_mapping: Final column to the matched provider field, or ``None`` when no
            field matched.
    """

    format: str
    layers: list[SourceLayer]
    source_layer: str | None
    field_mapping: dict[str, str | None]


def check_link(
    engine: Engine,
    layer: str,
    state: str,
    url: str,
    access_type: str,
    *,
    progress: CheckProgress | None = None,
) -> CheckedLink:
    """Open a source link with ``ogrinfo`` and match its fields to a layer's columns.

    A file link is downloaded into the kept downloads folder, where the load finds it.
    Fields are matched to the layer's current source first, then by the same name as the
    column, ignoring case.

    Args:
        engine: Engine for the reference database.
        layer: Layer name, such as ``boundaries.places``.
        state: Two-letter state code used to fill ``{state}`` and ``{fips}``.
        url: The link, which may hold ``{state}`` and ``{fips}``.
        access_type: ``file`` or ``service``.
        progress: Called with the download's progress, then with ``reading`` while the
            fields are read.

    Returns:
        The format, layers, and matched fields.

    Raises:
        LoadError: The layer or state is unknown, or the link can't be opened.
    """
    table = layer_table(layer)
    if table is None:
        raise LoadError(f"No layer named '{layer}'")
    if state not in STATE_FIPS:
        raise LoadError(f"Unknown state code '{state}'")

    filled_url = fill(url, state)
    settings.reference_work_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix="reference-check-", dir=settings.reference_work_dir
    ) as work_dir:
        if access_type == "service":
            dataset = filled_url
        else:

            def report_download(done: int, total: int | None) -> None:
                if progress is not None:
                    progress("downloading", done, total)

            downloaded, _ = download(filled_url, report_download)
            dataset = str(find_dataset(downloaded, Path(work_dir), list(DATASET_SUFFIXES.values())))
        if progress is not None:
            progress("reading", None, None)
        info: dict[str, Any] = json.loads(run_gdal("ogrinfo", ["-json", "-so", "-al", dataset]))

    layers = [
        SourceLayer(name=item["name"], fields=[field["name"] for field in item.get("fields", [])])
        for item in info.get("layers", [])
    ]
    current = find_source(engine, layer, state)
    chosen = pick_layer(layers, current, state)
    fields = [] if chosen is None else chosen.fields
    columns = [column.name for column in table.c if column.name not in FRAMEWORK_COLUMNS]
    current_mapping = {} if current is None else current.field_mapping

    field_mapping: dict[str, str | None] = {}
    for column in columns:
        by_name = {field.lower(): field for field in fields}
        previous = current_mapping.get(column)
        if previous is not None and previous.lower() in by_name:
            field_mapping[column] = by_name[previous.lower()]
        else:
            field_mapping[column] = by_name.get(column.lower())

    source_layer: str | None = None
    if chosen is not None and len(layers) > 1:
        pattern = None if current is None else current.source_layer
        source_layer = pattern if pattern and fill(pattern, state) == chosen.name else chosen.name

    return CheckedLink(
        format=info.get("driverShortName", ""),
        layers=layers,
        source_layer=source_layer,
        field_mapping=field_mapping,
    )


def pick_layer(layers: list[SourceLayer], current: Source | None, state: str) -> SourceLayer | None:
    """Pick the layer to load: the only one, or the one the current source names.

    Args:
        layers: Every layer in the dataset.
        current: The layer's current source, if any.
        state: Two-letter state code used to fill the current source's layer name.

    Returns:
        The layer, or ``None`` when it can't be picked.
    """
    if len(layers) == 1:
        return layers[0]
    if current is None or current.source_layer is None:
        return None
    wanted = fill(current.source_layer, state)
    return next((item for item in layers if item.name == wanted), None)


def current_version(url: str) -> tuple[str | None, str | None]:
    """Ask a link for its current version without downloading the file.

    Only the response headers are read; the file itself is not downloaded.

    Args:
        url: Download link.

    Returns:
        The ``Last-Modified`` (or ``ETag``) header, and the reason it couldn't be read.
    """
    try:
        with httpx.stream("GET", url, follow_redirects=True, timeout=DOWNLOAD_TIMEOUT) as response:
            if response.is_error:
                return None, f"HTTP {response.status_code} from {url}"
            return response.headers.get("last-modified") or response.headers.get("etag"), None
    except httpx.HTTPError as error:
        return None, str(error) or repr(error)


def check_sources(engine: Engine) -> None:
    """Ask each loaded layer's source whether its file changed since the last load.

    Every layer and state with a successful load is checked against the source it would
    load from now. A link is asked once, even when several states share it. Each answer
    is recorded in ``public.source_checks``. Web services have no file version, so they
    are not checked.

    Args:
        engine: Engine for the reference database.
    """
    query = (
        select(LoadRun)
        .where(LoadRun.status == "succeeded")
        .ext(distinct_on(LoadRun.layer, LoadRun.state))
        .order_by(LoadRun.layer, LoadRun.state, LoadRun.started_at.desc())
    )
    with Session(engine) as session:
        loaded = [(run.layer, run.state, run.source_version) for run in session.scalars(query)]

    versions: dict[str, tuple[str | None, str | None]] = {}
    checks: list[dict[str, Any]] = []
    for layer, state, loaded_version in loaded:
        source = find_source(engine, layer, state)
        if source is None or source.access_type == "service":
            continue
        url = fill(source.download_url, state)
        if url not in versions:
            versions[url] = current_version(url)
        version, error = versions[url]
        checks.append(
            {
                "layer": layer,
                "state": state,
                "source_version": version,
                "update_available": version is not None and version != loaded_version,
                "error": error,
            }
        )

    if checks:
        with engine.begin() as connection:
            connection.execute(insert(SourceCheck), checks)
    log.info(
        "sources_checked",
        checked=len(checks),
        updates=sum(check["update_available"] for check in checks),
        errors=sum(check["error"] is not None for check in checks),
    )

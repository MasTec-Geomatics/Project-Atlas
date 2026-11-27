"""Reference database endpoints, used by the admin page.

- ``/states``: every state's code and full name, for the **Add a state** box.
- ``/layers``: every layer, one column each in the **Load** table.
- ``/loads``: load a list of layer and state pairs, the admin page's **Load** button, and
  read the last load of each layer and state.
- ``/sources``: list, add, and edit sources.
- ``/sources/check``: open a link and match its fields to a layer, before saving. The
  answer streams back as the link downloads and unzips, so the page can show how far
  along it is.
- ``/sources/checks``: check every loaded layer's source for a newer file, the **Check for
  updates** button and the weekly scheduled job, and read what the last check found. The
  check streams back each source as it's checked, so the page can show how far along it is.
"""

import queue
import threading
from collections.abc import Callable, Iterator, Sequence
from datetime import datetime
from typing import Annotated, Any, Literal

import httpx
import structlog
from fastapi import APIRouter, BackgroundTasks, Body, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Engine, func, select
from sqlalchemy.dialects.postgresql import distinct_on
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from src.core.database import reference_engine
from src.reference.load import (
    CheckedLink,
    Load,
    LoadError,
    check_link,
    check_sources,
    layer_table,
    plan_load,
    run_loads,
)
from src.reference.models import metadata
from src.reference.models.public import LoadRun, Source, SourceCheck
from src.reference.state_codes import STATE_FIPS, STATE_NAMES

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/reference", tags=["reference"])

STATE_PATTERN = r"^[A-Z]{2}$"
URL_PATTERN = r"^https?://"
ACCESS_TYPE_PATTERN = r"^(file|service)$"


class LoadRequest(BaseModel):
    """One layer and state to load, one checked box on the admin page.

    Attributes:
        layer: Layer name, such as ``boundaries.places``.
        state: Two-letter state code, such as ``TX``.
    """

    layer: str
    state: str = Field(pattern=STATE_PATTERN)


class StateRead(BaseModel):
    """A state, searchable by code or full name.

    Attributes:
        code: Two-letter state code, such as ``NC``.
        name: Full name, such as ``North Carolina``.
    """

    code: str
    name: str


class LayerRead(BaseModel):
    """A layer, with the names the admin page shows.

    Attributes:
        name: Table name, such as ``hydro.wetlands``. The page sends this to load it.
        title: Readable name, such as ``Wetlands``.
        group: Readable name of the layer's schema, such as ``Water``.
    """

    name: str
    title: str
    group: str


class LoadRead(BaseModel):
    """The last load of one layer and state.

    Attributes:
        layer: Layer name, such as ``hydro.wetlands``.
        state: Two-letter state code, such as ``TX``.
        status: ``running``, ``succeeded``, or ``failed``.
        stage: While running: ``downloading``, ``unzipping``, ``copying``, or ``swapping``.
        progress_done: How far along the stage is: bytes while downloading or unzipping,
            percent while copying.
        progress_total: The stage's total, in the same units. Empty while downloading
            when the source doesn't say the file's size, and while swapping.
        rows_loaded: Rows in the layer for the state after the load, once it succeeded.
        source_version: The source's version or last-updated date, once it succeeded.
        error: Why the load failed.
        started_at: When the load started.
        finished_at: When the load ended, or ``None`` while it's running.
    """

    model_config = ConfigDict(from_attributes=True)

    layer: str
    state: str
    status: str
    stage: str | None
    progress_done: int | None
    progress_total: int | None
    rows_loaded: int | None
    source_version: str | None
    error: str | None
    started_at: datetime
    finished_at: datetime | None


class LoadsStarted(BaseModel):
    """Response when loads have been started.

    Attributes:
        loads: The layer and state pairs being loaded.
    """

    loads: list[LoadRequest]


class SourceCreate(BaseModel):
    """A new source, usually a state source from the **Add source** form.

    Attributes:
        layer: Layer name, such as ``hydro.wetlands``.
        state: Two-letter state code, or ``None`` for a federal source.
        download_url: Link, which may hold ``{state}`` and ``{fips}``.
        access_type: ``file`` or ``service``.
        format: GDAL format name, such as ``GPKG``.
        source_layer: Layer name inside the dataset, or ``None`` for its only layer.
        field_mapping: Final column to provider field.
        keep: Provider field to the values to keep, or ``None`` to keep every row.
        clip_to_state: Whether to cut the data at the state line.
        license: Source license.
        attribution: Required attribution text.
        is_enabled: Whether loads use this source.
    """

    layer: str
    state: str | None = Field(default=None, pattern=STATE_PATTERN)
    download_url: str = Field(pattern=URL_PATTERN)
    access_type: str = Field(pattern=ACCESS_TYPE_PATTERN)
    format: str = Field(min_length=1)
    source_layer: str | None = None
    field_mapping: dict[str, str] = Field(min_length=1)
    keep: dict[str, list[str]] | None = None
    clip_to_state: bool = False
    license: str | None = None
    attribution: str | None = None
    is_enabled: bool = True


class SourceUpdate(BaseModel):
    """Changes to a source from the **Edit source** form. Only the fields sent change.

    Attributes:
        download_url: Link, which may hold ``{state}`` and ``{fips}``.
        access_type: ``file`` or ``service``.
        format: GDAL format name, such as ``GPKG``.
        source_layer: Layer name inside the dataset, or ``None`` for its only layer.
        field_mapping: Final column to provider field.
        keep: Provider field to the values to keep, or ``None`` to keep every row.
        clip_to_state: Whether to cut the data at the state line.
        license: Source license.
        attribution: Required attribution text.
        is_enabled: Whether loads use this source.
    """

    download_url: str | None = Field(default=None, pattern=URL_PATTERN)
    access_type: str | None = Field(default=None, pattern=ACCESS_TYPE_PATTERN)
    format: str | None = Field(default=None, min_length=1)
    source_layer: str | None = None
    field_mapping: dict[str, str] | None = Field(default=None, min_length=1)
    keep: dict[str, list[str]] | None = None
    clip_to_state: bool | None = None
    license: str | None = None
    attribution: str | None = None
    is_enabled: bool | None = None


class SourceRead(BaseModel):
    """A ``public.sources`` row.

    Attributes:
        id: Row id.
        layer: Layer name, such as ``hydro.wetlands``.
        state: Two-letter state code, or ``None`` for a federal source.
        download_url: Link, which may hold ``{state}`` and ``{fips}``.
        access_type: ``file`` or ``service``.
        format: GDAL format name.
        source_layer: Layer name inside the dataset.
        field_mapping: Final column to provider field.
        keep: Provider field to the values to keep.
        clip_to_state: Whether the data is cut at the state line.
        license: Source license.
        attribution: Required attribution text.
        is_enabled: Whether loads use this source.
        updated_at: When the row was last changed.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    layer: str
    state: str | None
    download_url: str
    access_type: str
    format: str
    source_layer: str | None
    field_mapping: dict[str, str]
    keep: dict[str, list[str]] | None
    clip_to_state: bool
    license: str | None
    attribution: str | None
    is_enabled: bool
    updated_at: datetime


class CheckRequest(BaseModel):
    """A link to open before saving it, from the **Check link** button.

    Attributes:
        layer: Layer name, such as ``boundaries.places``.
        state: Two-letter state code used to fill ``{state}`` and ``{fips}``.
        download_url: Link, which may hold ``{state}`` and ``{fips}``.
        access_type: ``file`` or ``service``.
    """

    layer: str
    state: str = Field(pattern=STATE_PATTERN)
    download_url: str = Field(pattern=URL_PATTERN)
    access_type: str = Field(default="file", pattern=ACCESS_TYPE_PATTERN)


class CheckedLayer(BaseModel):
    """One layer found in the link.

    Attributes:
        name: The layer's name.
        fields: The layer's field names.
    """

    name: str
    fields: list[str]


class CheckResult(BaseModel):
    """What the link holds and how its fields match the layer's columns.

    Attributes:
        format: GDAL format name, such as ``GPKG``.
        layers: Every layer in the link.
        source_layer: The layer to load, or ``None`` when it can't be picked.
        field_mapping: Column to matched field, or ``None`` when nothing matched. The
            admin page shows a dropdown of the layer's fields for those.
    """

    format: str
    layers: list[CheckedLayer]
    source_layer: str | None
    field_mapping: dict[str, str | None]


class CheckEvent(BaseModel):
    """One line of a link check's streamed answer.

    The lines come in order: ``downloading`` (repeated as the file arrives) and
    ``unzipping`` (repeated as a zip is unzipped) for a file link, ``reading`` while the
    fields are read, then ``done`` with the result or ``failed`` with the reason.

    Attributes:
        stage: ``downloading``, ``unzipping``, ``reading``, ``done``, or ``failed``.
        progress_done: Bytes downloaded or unzipped so far.
        progress_total: The total bytes to download or unzip. Empty while downloading
            when the source doesn't say the file's size.
        result: What the link holds, when done.
        error: Why the link couldn't be checked, when failed.
    """

    stage: Literal["downloading", "unzipping", "reading", "done", "failed"]
    progress_done: int | None = None
    progress_total: int | None = None
    result: CheckResult | None = None
    error: str | None = None


class SourcesCheckEvent(BaseModel):
    """One line of a change check's streamed answer.

    The lines come in order: ``checking`` before each loaded layer and state is checked,
    then ``done`` with how many were checked, or ``failed`` with the reason.

    Attributes:
        stage: ``checking``, ``done``, or ``failed``.
        checked: How many layers and states are checked so far.
        total: How many layers and states there are to check.
        layer: The layer being checked, while checking.
        state: The state being checked, while checking.
        error: Why the check couldn't finish, when failed.
    """

    stage: Literal["checking", "done", "failed"]
    checked: int | None = None
    total: int | None = None
    layer: str | None = None
    state: str | None = None
    error: str | None = None


class SourceUpdateRead(BaseModel):
    """A loaded layer whose last change check found a newer file or an error.

    Attributes:
        layer: Layer name, such as ``hydro.wetlands``.
        state: Two-letter state code, such as ``TX``.
        last_pulled: When the layer last loaded successfully for the state.
        error: Why the source couldn't be checked, or ``None`` when it has a newer file.
    """

    layer: str
    state: str
    last_pulled: datetime | None
    error: str | None


class SourceChecksRead(BaseModel):
    """What the last change check found.

    Attributes:
        checked_at: When the last check ran, or ``None`` before the first one.
        updates: The loaded layers with a newer file or an error, by layer and state.
    """

    checked_at: datetime | None
    updates: list[SourceUpdateRead]


def get_reference_engine() -> Engine:
    """FastAPI dependency: the reference database engine. Tests override it."""
    return reference_engine


ReferenceEngine = Annotated[Engine, Depends(get_reference_engine)]


def run_background_loads(engine: Engine, loads: Sequence[Load]) -> None:
    """Run the requested loads in the background.

    Each load records its outcome in ``public.load_runs`` and logs any failure, so a
    failure is not raised again here.

    Args:
        engine: Engine for the reference database.
        loads: The loads to run, one per layer and state.
    """
    try:
        run_loads(engine, loads)
    except LoadError, httpx.HTTPError, OSError, SQLAlchemyError:
        log.warning(
            "background_load_failed",
            loads=[f"{load.layer}:{load.state}" for load in loads],
        )


def check_layer_and_state(layer: str, state: str | None) -> None:
    """Raise 422 when the layer or the state code is unknown.

    Args:
        layer: Layer name, such as ``hydro.wetlands``.
        state: Two-letter state code, or ``None``.

    Raises:
        HTTPException: 422 for an unknown layer or state code.
    """
    if layer_table(layer) is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"No layer named '{layer}'")
    if state is not None and state not in STATE_FIPS:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"Unknown state code '{state}'")


@router.get("/states")
def list_states() -> list[StateRead]:
    """List every state's code and full name, by name.

    Returns:
        The 50 states and the District of Columbia.
    """
    states = [StateRead(code=code, name=name) for code, name in STATE_NAMES.items()]
    return sorted(states, key=lambda state: state.name)


@router.get("/layers")
def list_layers() -> list[LayerRead]:
    """List every layer with its readable name and group.

    The readable names come from each model's ``info``.

    Returns:
        Every table with ``state`` and ``geom`` columns, in name order.
    """
    tables = [
        table for name, table in sorted(metadata.tables.items()) if layer_table(name) is not None
    ]
    return [
        LayerRead(name=table.fullname, title=table.info["title"], group=table.info["group"])
        for table in tables
    ]


@router.get("/loads")
def list_loads(engine: ReferenceEngine) -> list[LoadRead]:
    """List the last load of each layer and state.

    The admin page asks for this every few seconds while a load is running.

    Args:
        engine: Engine for the reference database.

    Returns:
        The newest ``public.load_runs`` row for each layer and state.
    """
    query = (
        select(LoadRun)
        .ext(distinct_on(LoadRun.layer, LoadRun.state))
        .order_by(LoadRun.layer, LoadRun.state, LoadRun.started_at.desc())
    )
    with Session(engine) as session:
        return [LoadRead.model_validate(run) for run in session.scalars(query)]


@router.post("/loads", status_code=status.HTTP_202_ACCEPTED)
def start_loads(
    body: Annotated[list[LoadRequest], Body(min_length=1)],
    background_tasks: BackgroundTasks,
    engine: ReferenceEngine,
) -> LoadsStarted:
    """Load a list of layer and state pairs. Returns right away; loads run in the background.

    Pairs that share a link, such as several states from one national file, are loaded
    from a single download. Results are recorded in ``public.load_runs``, one row per
    layer and state.

    Args:
        body: The layer and state pairs to load. Repeated pairs are loaded once.
        background_tasks: FastAPI's background task list.
        engine: Engine for the reference database.

    Returns:
        The layer and state pairs being loaded.

    Raises:
        HTTPException: 422 listing every pair that can't be loaded. Nothing is started
            when any pair has a problem.
    """
    pairs = list(dict.fromkeys((item.layer, item.state) for item in body))
    problems: list[str] = []
    loads: list[Load] = []

    for layer, state in pairs:
        try:
            loads.append(plan_load(engine, layer, state))
        except LoadError as error:
            problems.append(str(error))

    if problems:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, problems)

    background_tasks.add_task(run_background_loads, engine, loads)
    return LoadsStarted(loads=[LoadRequest(layer=layer, state=state) for layer, state in pairs])


@router.get("/sources")
def list_sources(engine: ReferenceEngine) -> list[SourceRead]:
    """List every source, by layer, federal first, then by state.

    Args:
        engine: Engine for the reference database.

    Returns:
        All ``public.sources`` rows.
    """
    query = select(Source).order_by(Source.layer, Source.state.nulls_first())
    with Session(engine) as session:
        return [SourceRead.model_validate(source) for source in session.scalars(query)]


@router.post("/sources", status_code=status.HTTP_201_CREATED)
def create_source(body: SourceCreate, engine: ReferenceEngine) -> SourceRead:
    """Add a source.

    Args:
        body: The new source.
        engine: Engine for the reference database.

    Returns:
        The saved source.

    Raises:
        HTTPException: 422 for an unknown layer or state code; 409 when the layer already
            has a source for that state, or already has a federal source.
    """
    check_layer_and_state(body.layer, body.state)

    with Session(engine) as session, session.begin():
        existing = session.scalar(
            select(Source.id).where(
                Source.layer == body.layer,
                Source.state.is_(None) if body.state is None else Source.state == body.state,
            )
        )
        if existing is not None:
            covers = "a federal source" if body.state is None else f"a source for {body.state}"
            raise HTTPException(status.HTTP_409_CONFLICT, f"{body.layer} already has {covers}")
        source = Source(**body.model_dump())
        session.add(source)
        session.flush()
        session.refresh(source)
        return SourceRead.model_validate(source)


@router.patch("/sources/{source_id}")
def update_source(source_id: int, body: SourceUpdate, engine: ReferenceEngine) -> SourceRead:
    """Change a source. Only the fields sent are changed.

    Args:
        source_id: The source's id.
        body: The fields to change.
        engine: Engine for the reference database.

    Returns:
        The updated source.

    Raises:
        HTTPException: 404 when there is no source with that id.
    """
    with Session(engine) as session, session.begin():
        source = session.get(Source, source_id)
        if source is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"No source with id {source_id}")
        for name, value in body.model_dump(exclude_unset=True).items():
            setattr(source, name, value)
        source.updated_at = func.now()
        session.flush()
        session.refresh(source)
        return SourceRead.model_validate(source)


def check_result(checked: CheckedLink) -> CheckResult:
    """Turn a checked link into the response the admin page reads."""
    return CheckResult(
        format=checked.format,
        layers=[CheckedLayer(name=item.name, fields=item.fields) for item in checked.layers],
        source_layer=checked.source_layer,
        field_mapping=checked.field_mapping,
    )


def stream_events(run: Callable[[Callable[[BaseModel], None]], None]) -> StreamingResponse:
    """Run a check in its own thread and stream each event it sends as one JSON line.

    Each line is sent as soon as the check sends it, instead of when the check ends.

    Args:
        run: The check. It sends each event by calling the function it's given.

    Returns:
        The streamed answer, as JSON lines (``application/x-ndjson``).
    """
    events: queue.Queue[BaseModel | None] = queue.Queue()

    def worker() -> None:
        try:
            run(events.put)
        finally:
            events.put(None)

    def lines() -> Iterator[str]:
        while (event := events.get()) is not None:
            yield event.model_dump_json(exclude_unset=True) + "\n"

    threading.Thread(target=worker, daemon=True).start()
    return StreamingResponse(lines(), media_type="application/x-ndjson")


def streamed(model: type[BaseModel]) -> dict[int | str, dict[str, Any]]:
    """The OpenAPI answer for a streamed endpoint: JSON lines, one ``model`` per line."""
    return {200: {"model": model, "content": {"application/x-ndjson": {}}}}


@router.post("/sources/check", response_class=StreamingResponse, responses=streamed(CheckEvent))
def check_source(body: CheckRequest, engine: ReferenceEngine) -> StreamingResponse:
    """Open a link and match its fields to the layer's columns, without saving anything.

    A file link is downloaded into the kept downloads folder, where the load finds it, so
    the file is downloaded only once. The answer streams back one JSON line at a time: the
    download's progress, then the unzip's, then reading, then the result or why it
    failed. Fields are matched to the layer's current source first, then by the same name
    as the column, ignoring case.

    Args:
        body: The link to check.
        engine: Engine for the reference database.

    Returns:
        The streamed answer, as JSON lines (``application/x-ndjson``).

    Raises:
        HTTPException: 422 for an unknown layer or state code, before anything streams.
    """
    check_layer_and_state(body.layer, body.state)

    def run(send: Callable[[BaseModel], None]) -> None:
        def report(stage: str, done: int | None, total: int | None) -> None:
            if stage == "downloading":
                send(CheckEvent(stage="downloading", progress_done=done, progress_total=total))
            elif stage == "unzipping":
                send(CheckEvent(stage="unzipping", progress_done=done, progress_total=total))
            else:
                send(CheckEvent(stage="reading"))

        try:
            checked = check_link(
                engine,
                body.layer,
                body.state,
                body.download_url,
                body.access_type,
                progress=report,
            )
            send(CheckEvent(stage="done", result=check_result(checked)))
        except (LoadError, httpx.HTTPError, OSError, SQLAlchemyError) as error:
            send(CheckEvent(stage="failed", error=str(error) or repr(error)))

    return stream_events(run)


@router.post(
    "/sources/checks", response_class=StreamingResponse, responses=streamed(SourcesCheckEvent)
)
def run_source_checks(engine: ReferenceEngine) -> StreamingResponse:
    """Check every loaded layer's source for a newer file, without downloading it.

    The admin page's **Check for updates** button and the weekly scheduled job call this.
    Each answer is recorded in ``public.source_checks``. The answer streams back one JSON
    line at a time: each layer and state as it's checked, then how many were checked, or
    why the check couldn't finish.

    Args:
        engine: Engine for the reference database.

    Returns:
        The streamed answer, as JSON lines (``application/x-ndjson``).
    """

    def run(send: Callable[[BaseModel], None]) -> None:
        def report(checked: int, total: int, layer: str, state: str) -> None:
            send(
                SourcesCheckEvent(
                    stage="checking", checked=checked, total=total, layer=layer, state=state
                )
            )

        try:
            count = check_sources(engine, progress=report)
            send(SourcesCheckEvent(stage="done", checked=count, total=count))
        except (httpx.HTTPError, OSError, SQLAlchemyError) as error:
            log.exception("source_checks_failed")
            send(SourcesCheckEvent(stage="failed", error=str(error) or repr(error)))

    return stream_events(run)


@router.get("/sources/checks")
def list_source_checks(engine: ReferenceEngine) -> SourceChecksRead:
    """Read what the last change check found.

    Args:
        engine: Engine for the reference database.

    Returns:
        When the last check ran, and each loaded layer and state whose newest check found
        a newer file or an error, with when it was last loaded.
    """
    newest = (
        select(SourceCheck)
        .ext(distinct_on(SourceCheck.layer, SourceCheck.state))
        .order_by(SourceCheck.layer, SourceCheck.state, SourceCheck.checked_at.desc())
    )
    pulled = (
        select(LoadRun.layer, LoadRun.state, func.max(LoadRun.finished_at))
        .where(LoadRun.status == "succeeded")
        .group_by(LoadRun.layer, LoadRun.state)
    )
    with Session(engine) as session:
        checked_at = session.scalar(select(func.max(SourceCheck.checked_at)))
        last_pulled = {(layer, state): at for layer, state, at in session.execute(pulled)}
        updates = [
            SourceUpdateRead(
                layer=check.layer,
                state=check.state,
                last_pulled=last_pulled.get((check.layer, check.state)),
                error=check.error,
            )
            for check in session.scalars(newest)
            if check.update_available or check.error is not None
        ]
    return SourceChecksRead(checked_at=checked_at, updates=updates)

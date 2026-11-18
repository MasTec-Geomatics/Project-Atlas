"""Reference database endpoints.

- ``/loads``: start loads. The admin page's Load button calls this; until that page
  exists, it is run from the API's ``/docs`` page.
- ``/sources``: add, list, and edit the download links in ``public.sources``.
"""

from collections.abc import Sequence
from datetime import datetime
from typing import Annotated

import httpx
import structlog
from fastapi import APIRouter, BackgroundTasks, Body, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Engine, func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from src.core.database import reference_engine
from src.reference.load import LayerSource, LoadError, enabled_sources, run_loads
from src.reference.loaders import LOADERS
from src.reference.models.public import Source
from src.reference.state_codes import STATE_FIPS

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/reference", tags=["reference"])

STATE_PATTERN = r"^[A-Z]{2}$"
URL_PATTERN = r"^https?://"


class LoadRequest(BaseModel):
    """One layer and state to load, one checked box on the admin page.

    Attributes:
        layer: Layer name, such as ``wetlands``.
        state: Two-letter state code, such as ``TX``.
    """

    layer: str
    state: str = Field(pattern=STATE_PATTERN)


class LoadsStarted(BaseModel):
    """Response when loads have been started.

    Attributes:
        loads: The layer and state pairs being loaded.
    """

    loads: list[LoadRequest]


class SourceCreate(BaseModel):
    """A new download link for one layer and state.

    Attributes:
        layer: Layer name, such as ``hydro.wetlands``.
        state: Two-letter state code, such as ``TX``.
        download_url: Link to the source file.
        format: Dataset format inside the download, such as ``gpkg``.
        license: Source license.
        attribution: Required attribution text.
        is_enabled: Whether loads include this source.
    """

    layer: str
    state: str = Field(pattern=STATE_PATTERN)
    download_url: str = Field(pattern=URL_PATTERN)
    format: str = Field(min_length=1)
    license: str | None = None
    attribution: str | None = None
    is_enabled: bool = True


class SourceUpdate(BaseModel):
    """Changes to an existing source. Only the fields sent are changed.

    Attributes:
        download_url: Link to the source file.
        format: Dataset format inside the download, such as ``gpkg``.
        license: Source license.
        attribution: Required attribution text.
        is_enabled: Whether loads include this source.
    """

    download_url: str | None = Field(default=None, pattern=URL_PATTERN)
    format: str | None = Field(default=None, min_length=1)
    license: str | None = None
    attribution: str | None = None
    is_enabled: bool | None = None


class SourceRead(BaseModel):
    """A ``public.sources`` row.

    Attributes:
        id: Row id.
        layer: Layer name, such as ``hydro.wetlands``.
        state: Two-letter state code.
        download_url: Link to the source file.
        format: Dataset format inside the download.
        license: Source license.
        attribution: Required attribution text.
        is_enabled: Whether loads include this source.
        updated_at: When the row was last changed.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    layer: str
    state: str
    download_url: str
    format: str
    license: str | None
    attribution: str | None
    is_enabled: bool
    updated_at: datetime


def get_reference_engine() -> Engine:
    """FastAPI dependency: the reference database engine. Tests override it."""
    return reference_engine


ReferenceEngine = Annotated[Engine, Depends(get_reference_engine)]


def run_background_loads(engine: Engine, sources: Sequence[LayerSource]) -> None:
    """Run the requested loads in the background.

    Each load records its outcome in ``public.load_runs`` and logs any failure, so a
    failure is not raised again here.

    Args:
        engine: Engine for the reference database.
        sources: The loads to run, one per layer and state.
    """
    try:
        run_loads(engine, sources)
    except LoadError, httpx.HTTPError, OSError, SQLAlchemyError:
        log.warning(
            "background_load_failed",
            loads=[f"{source.model.__tablename__}:{source.state}" for source in sources],
        )


@router.post("/loads", status_code=status.HTTP_202_ACCEPTED)
def start_loads(
    body: Annotated[list[LoadRequest], Body(min_length=1)],
    background_tasks: BackgroundTasks,
    engine: ReferenceEngine,
) -> LoadsStarted:
    """Load a list of layer and state pairs. Returns right away; loads run in the background.

    Pairs that share a download link, such as several states from one national file, are
    loaded from a single download. Results are recorded in ``public.load_runs``, one row
    per layer and state.

    Args:
        body: The layer and state pairs to load. Repeated pairs are loaded once.
        background_tasks: FastAPI's background task list.
        engine: Engine for the reference database.

    Returns:
        The layer and state pairs being loaded.

    Raises:
        HTTPException: 422 listing every pair that has no loader or no enabled source.
            Nothing is started when any pair has a problem.
    """
    pairs = list(dict.fromkeys((item.layer, item.state) for item in body))
    problems: list[str] = []
    layer_sources: list[LayerSource] = []

    for layer, state in pairs:
        loader = LOADERS.get(layer)
        if loader is None:
            problems.append(f"No loader for layer '{layer}'")
            continue
        sources = enabled_sources(engine, loader.layer, state)
        if not sources:
            problems.append(f"No enabled source for {loader.layer} in {state}")
            continue
        layer_sources.append(loader.layer_source(sources[0]))

    if problems:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, problems)

    background_tasks.add_task(run_background_loads, engine, layer_sources)
    return LoadsStarted(loads=[LoadRequest(layer=layer, state=state) for layer, state in pairs])


@router.get("/sources")
def list_sources(engine: ReferenceEngine) -> list[SourceRead]:
    """List every source, by layer and then state.

    Args:
        engine: Engine for the reference database.

    Returns:
        All ``public.sources`` rows.
    """
    with Session(engine) as session:
        sources = session.scalars(select(Source).order_by(Source.layer, Source.state))
        return [SourceRead.model_validate(source) for source in sources]


@router.post("/sources", status_code=status.HTTP_201_CREATED)
def create_source(body: SourceCreate, engine: ReferenceEngine) -> SourceRead:
    """Add the download link for one layer and state.

    Args:
        body: The new source.
        engine: Engine for the reference database.

    Returns:
        The saved source.

    Raises:
        HTTPException: 422 when no loader handles the layer or the state code is unknown;
            409 when the layer already has a source for the state.
    """
    if body.layer not in {loader.layer for loader in LOADERS.values()}:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, f"No loader for layer '{body.layer}'"
        )
    if body.state not in STATE_FIPS:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, f"Unknown state code '{body.state}'"
        )

    with Session(engine) as session, session.begin():
        existing = session.scalar(
            select(Source.id).where(Source.layer == body.layer, Source.state == body.state)
        )
        if existing is not None:
            raise HTTPException(
                status.HTTP_409_CONFLICT, f"{body.layer} already has a source for {body.state}"
            )
        source = Source(**body.model_dump())
        session.add(source)
        session.flush()
        session.refresh(source)
        return SourceRead.model_validate(source)


@router.patch("/sources/{source_id}")
def update_source(source_id: int, body: SourceUpdate, engine: ReferenceEngine) -> SourceRead:
    """Change an existing source. Only the fields sent are changed.

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

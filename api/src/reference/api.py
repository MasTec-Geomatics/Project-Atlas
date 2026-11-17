"""Reference database endpoints.

The admin page's Load button calls ``POST /api/v1/references/loads/{layer}``. Until that
page exists, the same endpoint is run from the API's ``/docs`` page.
"""

from typing import Annotated

import httpx
import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import Engine
from sqlalchemy.exc import SQLAlchemyError

from src.core.database import reference_engine
from src.reference.load import LoadError
from src.reference.loaders import LOADERS

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/reference", tags=["reference"])


class LoadStarted(BaseModel):
    """Response when a load has been started.

    Attributes:
        layer: The layer being loaded, such as ``wetlands``.
    """

    layer: str


def get_reference_engine() -> Engine:
    """FastAPI dependency: the reference database engine. Tests override it."""
    return reference_engine


def run_layer_load(layer: str, engine: Engine) -> None:
    """Run one layer's loader in the background.

    The loader records the outcome in ``public.load_runs`` and logs any failure, so a
    failure is not raised again here.

    Args:
        layer: Layer name, a key of ``LOADERS``.
        engine: Engine for the reference database.
    """
    try:
        LOADERS[layer](engine)
    except LoadError, httpx.HTTPError, OSError, SQLAlchemyError:
        log.warning("background_load_failed", layer=layer)


@router.post("/loads/{layer}", status_code=status.HTTP_202_ACCEPTED)
def start_load(
    layer: str,
    background_tasks: BackgroundTasks,
    engine: Annotated[Engine, Depends(get_reference_engine)],
) -> LoadStarted:
    """Start loading one reference layer. Returns right away; the load runs in the background.

    Progress and results are recorded in ``public.load_runs``.

    Args:
        layer: Layer name, such as ``wetlands``.
        background_tasks: FastAPI's background task lists.
        engine: Engine for the reference database.

    Returns:
        The layer that was started.

    Raises:
        HTTPException: 404 when there is no loader for the layer.
    """
    if layer not in LOADERS:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No loader for layer '{layer}'")
    background_tasks.add_task(run_layer_load, layer, engine)
    return LoadStarted(layer=layer)

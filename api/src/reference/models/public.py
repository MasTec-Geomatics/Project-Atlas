"""Tables in the ``public`` schema: sources and load bookkeeping (ADR 0018)."""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Identity,
    Index,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import ReferenceBase


class Source(ReferenceBase):
    """Where a layer comes from and how to read it.

    A source with no ``state`` is federal and covers every state. A source with a
    ``state`` covers only that state. A load uses the state source if there is one,
    otherwise the federal source.
    """

    __tablename__ = "sources"
    __table_args__ = (
        UniqueConstraint("layer", "state", postgresql_nulls_not_distinct=True),
        CheckConstraint("access_type IN ('file', 'service')", name="access_type"),
        {"schema": "public"},
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    layer: Mapped[str]
    state: Mapped[str | None]
    download_url: Mapped[str]
    access_type: Mapped[str]
    format: Mapped[str]
    source_layer: Mapped[str | None]
    field_mapping: Mapped[dict[str, str]] = mapped_column(JSONB)
    keep: Mapped[dict[str, list[str]] | None] = mapped_column(JSONB)
    clip_to_state: Mapped[bool] = mapped_column(server_default="false")
    license: Mapped[str | None]
    attribution: Mapped[str | None]
    is_enabled: Mapped[bool] = mapped_column(server_default="true")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class LoadRun(ReferenceBase):
    """One row per load of a layer for a state.

    While a load is running, ``stage`` is ``downloading``, ``copying`` (into staging), or
    ``swapping`` (into the final table), and the download's progress is in
    ``bytes_downloaded`` and ``bytes_total``. ``stage`` is cleared when the load ends.
    """

    __tablename__ = "load_runs"
    __table_args__ = (
        CheckConstraint("status IN ('running', 'succeeded', 'failed')", name="status"),
        CheckConstraint("stage IN ('downloading', 'copying', 'swapping')", name="stage"),
        Index("load_runs_layer_state_started_idx", "layer", "state", "started_at"),
        {"schema": "public"},
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    layer: Mapped[str]
    state: Mapped[str]
    status: Mapped[str]
    stage: Mapped[str | None]
    bytes_downloaded: Mapped[int | None] = mapped_column(BigInteger)
    bytes_total: Mapped[int | None] = mapped_column(BigInteger)
    source_version: Mapped[str | None]
    rows_loaded: Mapped[int | None]
    error: Mapped[str | None]
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SourceCheck(ReferenceBase):
    """One row per change check of a layer's source for a state."""

    __tablename__ = "source_checks"
    __table_args__ = (
        Index(None, "layer", "state", "checked_at"),
        {"schema": "public"},
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    layer: Mapped[str]
    state: Mapped[str]
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    source_version: Mapped[str | None]
    update_available: Mapped[bool]
    error: Mapped[str | None]

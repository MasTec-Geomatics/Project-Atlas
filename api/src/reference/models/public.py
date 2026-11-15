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
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import ReferenceBase


class Source(ReferenceBase):
    """Where each layer is downloaded from, per state. Maintainers edit rows."""

    __tablename__ = "sources"
    __table_args__ = (
        UniqueConstraint("layer", "state"),
        {"schema": "public"},
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    layer: Mapped[str]
    state: Mapped[str]
    download_url: Mapped[str]
    format: Mapped[str]
    license: Mapped[str | None]
    attribution: Mapped[str | None]
    is_enabled: Mapped[bool] = mapped_column(server_default="true")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class LoadRun(ReferenceBase):
    """One row per load of a layer for a state."""

    __tablename__ = "load_runs"
    __table_args__ = (
        CheckConstraint("status IN ('running', 'succeeded', 'failed')", name="status"),
        Index("load_runs_layer_state_started_idx", "layer", "state", "started_at"),
        {"schema": "public"},
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    layer: Mapped[str]
    state: Mapped[str]
    status: Mapped[str]
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

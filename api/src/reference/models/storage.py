"""Tables in the ``storage`` schema: files kept outside the database."""

from datetime import date, datetime

from geoalchemy2 import Geometry, WKBElement
from sqlalchemy import BigInteger, DateTime, Identity, Index, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import ReferenceBase

SCHEMA = "storage"


class RasterAsset(ReferenceBase):
    """One raster file, recorded as storage system plus key, with its footprint."""

    __tablename__ = "raster_assets"
    __table_args__ = (
        UniqueConstraint("storage_system", "storage_key"),
        Index("raster_assets_footprint_idx", "footprint", postgresql_using="gist"),
        {"schema": SCHEMA},
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    state: Mapped[str] = mapped_column(index=True)
    layer: Mapped[str]
    storage_system: Mapped[str]
    storage_key: Mapped[str]
    source: Mapped[str]
    source_date: Mapped[date | None]
    loaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    footprint: Mapped[WKBElement] = mapped_column(
        Geometry("POLYGON", srid=4326, spatial_index=False)
    )

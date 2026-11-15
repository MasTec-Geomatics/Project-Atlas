"""Tables in the ``utilities`` schema."""

from geoalchemy2 import Geometry, WKBElement
from sqlalchemy import BigInteger, Identity, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import ReferenceBase

SCHEMA = "utilities"


class WaterWell(ReferenceBase):
    """TWDB groundwater database wells."""

    __tablename__ = "water_wells"
    __table_args__ = (
        UniqueConstraint("state", "state_well_number"),
        Index("water_wells_geom_idx", "geom", postgresql_using="gist"),
        {"schema": SCHEMA},
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    state: Mapped[str]
    state_well_number: Mapped[str]
    well_use: Mapped[str | None]
    geom: Mapped[WKBElement] = mapped_column(Geometry("POINT", srid=4326, spatial_index=False))

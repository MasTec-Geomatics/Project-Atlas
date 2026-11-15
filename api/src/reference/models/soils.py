"""Tables in the ``soils`` schema."""

from geoalchemy2 import Geometry, WKBElement
from sqlalchemy import BigInteger, Identity, Index
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import ReferenceBase

SCHEMA = "soils"


class MapUnit(ReferenceBase):
    """NRCS gSSURGO map unit polygons."""

    __tablename__ = "map_units"
    __table_args__ = (
        Index("map_units_geom_idx", "geom", postgresql_using="gist"),
        {"schema": SCHEMA},
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    state: Mapped[str] = mapped_column(index=True)
    mukey: Mapped[str]
    musym: Mapped[str | None]
    muname: Mapped[str | None]
    geom: Mapped[WKBElement] = mapped_column(
        Geometry("MULTIPOLYGON", srid=4326, spatial_index=False)
    )

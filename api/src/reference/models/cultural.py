"""Tables in the ``cultural`` schema."""

from geoalchemy2 import Geometry, WKBElement
from sqlalchemy import BigInteger, Identity, Index
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import ReferenceBase

SCHEMA = "cultural"


class NationalRegisterProperty(ReferenceBase):
    """NPS National Register of Historic Places (points and polygons)."""

    __tablename__ = "nrhp"
    __table_args__ = (
        Index("nrhp_geom_idx", "geom", postgresql_using="gist"),
        {"schema": SCHEMA},
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    state: Mapped[str] = mapped_column(index=True)
    ref_number: Mapped[str]
    name: Mapped[str]
    geom: Mapped[WKBElement] = mapped_column(Geometry("GEOMETRY", srid=4326, spatial_index=False))


class Cemetery(ReferenceBase):
    """THC cemeteries. ``location_known`` is false for vicinity cemeteries."""

    __tablename__ = "cemeteries"
    __table_args__ = (
        Index("cemeteries_geom_idx", "geom", postgresql_using="gist"),
        {"schema": SCHEMA},
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    state: Mapped[str] = mapped_column(index=True)
    name: Mapped[str | None]
    location_known: Mapped[bool]
    geom: Mapped[WKBElement] = mapped_column(Geometry("GEOMETRY", srid=4326, spatial_index=False))


class Marker(ReferenceBase):
    """THC historical markers."""

    __tablename__ = "markers"
    __table_args__ = (
        Index("markers_geom_idx", "geom", postgresql_using="gist"),
        {"schema": SCHEMA},
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    state: Mapped[str] = mapped_column(index=True)
    marker_number: Mapped[str | None]
    title: Mapped[str]
    geom: Mapped[WKBElement] = mapped_column(Geometry("POINT", srid=4326, spatial_index=False))

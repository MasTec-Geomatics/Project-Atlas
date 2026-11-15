"""Tables in the ``hydro`` schema."""

from decimal import Decimal

from geoalchemy2 import Geometry, WKBElement
from sqlalchemy import BigInteger, Identity, Index
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import ReferenceBase

SCHEMA = "hydro"


class Wetland(ReferenceBase):
    """USFWS National Wetlands Inventory polygons."""

    __tablename__ = "wetlands"
    __table_args__ = (
        Index("wetlands_geom_idx", "geom", postgresql_using="gist"),
        {"schema": SCHEMA},
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    state: Mapped[str] = mapped_column(index=True)
    cowardin_code: Mapped[str]
    wetland_type: Mapped[str]
    acres: Mapped[Decimal | None]
    geom: Mapped[WKBElement] = mapped_column(
        Geometry("MULTIPOLYGON", srid=4326, spatial_index=False)
    )


class Flowline(ReferenceBase):
    """USGS 3DHP flowlines, including canals and ditches."""

    __tablename__ = "flowlines"
    __table_args__ = (
        Index("flowlines_geom_idx", "geom", postgresql_using="gist"),
        {"schema": SCHEMA},
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    state: Mapped[str] = mapped_column(index=True)
    id3dhp: Mapped[str] = mapped_column(unique=True)
    name: Mapped[str | None]
    feature_type: Mapped[str]
    geom: Mapped[WKBElement] = mapped_column(
        Geometry("MULTILINESTRING", srid=4326, spatial_index=False)
    )


class Waterbody(ReferenceBase):
    """USGS 3DHP waterbodies."""

    __tablename__ = "waterbodies"
    __table_args__ = (
        Index("waterbodies_geom_idx", "geom", postgresql_using="gist"),
        {"schema": SCHEMA},
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    state: Mapped[str] = mapped_column(index=True)
    id3dhp: Mapped[str] = mapped_column(unique=True)
    name: Mapped[str | None]
    feature_type: Mapped[str]
    geom: Mapped[WKBElement] = mapped_column(
        Geometry("MULTIPOLYGON", srid=4326, spatial_index=False)
    )


class StreamSegment(ReferenceBase):
    """TCEQ classified stream segments."""

    __tablename__ = "stream_segments"
    __table_args__ = (
        Index("stream_segments_geom_idx", "geom", postgresql_using="gist"),
        {"schema": SCHEMA},
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    state: Mapped[str] = mapped_column(index=True)
    segment_id: Mapped[str]
    segment_name: Mapped[str | None]
    basin: Mapped[str | None]
    geom: Mapped[WKBElement] = mapped_column(Geometry("GEOMETRY", srid=4326, spatial_index=False))


class FloodFema(ReferenceBase):
    """FEMA National Flood Hazard Layer zones."""

    __tablename__ = "flood_fema"
    __table_args__ = (
        Index("flood_fema_geom_idx", "geom", postgresql_using="gist"),
        {"schema": SCHEMA},
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    state: Mapped[str] = mapped_column(index=True)
    flood_zone: Mapped[str]
    zone_subtype: Mapped[str | None]
    sfha: Mapped[bool]
    static_bfe: Mapped[Decimal | None]
    geom: Mapped[WKBElement] = mapped_column(
        Geometry("MULTIPOLYGON", srid=4326, spatial_index=False)
    )


class FloodBle(ReferenceBase):
    """TWDB Base Level Engineering floodplain."""

    __tablename__ = "flood_ble"
    __table_args__ = (
        Index("flood_ble_geom_idx", "geom", postgresql_using="gist"),
        {"schema": SCHEMA},
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    state: Mapped[str] = mapped_column(index=True)
    huc8: Mapped[str]
    flood_zone: Mapped[str]
    geom: Mapped[WKBElement] = mapped_column(
        Geometry("MULTIPOLYGON", srid=4326, spatial_index=False)
    )

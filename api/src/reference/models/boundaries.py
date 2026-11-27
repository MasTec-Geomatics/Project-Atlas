"""Tables in the ``boundaries`` schema: areas users navigate by (ADR 0021)."""

from geoalchemy2 import Geometry, WKBElement
from sqlalchemy import BigInteger, Identity, Index
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import ReferenceBase

SCHEMA = "boundaries"
SCHEMA_TITLE = "Boundaries"


class State(ReferenceBase):
    """Census TIGER/Line states, full detail. Used to cut national sources at state lines."""

    __tablename__ = "states"
    __table_args__ = (
        Index("states_geom_idx", "geom", postgresql_using="gist"),
        {"schema": SCHEMA, "info": {"title": "States", "group": SCHEMA_TITLE}},
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    state: Mapped[str] = mapped_column(unique=True)
    name: Mapped[str]
    geom: Mapped[WKBElement] = mapped_column(
        Geometry("MULTIPOLYGON", srid=4326, spatial_index=False)
    )


class County(ReferenceBase):
    """Census TIGER/Line counties, full detail."""

    __tablename__ = "counties"
    __table_args__ = (
        Index("counties_geom_idx", "geom", postgresql_using="gist"),
        {"schema": SCHEMA, "info": {"title": "Counties", "group": SCHEMA_TITLE}},
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    state: Mapped[str] = mapped_column(index=True)
    geoid: Mapped[str] = mapped_column(unique=True)
    name: Mapped[str]
    geom: Mapped[WKBElement] = mapped_column(
        Geometry("MULTIPOLYGON", srid=4326, spatial_index=False)
    )


class Place(ReferenceBase):
    """Census TIGER/Line places, full detail: cities, towns, villages, and CDPs.

    No county column: places can cross county lines, so the places in a county are found
    by spatial overlap.
    """

    __tablename__ = "places"
    __table_args__ = (
        Index("places_geom_idx", "geom", postgresql_using="gist"),
        {"schema": SCHEMA, "info": {"title": "Cities and towns", "group": SCHEMA_TITLE}},
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    state: Mapped[str] = mapped_column(index=True)
    geoid: Mapped[str] = mapped_column(unique=True)
    name: Mapped[str]
    geom: Mapped[WKBElement] = mapped_column(
        Geometry("MULTIPOLYGON", srid=4326, spatial_index=False)
    )

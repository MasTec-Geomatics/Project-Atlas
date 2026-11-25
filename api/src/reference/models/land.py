"""Tables in the ``land`` schema."""

from geoalchemy2 import Geometry, WKBElement
from sqlalchemy import BigInteger, CheckConstraint, Identity, Index
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import ReferenceBase

SCHEMA = "land"
SCHEMA_TITLE = "Land"


class ProtectedArea(ReferenceBase):
    """USGS PAD-US protected areas."""

    __tablename__ = "protected_areas"
    __table_args__ = (
        CheckConstraint("category IN ('Fee', 'Easement', 'Designation')", name="category"),
        Index("protected_areas_geom_idx", "geom", postgresql_using="gist"),
        {"schema": SCHEMA, "info": {"title": "Protected areas", "group": SCHEMA_TITLE}},
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    state: Mapped[str] = mapped_column(index=True)
    unit_name: Mapped[str | None]
    manager_name: Mapped[str | None]
    category: Mapped[str]
    gap_status: Mapped[str | None]
    geom: Mapped[WKBElement] = mapped_column(
        Geometry("MULTIPOLYGON", srid=4326, spatial_index=False)
    )


class Parcel(ReferenceBase):
    """TxGIO StratMap land parcels."""

    __tablename__ = "parcels"
    __table_args__ = (
        Index("parcels_geom_idx", "geom", postgresql_using="gist"),
        {"schema": SCHEMA, "info": {"title": "Parcels", "group": SCHEMA_TITLE}},
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    state: Mapped[str] = mapped_column(index=True)
    county: Mapped[str]
    prop_id: Mapped[str | None]
    owner_name: Mapped[str | None]
    situs_address: Mapped[str | None]
    geom: Mapped[WKBElement] = mapped_column(
        Geometry("MULTIPOLYGON", srid=4326, spatial_index=False)
    )

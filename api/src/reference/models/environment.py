"""Tables in the ``environment`` schema."""

from geoalchemy2 import Geometry, WKBElement
from sqlalchemy import BigInteger, CheckConstraint, Identity, Index
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import ReferenceBase

SCHEMA = "environment"
SCHEMA_TITLE = "Environment"


class CriticalHabitat(ReferenceBase):
    """USFWS ECOS critical habitat."""

    __tablename__ = "critical_habitat"
    __table_args__ = (
        CheckConstraint("designation_status IN ('final', 'proposed')", name="designation_status"),
        Index("critical_habitat_geom_idx", "geom", postgresql_using="gist"),
        {"schema": SCHEMA, "info": {"title": "Critical habitat", "group": SCHEMA_TITLE}},
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    state: Mapped[str] = mapped_column(index=True)
    common_name: Mapped[str]
    scientific_name: Mapped[str]
    listing_status: Mapped[str]
    designation_status: Mapped[str]
    geom: Mapped[WKBElement] = mapped_column(Geometry("GEOMETRY", srid=4326, spatial_index=False))

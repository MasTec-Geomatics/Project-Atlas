"""Tables in the ``energy`` schema."""

from decimal import Decimal

from geoalchemy2 import Geometry, WKBElement
from sqlalchemy import BigInteger, Identity, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import ReferenceBase

SCHEMA = "energy"


class OilGasWell(ReferenceBase):
    """RRC oil and gas wells."""

    __tablename__ = "oilgas_wells"
    __table_args__ = (
        Index("oilgas_wells_geom_idx", "geom", postgresql_using="gist"),
        {"schema": SCHEMA},
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    state: Mapped[str] = mapped_column(index=True)
    api_number: Mapped[str]
    well_type: Mapped[str | None]
    geom: Mapped[WKBElement] = mapped_column(Geometry("POINT", srid=4326, spatial_index=False))


class Pipeline(ReferenceBase):
    """RRC pipelines."""

    __tablename__ = "pipelines"
    __table_args__ = (
        Index("pipelines_geom_idx", "geom", postgresql_using="gist"),
        {"schema": SCHEMA},
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    state: Mapped[str] = mapped_column(index=True)
    t4_permit: Mapped[str | None]
    operator_name: Mapped[str | None]
    commodity: Mapped[str | None]
    diameter_in: Mapped[Decimal | None]
    interstate: Mapped[bool | None]
    geom: Mapped[WKBElement] = mapped_column(
        Geometry("MULTILINESTRING", srid=4326, spatial_index=False)
    )


class TransmissionLineHifld(ReferenceBase):
    """HIFLD Open archive transmission lines (frozen; data dated 2025-02-19)."""

    __tablename__ = "transmission_lines_hifld"
    __table_args__ = (
        Index("transmission_lines_hifld_geom_idx", "geom", postgresql_using="gist"),
        {"schema": SCHEMA},
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    state: Mapped[str] = mapped_column(index=True)
    owner: Mapped[str | None]
    voltage_kv: Mapped[Decimal | None]
    geom: Mapped[WKBElement] = mapped_column(
        Geometry("MULTILINESTRING", srid=4326, spatial_index=False)
    )


class TransmissionLineOsm(ReferenceBase):
    """OpenStreetMap power=line from Geofabrik state extracts (ODbL)."""

    __tablename__ = "transmission_lines_osm"
    __table_args__ = (
        UniqueConstraint("state", "osm_id"),
        Index("transmission_lines_osm_geom_idx", "geom", postgresql_using="gist"),
        {"schema": SCHEMA},
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    state: Mapped[str]
    osm_id: Mapped[int] = mapped_column(BigInteger)
    operator: Mapped[str | None]
    voltage: Mapped[str | None]
    geom: Mapped[WKBElement] = mapped_column(
        Geometry("MULTILINESTRING", srid=4326, spatial_index=False)
    )
